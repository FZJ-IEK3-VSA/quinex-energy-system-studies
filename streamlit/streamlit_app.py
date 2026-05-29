# Start: streamlit run streamlit/streamlit_app.py --server.address 0.0.0.0
# Aufruf aus VPN: http://134.94.54.174:8501/
# Lokal: http://127.0.0.1:8501/
import os
import math
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


def _to_stable_signature(value):
    if isinstance(value, dict):
        return tuple((k, _to_stable_signature(v)) for k, v in sorted(value.items(), key=lambda item: str(item[0])))
    if isinstance(value, list):
        return tuple(_to_stable_signature(v) for v in value)
    if isinstance(value, tuple):
        return tuple(_to_stable_signature(v) for v in value)
    return value


def _reset_page_on_filter_change(active_regex_filters):
    current_signature = _to_stable_signature(active_regex_filters)
    previous_signature = st.session_state.get("last_regex_filters_signature")

    if previous_signature is None:
        st.session_state.last_regex_filters_signature = current_signature
        return

    if current_signature != previous_signature:
        st.session_state.page = 1
        st.session_state.last_regex_filters_signature = current_signature


def _fetch_page_data(active_regex_filters, active_regex_mapping):
    value_min, value_max = duckdb_filter.get_value_range_from_filters(active_regex_filters)
    value_range_active = value_min is not None or value_max is not None
    st.session_state.value_range_active = value_range_active

    if value_range_active:
        total_base = duckdb_filter.get_total_rows(active_regex_filters)
        all_df = duckdb_filter.get_page(active_regex_filters, limit=total_base, offset=0)
        all_df = duckdb_filter.apply_master_mapping(all_df, active_regex_mapping)
        all_df = unit_filter.apply_unit_filters(all_df, active_regex_mapping)
        all_df = duckdb_filter.add_effective_value_column(all_df)
        all_df = duckdb_filter.apply_value_range_filter(all_df, min_value=value_min, max_value=value_max)

        total_count = len(all_df)
        total_pages = max(1, math.ceil(total_count / ROWS_PER_PAGE))
        current_page = min(st.session_state.page, total_pages)
        st.session_state.page = current_page

        start_idx = (current_page - 1) * ROWS_PER_PAGE
        end_idx = start_idx + ROWS_PER_PAGE
        page_df = all_df.iloc[start_idx:end_idx].reset_index(drop=True)
        st.session_state.value_filtered_df_all = all_df
        return total_count, page_df

    total_count = duckdb_filter.get_total_rows(active_regex_filters)
    total_pages = max(1, math.ceil(total_count / ROWS_PER_PAGE))
    current_page = min(st.session_state.page, total_pages)
    st.session_state.page = current_page
    offset = (current_page - 1) * ROWS_PER_PAGE

    page_df = duckdb_filter.get_page(active_regex_filters, limit=ROWS_PER_PAGE, offset=offset)
    page_df = duckdb_filter.apply_master_mapping(page_df, active_regex_mapping)
    page_df = unit_filter.apply_unit_filters(page_df, active_regex_mapping)
    page_df = duckdb_filter.add_effective_value_column(page_df)
    st.session_state.value_filtered_df_all = None
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
_reset_page_on_filter_change(regex_filters)

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
    column_analysis.render(
        regex_filters,
        regex_mapping,
        st.session_state.get("value_filtered_df_all"),
    )

with tab_temporal:
    # --- Visualisation ---
    visualisation.render_temporal(regex_filters, regex_mapping)

with tab_spatial:
    # --- Visualisation ---
    visualisation.render_spatial(regex_filters, regex_mapping)