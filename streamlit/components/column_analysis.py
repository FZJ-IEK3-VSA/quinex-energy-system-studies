import streamlit as st
import plotly.express as px
from utils import duckdb_filter

ALLOWED_COLUMNS = [
    "DOI",
    "Publication Year",
    "Entity",
    "Property",
    "Temporal Scope",
    "Spatial Scope",
    "Unit Normalized",
]


def _get_mapping_options(regex_mapping, col):
    """Extrahiert die verfügbaren Master-Labels aus dem Regex-Mapping."""
    options = []
    for row in regex_mapping.get(col, []):
        if row and row[0] and row[0].strip():
            options.append(row[0].strip())
    return options


def _get_variants_for_masters(regex_mapping, col, selected_masters):
    """Gibt alle Variants (inkl. Master) für die ausgewählten Master-Labels zurück."""
    variants = []
    for row in regex_mapping.get(col, []):
        if row and row[0] and row[0].strip() in selected_masters:
            for val in row:
                if val and val.strip():
                    token = val.strip()
                    if _is_exclusion_keyword(token):
                        continue
                    variants.append(token)
    return variants


def _get_class_groups_for_masters(regex_mapping, col, selected_masters):
    """Gibt die ausgewählten Klassen als include/exclude-Gruppen zurück."""
    selected = {m.strip() for m in selected_masters if isinstance(m, str) and m.strip()}
    groups = []
    for row in regex_mapping.get(col, []):
        if not row or not row[0]:
            continue
        master = row[0].strip()
        if master not in selected:
            continue

        include_seen = set()
        exclude_seen = set()
        include_tokens = []
        exclude_tokens = []
        for val in row:
            token = val.strip() if isinstance(val, str) else ""
            if not token:
                continue

            normalized_exclusion = _normalize_exclusion_token(token)
            if normalized_exclusion is not None:
                key = normalized_exclusion.lower()
                if key in exclude_seen:
                    continue
                exclude_seen.add(key)
                exclude_tokens.append(normalized_exclusion)
                continue

            key = token.lower()
            if key in include_seen:
                continue
            include_seen.add(key)
            include_tokens.append(token)

        if include_tokens:
            groups.append({
                "include": include_tokens,
                "exclude": exclude_tokens,
            })

    return groups


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


def _is_exclusion_keyword(token: str) -> bool:
    return _normalize_exclusion_token(token) is not None


def _value_counts_from_dataframe(df, selected_col, top_n):
    if selected_col not in df.columns:
        return None

    series = df[selected_col]
    if selected_col == "Unit Normalized":
        series = series.astype(str)

    counts = (
        series.dropna()
        .astype(str)
        .value_counts()
        .head(top_n)
        .rename_axis("value")
        .reset_index(name="count")
    )
    return counts


def render(regex_filters, regex_mapping=None, filtered_df_all=None):
    st.markdown("#### Column Frequency Analysis")
    st.caption("Select a column to see the most frequent values.")

    # --- Mapping-Filter ---
    if regex_mapping is None:
        regex_mapping = {}

    entity_options = _get_mapping_options(regex_mapping, "Entity")
    property_options = _get_mapping_options(regex_mapping, "Property")

    if entity_options or property_options:
        filter_cols = st.columns(2)
        with filter_cols[0]:
            selected_entities = st.multiselect(
                "Entity Mapping",
                options=entity_options,
                default=[],
                key="freq_entity_mapping",
            )
        with filter_cols[1]:
            selected_properties = st.multiselect(
                "Property Mapping",
                options=property_options,
                default=[],
                key="freq_property_mapping",
            )
    else:
        selected_entities = []
        selected_properties = []

    # Zusätzliche Filter aus Mapping-Auswahl aufbauen
    active_filters = dict(regex_filters) if regex_filters else {}
    if selected_entities:
        entity_variants = _get_variants_for_masters(regex_mapping, "Entity", selected_entities)
        active_filters["Entity"] = entity_variants
        entity_groups = _get_class_groups_for_masters(regex_mapping, "Entity", selected_entities)
        if entity_groups:
            active_filters["__entity_groups"] = entity_groups
    if selected_properties:
        property_variants = _get_variants_for_masters(regex_mapping, "Property", selected_properties)
        active_filters["Property"] = property_variants
        property_groups = _get_class_groups_for_masters(regex_mapping, "Property", selected_properties)
        if property_groups:
            active_filters["__property_groups"] = property_groups

    columns = [c for c in duckdb_filter.get_columns() if c in ALLOWED_COLUMNS]

    col1, col2 = st.columns([2, 1])
    with col1:
        selected_col = st.selectbox("Column", columns, key="freq_column")
    with col2:
        top_n = st.slider("Top N", min_value=5, max_value=50, value=15, step=5, key="freq_top_n")

    if selected_col:
        if filtered_df_all is not None:
            df_filtered = filtered_df_all.copy()

            if selected_entities and "Entity Mapping" in df_filtered.columns:
                df_filtered = df_filtered[df_filtered["Entity Mapping"].isin(selected_entities)]
            if selected_properties and "Property Mapping" in df_filtered.columns:
                df_filtered = df_filtered[df_filtered["Property Mapping"].isin(selected_properties)]

            df_counts = _value_counts_from_dataframe(df_filtered, selected_col, top_n)
            if df_counts is None:
                st.info("No data available for this column.")
                return
        else:
            df_counts = duckdb_filter.get_value_counts(selected_col, regex_filters=active_filters, top_n=top_n)

        if df_counts.empty:
            st.info("No data available for this column.")
            return

        # --- Bar Chart ---
        df_plot = df_counts.sort_values("count", ascending=True)

        fig = px.bar(
            df_plot,
            x="count",
            y="value",
            orientation="h",
            text="count",
            color="count",
            color_continuous_scale="Blues",
        )
        fig.update_layout(
            height=max(350, len(df_plot) * 28),
            margin=dict(l=10, r=10, t=10, b=10),
            xaxis_title="Count",
            yaxis_title="",
            coloraxis_showscale=False,
            font=dict(size=13),
        )
        fig.update_traces(
            textposition="outside",
            texttemplate="%{text:,}",
        )
        st.plotly_chart(fig, width='stretch')
