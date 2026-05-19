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
                    variants.append(val.strip())
    return variants


def render(regex_filters, regex_mapping=None):
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
    if selected_properties:
        property_variants = _get_variants_for_masters(regex_mapping, "Property", selected_properties)
        active_filters["Property"] = property_variants

    columns = [c for c in duckdb_filter.get_columns() if c in ALLOWED_COLUMNS]

    col1, col2 = st.columns([2, 1])
    with col1:
        selected_col = st.selectbox("Column", columns, key="freq_column")
    with col2:
        top_n = st.slider("Top N", min_value=5, max_value=50, value=15, step=5, key="freq_top_n")

    if selected_col:
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
