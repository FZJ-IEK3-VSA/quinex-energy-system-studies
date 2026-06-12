# Start: streamlit run streamlit/streamlit_app.py --server.address 0.0.0.0
# Aufruf aus VPN: http://134.94.54.174:8501/
# Lokal: http://127.0.0.1:8501/
import os
import math
import hmac
import streamlit as st
from utils import duckdb_filter, style, unit_filter
from components import header, dataframe_view, pagination_download, filters, visualisation, column_analysis


# --- Setup ---
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__)))
LOGO_FILE = os.path.join(BASE_DIR, "assets", "Jülich Systems Analysis.svg")
DEFAULT_ROWS_PER_PAGE = 10

ENV_PATH = os.path.abspath(os.path.join(BASE_DIR, "..", ".env"))


def _load_env_file(path):
    if not os.path.exists(path):
        return

    with open(path, "r", encoding="utf-8") as env_file:
        for line in env_file:
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue

            if stripped.startswith("export "):
                stripped = stripped[len("export "):].strip()
                if not stripped or "=" not in stripped:
                    continue

            key, value = stripped.split("=", 1)
            key = key.strip()
            value = value.strip()

            # Remove trailing inline comments for unquoted values.
            if value and not value.startswith(("\"", "'")):
                value = value.split("#", 1)[0].strip()

            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


_load_env_file(ENV_PATH)

DEFAULT_REGEX_GROUPS = {
    "Entity": [
        ["Battery", "battery", "batteries"],
        ["Photovoltaic", "photovoltaic", "pv"],
    ],
    "Property": [
        ["Lifetime", "lifetime", "lifespan"],
        ["Efficiency", "efficiency"],
    ],
    "Unit": [["years"], ["%"]],
    "Year": [[""], [""]],
}


def _initialize_session_state():
    if "page" not in st.session_state:
        st.session_state.page = 1

    if "rows_per_page" not in st.session_state:
        st.session_state.rows_per_page = DEFAULT_ROWS_PER_PAGE

    if "regex_groups" not in st.session_state:
        st.session_state.regex_groups = {
            key: [list(row) for row in rows]
            for key, rows in DEFAULT_REGEX_GROUPS.items()
        }

    if "regex_hidden_groups" not in st.session_state:
        st.session_state.regex_hidden_groups = {
            "Entity": [False] * len(st.session_state.regex_groups.get("Entity", [])),
            "Property": [False] * len(st.session_state.regex_groups.get("Property", [])),
        }

    if "property_visible_indices" not in st.session_state:
        property_rows = st.session_state.regex_groups.get("Property", [])
        hidden_property = st.session_state.regex_hidden_groups.get("Property", [False] * len(property_rows))
        st.session_state.property_visible_indices = [
            idx for idx, hidden in enumerate(hidden_property) if not hidden
        ]


def _is_authenticated():
    # Reset auth on new websocket visits (new tab / reopened page / hard reload).
    headers = getattr(st.context, "headers", {})
    current_visit_id = None
    if isinstance(headers, dict):
        current_visit_id = headers.get("sec-websocket-key") or headers.get("Sec-Websocket-Key")

    previous_visit_id = st.session_state.get("auth_visit_id")
    if current_visit_id and previous_visit_id != current_visit_id:
        st.session_state["app_authenticated"] = False
        st.session_state["auth_visit_id"] = current_visit_id

    expected_password = os.getenv("STREAMLIT_APP_PASSWORD", "")
    if not expected_password:
        st.error("No password configured. Set STREAMLIT_APP_PASSWORD in the project .env file.")
        return False

    if "app_authenticated" not in st.session_state:
        st.session_state.app_authenticated = False

    if st.session_state.app_authenticated:
        return True

    entered_password = st.text_input("App password", type="password")
    if st.button("Login", use_container_width=True):
        st.session_state.app_authenticated = hmac.compare_digest(
            entered_password,
            expected_password,
        )
        if not st.session_state.app_authenticated:
            st.error("Wrong password.")
        else:
            st.rerun()

    return False


def _build_regex_mapping(entity_group_values, property_group_values, metadata_group_values):
    mapping = {
        "Entity": entity_group_values,
        "Property": property_group_values,
    }
    mapping.update(metadata_group_values)

    visible_property_indices = st.session_state.get("property_visible_indices", [])

    for aux_key in ("Unit", "Year"):
        if aux_key not in st.session_state.regex_groups:
            continue

        aux_rows = st.session_state.regex_groups[aux_key]
        if not isinstance(aux_rows, list):
            continue

        if visible_property_indices:
            mapping[aux_key] = [
                aux_rows[idx] for idx in visible_property_indices if idx < len(aux_rows)
            ]
        else:
            mapping[aux_key] = []

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


def _fetch_page_data(active_regex_filters, active_regex_mapping, rows_limit):
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
        total_pages = max(1, math.ceil(total_count / rows_limit))
        current_page = min(st.session_state.page, total_pages)
        st.session_state.page = current_page

        start_idx = (current_page - 1) * rows_limit
        end_idx = start_idx + rows_limit
        page_df = all_df.iloc[start_idx:end_idx].reset_index(drop=True)
        st.session_state.value_filtered_df_all = all_df
        return total_count, page_df

    total_count = duckdb_filter.get_total_rows(active_regex_filters)
    total_pages = max(1, math.ceil(total_count / rows_limit))
    current_page = min(st.session_state.page, total_pages)
    st.session_state.page = current_page
    offset = (current_page - 1) * rows_limit

    page_df = duckdb_filter.get_page(active_regex_filters, limit=rows_limit, offset=offset)
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

if not _is_authenticated():
    st.info("Please enter the app password to continue.")
    st.stop()

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
selected_page_size = st.session_state.rows_per_page
total_rows, df_page = _fetch_page_data(regex_filters, regex_mapping, selected_page_size)

# Untere Dashboard-Tabs
tab_data, tab_freq, tab_temporal, tab_spatial = st.tabs([
    "📋 Data",
    "📊 Column Frequency",
    "📈 Temporal Plot",
    "🌍 Spatial Plot",
])

with tab_data:
    rows_per_page_options = [10, 25, 50, 100]
    current_rows_per_page = st.session_state.rows_per_page
    if current_rows_per_page not in rows_per_page_options:
        current_rows_per_page = DEFAULT_ROWS_PER_PAGE

    selected_rows_per_page = st.selectbox(
        "Rows per page",
        options=rows_per_page_options,
        index=rows_per_page_options.index(current_rows_per_page),
    )

    if selected_rows_per_page != st.session_state.rows_per_page:
        st.session_state.rows_per_page = selected_rows_per_page
        st.session_state.page = 1
        st.rerun()

    # --- DataFrame Anzeige ---
    dataframe_view.render(df_page, selected_page_size)

    # --- Pagination + Download ---
    pagination_download.render(total_rows, selected_page_size, regex_filters, regex_mapping)

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