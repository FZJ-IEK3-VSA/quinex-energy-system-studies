import os
import streamlit as st
from utils import duckdb_filter, style, unit_filter
from components import header, dataframe_view, pagination_download, filters, visualisation

# --- Setup ---
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__)))
LOGO_FILE = os.path.join(BASE_DIR, "assets", "Jülich Systems Analysis.svg")

st.set_page_config(
    page_title="Data Viewer",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Styling / UI Setup ---
style.add_textinput_style()
style.set_vertical_alignment()
style.set_warning_color()

# --- Header ---
header.render(LOGO_FILE)

# --- Session State Defaults ---
if 'page' not in st.session_state:
    st.session_state.page = 1

if "regex_groups" not in st.session_state:
    st.session_state.regex_groups = {
        "Entity": [["", ""]],
        "Property": [["", ""]]
    }

# Filter UI
regex_mapping = filters.render_filters()
regex_filters = duckdb_filter.flatten_regex_filters(regex_mapping)

ROWS_PER_PAGE = 10
page = st.session_state.page

# --- Daten abfragen ---
total_rows = duckdb_filter.get_total_rows(regex_filters)
df_page = duckdb_filter.get_page(regex_filters, limit=ROWS_PER_PAGE, offset=(page-1)*ROWS_PER_PAGE)
df_page = duckdb_filter.apply_master_mapping(df_page, regex_mapping)

# --- Unit-Filtern ---
df_page = unit_filter.apply_unit_filters(df_page, regex_mapping)

# --- Tabs für Data / Plots ---
tab_data, tab_temporal, tab_spatial = st.tabs(["Data", "Temporal Plot", "Spatial Plot"])

with tab_data:
    # --- DataFrame Anzeige ---
    dataframe_view.render(df_page, ROWS_PER_PAGE)

    # --- Pagination + Download ---
    pagination_download.render(total_rows, ROWS_PER_PAGE, regex_filters, regex_mapping)

with tab_temporal:
    # --- Visualisation ---
    visualisation.render_temporal(total_rows, regex_filters, regex_mapping)

with tab_spatial:
    # --- Visualisation ---
    visualisation.render_spatial(total_rows, regex_filters, regex_mapping)