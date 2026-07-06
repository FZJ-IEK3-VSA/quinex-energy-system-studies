import streamlit as st
from utils import duckdb_filter
from components import mapping_cards

PROPERTY_AUX_FIELDS = ("Unit", "Year")


def _ensure_hidden_state(col_name, groups):
    if "regex_hidden_groups" not in st.session_state:
        st.session_state.regex_hidden_groups = {}

    hidden = st.session_state.regex_hidden_groups.get(col_name)
    if not isinstance(hidden, list):
        hidden = [False] * len(groups)

    if len(hidden) < len(groups):
        hidden.extend([False] * (len(groups) - len(hidden)))
    elif len(hidden) > len(groups):
        hidden = hidden[: len(groups)]

    st.session_state.regex_hidden_groups[col_name] = hidden


def _delete_hidden_row(col_name, row_idx):
    if "regex_hidden_groups" not in st.session_state:
        return

    hidden = st.session_state.regex_hidden_groups.get(col_name)
    if isinstance(hidden, list) and len(hidden) > row_idx:
        del hidden[row_idx]


def _add_hidden_row(col_name):
    if "regex_hidden_groups" not in st.session_state:
        st.session_state.regex_hidden_groups = {}

    hidden = st.session_state.regex_hidden_groups.get(col_name)
    if not isinstance(hidden, list):
        hidden = []
    hidden.append(False)
    st.session_state.regex_hidden_groups[col_name] = hidden


def _mark_publication_year_modified():
    st.session_state["meta_publication_year_user_modified"] = True


def _parse_keywords(raw_keywords: str):
    """Parst Keyword-Text robust aus Komma/Semikolon/Zeilenumbruechen in eine Liste."""
    if not raw_keywords:
        return []

    normalized = raw_keywords.replace("\n", ",").replace(";", ",")
    return [k.strip() for k in normalized.split(",") if k.strip()]


def _normalize_exclusion_token(token: str):
    if not token:
        return None

    stripped = token.strip()
    if not stripped:
        return None

    lowered = stripped.lower()
    if stripped.startswith("!"):
        candidate = stripped[1:].strip()
        return candidate if candidate else None
    if lowered.startswith("not:"):
        candidate = stripped[4:].strip()
        return candidate if candidate else None
    if lowered.startswith("exclude:"):
        candidate = stripped[8:].strip()
        return candidate if candidate else None

    return None


def _split_keywords_by_polarity(keywords):
    include_seen = set()
    exclude_seen = set()
    include_terms = []
    exclude_terms = []

    for raw in keywords:
        token = str(raw).strip() if isinstance(raw, str) else ""
        if not token:
            continue

        exclusion = _normalize_exclusion_token(token)
        if exclusion is not None:
            key = exclusion.lower()
            if key in exclude_seen:
                continue
            exclude_seen.add(key)
            exclude_terms.append(exclusion)
            continue

        key = token.lower()
        if key in include_seen:
            continue
        include_seen.add(key)
        include_terms.append(token)

    return include_terms, exclude_terms


def _parse_float_optional(raw_value):
    if raw_value is None:
        return None
    text = str(raw_value).strip()
    if not text:
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _render_readme_section():
    """README-Hilfe in der Sidebar ohne Expander."""
    with st.sidebar:
        st.markdown("### README")
        st.markdown(
                        """
                        Quick start — first-time user guide

                        1) Define mappings (left tabs):
                             - `Entity Filtering`: Create classes (e.g. Battery, Photovoltaic)
                                - Grey Box: Add keywords that identify matching records. Use commas or new lines to enter multiple keywords.
                                - Red Box: Add keywords to exclude matches.
                             - `Property Filtering`: Create classes (e.g. Lifetime, Efficiency).
                                - Grey Box: Add keywords that identify matching records. Use commas or new lines to enter multiple keywords.                    
                                - Red Box: Add keywords to exclude matches.
                                - Add a Unit filter for each property for conversions. For currency units, Year is optional.

                        2) Filter metadata (Filters expander):
                             - Narrow the dataset by author origin, publication year, temporal or spatial scope,
                                 or numeric value range. Facets react to each other so the available options update
                                 based on your selections.

                        3) Explore results (main tabs):
                             - `Data`: paginated table of matched rows. Use "Rows per page" and the download
                                 controls to export filtered results.
                             - `Column Frequency`: frequency counts of mapped classes and keywords.
                             - `Temporal Plot` / `Spatial Plot`: visual summaries for time series and spatial data.
                        """
        )


def _ensure_property_aux_fields(groups):
    for field in PROPERTY_AUX_FIELDS:
        if field not in st.session_state.regex_groups:
            st.session_state.regex_groups[field] = [[""] * len(groups)]


def _ensure_property_aux_row(row_idx):
    for field in PROPERTY_AUX_FIELDS:
        if len(st.session_state.regex_groups[field]) <= row_idx:
            st.session_state.regex_groups[field].append([""])


def _delete_property_aux_row(row_idx):
    for field in PROPERTY_AUX_FIELDS:
        if field in st.session_state.regex_groups and len(st.session_state.regex_groups[field]) > row_idx:
            del st.session_state.regex_groups[field][row_idx]


def _add_property_aux_row():
    for field in PROPERTY_AUX_FIELDS:
        st.session_state.regex_groups[field].append([""])

# ----------------------------
# Unterfunktionen für einzelne Filter
# ----------------------------

def _render_mapping_filter(col_name):
    """
    Rendert den Sidebar-Filter für 'Entity' oder 'Property'.
    Bei 'Property' wird zusätzlich ein Unit-Input ermöglicht.
    """
    
    groups = st.session_state.regex_groups[col_name]
    new_groups = []
    active_groups = []

    _ensure_hidden_state(col_name, groups)
    hidden_flags = st.session_state.regex_hidden_groups.get(col_name, [False] * len(groups))

    # Unit-Filter vorbereiten, falls noch nicht existiert
    if col_name == "Property":
        _ensure_property_aux_fields(groups)

    if not groups:
        mapping_cards.render_mapping_empty_state(col_name)

    num_cols = 2 if len(groups) > 1 else 1
    grid_cols = st.columns(num_cols, gap="medium") if groups else []

    for row_idx, row in enumerate(groups):
        if len(row) < 2:
            row = ["", ""]
        master, variants = row[0], row[1:]

        target_col = grid_cols[row_idx % num_cols] if num_cols > 1 else grid_cols[0]

        with target_col:
            master_key = f"{col_name}_master_{row_idx}"
            keywords_key = f"{col_name}_keywords_{row_idx}"
            exclude_keywords_key = f"{col_name}_exclude_keywords_{row_idx}"

            if master_key not in st.session_state:
                st.session_state[master_key] = master

            include_variants, exclude_variants = _split_keywords_by_polarity(variants)
            keywords_string = ", ".join(include_variants)
            exclude_keywords_string = ", ".join(exclude_variants)
            if keywords_key not in st.session_state:
                st.session_state[keywords_key] = keywords_string
            if exclude_keywords_key not in st.session_state:
                st.session_state[exclude_keywords_key] = exclude_keywords_string

            live_master = st.session_state.get(master_key, master)
            is_hidden = bool(hidden_flags[row_idx]) if row_idx < len(hidden_flags) else False
            title_base = live_master.strip() if isinstance(live_master, str) and live_master.strip() else f"Class {row_idx + 1}"
            title = f"{title_base} (hidden)" if is_hidden else title_base
            with st.expander(title, expanded=(row_idx < 2)):
                with st.container(border=False):
                    new_master = st.text_input(
                        "Class label",
                        key=master_key,
                        placeholder="Enter class label",
                        icon=":material/topic:",
                    )

                    raw_keywords = st.text_area(
                        "Keywords",
                        key=keywords_key,
                        height=50,
                        placeholder="keyword 1, keyword 2, keyword 3",
                        label_visibility="collapsed",
                    )
                    new_variants = _parse_keywords(raw_keywords)
                    mapping_cards.render_keyword_chips(new_variants)

                    raw_exclude_keywords = st.text_area(
                        "Exclude Keywords",
                        key=exclude_keywords_key,
                        height=50,
                        placeholder="keyword that must not match",
                        help="Terms entered here are stored as !keyword and exclude matches for this class.",
                        label_visibility="collapsed",
                    )
                    new_exclude_variants = _parse_keywords(raw_exclude_keywords)
                    if new_exclude_variants:
                        mapping_cards.render_keyword_chips([f"!{k}" for k in new_exclude_variants])

                    if col_name == "Property":
                        _ensure_property_aux_row(row_idx)

                        unit_val = st.session_state.regex_groups["Unit"][row_idx][0]
                        year_val = st.session_state.regex_groups["Year"][row_idx][0]
                        unit_col, year_col = st.columns(2)

                        with unit_col:
                            unit_key = f"unit_{row_idx}"
                            if unit_key not in st.session_state:
                                st.session_state[unit_key] = unit_val
                            new_unit = st.text_input(
                                "Unit filter (unitless = no unit)",
                                key=unit_key,
                                placeholder="e.g. $/kWh or [-] (unitless)",
                                icon=":material/straighten:",
                            )
                            st.session_state.regex_groups["Unit"][row_idx][0] = new_unit

                        with year_col:
                            year_key = f"year_{row_idx}"
                            if year_key not in st.session_state:
                                st.session_state[year_key] = year_val
                            new_year = st.text_input(
                                "Year",
                                key=year_key,
                                placeholder="Optional for currency (fallback: Temporal Scope/ Publication Year)",
                                icon=":material/calendar_today:",
                            )
                            st.session_state.regex_groups["Year"][row_idx][0] = new_year

                    # Action buttons: place Hide/Unhide and Delete next to each other bottom-left
                    action_cols = st.columns([1, 3])
                    with action_cols[0]:
                        btns = st.columns([1, 1])
                        with btns[0]:
                            toggle_label = "Unhide class" if is_hidden else "Hide class"
                            if st.button(toggle_label, key=f"{col_name}_toggle_hidden_{row_idx}"):
                                hidden_flags[row_idx] = not is_hidden
                                st.session_state.regex_hidden_groups[col_name] = hidden_flags
                                st.rerun()
                        with btns[1]:
                            if st.button("Delete class", key=f"{col_name}_delrow_{row_idx}"):
                                del st.session_state.regex_groups[col_name][row_idx]
                                _delete_hidden_row(col_name, row_idx)
                                if col_name == "Property":
                                    _delete_property_aux_row(row_idx)
                                st.rerun()

                    # Datenstruktur unveraendert: [class_label, keyword1, keyword2, ...]
                    # Ausschluss-Keywords werden als !keyword serialisiert.
                    serialized_excludes = [f"!{k}" for k in new_exclude_variants]
                    all_terms = new_variants + serialized_excludes
                    serialized_row = [new_master] + (all_terms if all_terms else [""])
                    new_groups.append(serialized_row)
                    if not is_hidden:
                        active_groups.append(serialized_row)

    if st.button("+ Add class", key=f"{col_name}_addrow", use_container_width=True):
        st.session_state.regex_groups[col_name].append(["", ""])
        _add_hidden_row(col_name)
        if col_name == "Property":
            _add_property_aux_row()
        st.rerun()

    st.session_state.regex_groups[col_name] = new_groups

    visible_indices = [idx for idx, hidden in enumerate(hidden_flags) if not hidden]
    if col_name == "Property":
        st.session_state.property_visible_indices = visible_indices
    if col_name == "Entity":
        st.session_state.entity_visible_indices = visible_indices

    return active_groups


def _render_metadata_filters(facet_base_filters=None):
    """
    Rendert zusätzliche, datengetriebene Filter für Metadaten.
    """
    if "metadata_filters" not in st.session_state:
        st.session_state.metadata_filters = {
            "author_origin": [],
            "publication_year_range": None,
            "temporal_scope": [],
            "spatial_scope": [],
            "value_min": None,
            "value_max": None,
        }
    if "meta_publication_year_user_modified" not in st.session_state:
        st.session_state.meta_publication_year_user_modified = False
    if "meta_publication_year_last_bounds" not in st.session_state:
        st.session_state.meta_publication_year_last_bounds = None

    state = st.session_state.metadata_filters

    # Aktuelle Selektionen aus Widget-State lesen (falls vorhanden),
    # damit Facetten sofort gegenseitig reagieren.
    current_author_origin = st.session_state.get("meta_author_origin", state.get("author_origin", []))
    current_temporal_scope = st.session_state.get("meta_temporal_scope", state.get("temporal_scope", []))
    current_spatial_scope = st.session_state.get("meta_spatial_scope", state.get("spatial_scope", []))
    current_year_range = st.session_state.get("meta_publication_year", state.get("publication_year_range"))
    current_value_min = st.session_state.get("meta_value_min", state.get("value_min"))
    current_value_max = st.session_state.get("meta_value_max", state.get("value_max"))

    def _faceted_filters(exclude_key=None):
        filters = dict(facet_base_filters or {})

        if exclude_key != "author_origin" and current_author_origin:
            filters["__author_origin_values"] = current_author_origin
        if exclude_key != "temporal_scope" and current_temporal_scope:
            filters["__temporal_scope_values"] = current_temporal_scope
        if exclude_key != "spatial_scope" and current_spatial_scope:
            filters["__spatial_scope_values"] = current_spatial_scope
        if exclude_key != "publication_year_range" and current_year_range:
            filters["__publication_year_range"] = current_year_range

        return filters

    author_origin_options = duckdb_filter.get_author_origin_values(
        regex_filters=_faceted_filters(exclude_key="author_origin")
    )
    temporal_scope_options = duckdb_filter.get_scope_values(
        "Temporal Scope", regex_filters=_faceted_filters(exclude_key="temporal_scope")
    )
    spatial_scope_options = duckdb_filter.get_scope_values(
        "Spatial Scope", regex_filters=_faceted_filters(exclude_key="spatial_scope")
    )
    year_min, year_max = duckdb_filter.get_publication_year_bounds(
        regex_filters=_faceted_filters(exclude_key="publication_year_range")
    )

    selected_author_origin = st.multiselect(
        "Author Origin",
        options=author_origin_options,
        default=[v for v in current_author_origin if v in author_origin_options],
        placeholder="Select one or more countries",
        key="meta_author_origin",
    )

    if year_min is not None and year_max is not None:
        current_bounds = (int(year_min), int(year_max))
        last_bounds = st.session_state.get("meta_publication_year_last_bounds")
        user_modified = bool(st.session_state.get("meta_publication_year_user_modified", False))

        # Wenn sich die verfügbare Spanne ändert und der Slider nicht manuell gesetzt wurde,
        # auf volle Spanne zurücksetzen.
        if last_bounds != current_bounds and not user_modified:
            current_year_range = current_bounds

        default_range = current_year_range
        if (
            not default_range
            or len(default_range) != 2
            or default_range[0] < year_min
            or default_range[1] > year_max
        ):
            default_range = (year_min, year_max)

        if year_min == year_max:
            selected_year_range = (year_min, year_max)
            st.session_state.meta_publication_year_user_modified = False
            st.session_state.meta_publication_year = selected_year_range
            st.text_input(
                "Publication Year",
                value=str(year_min),
                disabled=True,
                help="Only one publication year is available for the current filter combination.",
            )
        else:
            selected_year_range = st.slider(
                "Publication Year",
                min_value=year_min,
                max_value=year_max,
                value=(int(default_range[0]), int(default_range[1])),
                key="meta_publication_year",
                on_change=_mark_publication_year_modified,
            )
        st.session_state.meta_publication_year_last_bounds = current_bounds
    else:
        selected_year_range = None
        st.info("No valid publication years available.")

    selected_temporal_scope = st.multiselect(
        "Temporal Scope",
        options=temporal_scope_options,
        default=[v for v in current_temporal_scope if v in temporal_scope_options],
        placeholder="Select one or more temporal scopes",
        key="meta_temporal_scope",
    )

    selected_spatial_scope = st.multiselect(
        "Spatial Scope",
        options=spatial_scope_options,
        default=[v for v in current_spatial_scope if v in spatial_scope_options],
        placeholder="Select one or more spatial scopes",
        key="meta_spatial_scope",
    )

    value_col_min, value_col_max = st.columns(2)
    with value_col_min:
        selected_value_min_raw = st.text_input(
            "Min value",
            value="" if current_value_min is None else str(current_value_min),
            key="meta_value_min",
            placeholder="e.g. 0",
        )
    with value_col_max:
        selected_value_max_raw = st.text_input(
            "Max value",
            value="" if current_value_max is None else str(current_value_max),
            key="meta_value_max",
            placeholder="e.g. 1000",
        )

    selected_value_min = _parse_float_optional(selected_value_min_raw)
    selected_value_max = _parse_float_optional(selected_value_max_raw)

    st.session_state.metadata_filters = {
        "author_origin": selected_author_origin,
        "publication_year_range": selected_year_range,
        "temporal_scope": selected_temporal_scope,
        "spatial_scope": selected_spatial_scope,
        "value_min": selected_value_min,
        "value_max": selected_value_max,
    }

    return {
        "__author_origin_values": selected_author_origin,
        "__publication_year_range": selected_year_range,
        "__temporal_scope_values": selected_temporal_scope,
        "__spatial_scope_values": selected_spatial_scope,
        "__value_min": selected_value_min,
        "__value_max": selected_value_max,
    }


# ----------------------------
# Hauptfunktion
# ----------------------------

def render_entity_filter():
    """Rendert nur den Entity-Filterbereich."""
    mapping_cards.inject_mapping_card_styles()
    return _render_mapping_filter("Entity")


def render_property_filter():
    """Rendert nur den Property-Filterbereich."""
    mapping_cards.inject_mapping_card_styles()
    return _render_mapping_filter("Property")


def render_metadata_filter(entity_groups, property_groups):
    """Rendert nur den Metadata-Filterbereich."""
    all_groups = {}

    facet_base_filters = duckdb_filter.flatten_regex_filters(
        {
            "Entity": entity_groups or [],
            "Property": property_groups or [],
        }
    )

    with st.expander("Filters", expanded=True):
        all_groups.update(_render_metadata_filters(facet_base_filters=facet_base_filters))

    return all_groups


def render_sidebar_readme():
    """Zeigt die README-Hilfe in der Sidebar."""
    _render_readme_section()