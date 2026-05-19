# Start: streamlit run streamlit/streamlit_app.py --server.address 0.0.0.0
# Aufruf aus VPN: http://134.94.54.174:8501/
# Lokal: http://127.0.0.1:8501/
import os
import streamlit as st
from utils import duckdb_filter, style, unit_filter
from components import header, dataframe_view, pagination_download, filters, visualisation, column_analysis


# --- Setup ---
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__)))
LOGO_FILE = os.path.join(BASE_DIR, "assets", "Jülich Systems Analysis.svg")
ROWS_PER_PAGE = 10


def _initialize_session_state():
    if "page" not in st.session_state:
        st.session_state.page = 1

    if "regex_groups" not in st.session_state:
        st.session_state.regex_groups = {
            "Entity": [["", ""]],
            "Property": [["", ""]],
        }


def _build_regex_mapping(entity_group_values, property_group_values, metadata_group_values):
    mapping = {
        "Entity": entity_group_values,
        "Property": property_group_values,
    }
    mapping.update(metadata_group_values)

    for aux_key in ("Unit", "Year"):
        if aux_key in st.session_state.regex_groups:
            mapping[aux_key] = st.session_state.regex_groups[aux_key]

    return mapping


def _fetch_page_data(active_regex_filters, active_regex_mapping):
    total_count = duckdb_filter.get_total_rows(active_regex_filters)
    current_page = st.session_state.page
    offset = (current_page - 1) * ROWS_PER_PAGE

    page_df = duckdb_filter.get_page(active_regex_filters, limit=ROWS_PER_PAGE, offset=offset)
    page_df = duckdb_filter.apply_master_mapping(page_df, active_regex_mapping)
    page_df = unit_filter.apply_unit_filters(page_df, active_regex_mapping)
    return total_count, page_df

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
style.add_form_input_border()

# --- Header ---
header.render(LOGO_FILE)

# --- Session State Defaults ---
_initialize_session_state()

# Obere Filter-Tabs
tab_entity, tab_property, tab_metadata = st.tabs([
    "🏷️ Entity Filtering",
    "⚙️ Property Filtering",
    "🧭 Metadata Filtering",
])

with tab_entity:
    entity_groups = filters.render_entity_filter()

with tab_property:
    property_groups = filters.render_property_filter()

with tab_metadata:
    metadata_groups = filters.render_metadata_filter(entity_groups, property_groups)

filters.render_sidebar_readme()

regex_mapping = _build_regex_mapping(entity_groups, property_groups, metadata_groups)

regex_filters = duckdb_filter.flatten_regex_filters(regex_mapping)

# --- Daten abfragen und Unit-Filtern ---
total_rows, df_page = _fetch_page_data(regex_filters, regex_mapping)

# Untere Dashboard-Tabs
tab_data, tab_freq, tab_temporal, tab_spatial = st.tabs([
    "📋 Data",
    "📊 Column Frequency",
    "📈 Temporal Plot",
    "🌍 Spatial Plot",
])

with tab_data:
    # --- DataFrame Anzeige ---
    dataframe_view.render(df_page, ROWS_PER_PAGE)

    # --- Pagination + Download ---
    pagination_download.render(total_rows, ROWS_PER_PAGE, regex_filters, regex_mapping)

with tab_freq:
    # --- Column Frequency Analysis ---
    column_analysis.render(regex_filters, regex_mapping)

with tab_temporal:
    # --- Visualisation ---
    visualisation.render_temporal(total_rows, regex_filters, regex_mapping)

with tab_spatial:
    # --- Visualisation ---
    visualisation.render_spatial(total_rows, regex_filters, regex_mapping)