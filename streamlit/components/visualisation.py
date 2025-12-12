import sys
import os
import io
import string
import streamlit as st
from utils import duckdb_filter, unit_filter

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__)))
sys.path.append(os.path.abspath(os.path.join(BASE_DIR, "..", "..")))

from quinex_application.quinex_visualisation import QuinexVisualisation  # Klasse mit den Plot-Funktionen

if 'vis' not in st.session_state:
    st.session_state.vis = QuinexVisualisation()

vis = st.session_state.vis


def prepare_df(regex_filters, regex_mapping, total_rows):
    df_all = duckdb_filter.get_page(regex_filters, limit=total_rows, offset=0)
    df_all = duckdb_filter.apply_master_mapping(df_all, regex_mapping)
    df_all = unit_filter.apply_unit_filters(df_all, regex_mapping)
    return df_all


def render_temporal(total_rows, regex_filters, regex_mapping):
    with st.expander("⚙️ Plot Settings"):
        # --- Form starten ---
        with st.form("temporal_plot_form", border=False):
            col1, col2 = st.columns(2)
            with col1:
                width = st.number_input("Figure width (inch)", min_value=2.0, max_value=16.0, value=12.0, step=0.5)
                technology_legend_x = st.number_input("Technology Legend X", min_value=0.0, max_value=1.0, value=0.96, step=0.01)
                size_legend_x = st.number_input("Size Legend X", min_value=0.0, max_value=1.0, value=0.96, step=0.01)
                point_size = st.number_input("Point Size", min_value=10.0, max_value=80.0, value=30.0, step=5.0)
            with col2:
                height = st.number_input("Figure height (inch)", min_value=1.0, max_value=10.0, value=6.0, step=0.5)
                technology_legend_y = st.number_input("Technology Legend Y", min_value=0.0, max_value=1.0, value=0.82, step=0.01)
                size_legend_y = st.number_input("Size Legend Y", min_value=0.0, max_value=1.0, value=0.5, step=0.01)
                font_size = st.number_input("Font Size", min_value=10.0, max_value=40.0, value=12.0, step=1.0)


            # --- Submit Button ---
            submitted = st.form_submit_button("Generate Plot", key="generate_plot_temporal")

    if submitted:
        df = prepare_df(regex_filters, regex_mapping, total_rows)

        # --- Automatische Erstellung von data_over_time ---
        alphabet_labels = list(string.ascii_lowercase)
        data_over_time = []
        for i, row in enumerate(regex_mapping["Property"]):
            prop_name = row[0]
            unit = regex_mapping["Unit"][i][0] if "Unit" in regex_mapping else ""
            df_prop = df[df["Property Mapping"] == prop_name]
            label_prefix = f"{alphabet_labels[i]}" if i < len(alphabet_labels) else f"{i+1}"
            if not df_prop.empty:
                data_over_time.append({
                    'df': df_prop,
                    'entity_col': 'Entity Mapping',
                    'value_col': 'Value Normalized',
                    'ylabel': f"{prop_name} [{unit}]",
                    'title': label_prefix
                })

        # --- Plot erzeugen ---
        fig = vis.plot_multiple_properties_over_time(
            data_list=data_over_time,
            legend_title='Technology Type',
            color_dict=vis.entity_colors,
            figsize=(width, height),
            legend_position=(technology_legend_x, technology_legend_y),
            legend_size_position=(size_legend_x, size_legend_y),
            central_tendency="moving average",
            error_type="se",
            error_display="shade",
            font_size=font_size,
            point_size_range=(point_size, point_size*4),
            temporal_col="Temporal Scope",
            publicationyear_col="Publication Year"
        )

        buf = io.StringIO()  # SVG ist Text
        fig.savefig(buf, format='svg', bbox_inches='tight')
        svg_data = buf.getvalue()
        with st.expander("📊 Plot", expanded=True):
            st.write(svg_data, unsafe_allow_html=True)

            # --- Download ---
            buf = io.BytesIO()
            fig.savefig(buf, format='pdf', bbox_inches='tight')
            buf.seek(0)
            st.download_button(
                "Download Plot as PDF", 
                data=buf, 
                file_name="temporal_plot.pdf", 
                mime="application/pdf",
                type="primary"
            )

def render_spatial(total_rows, regex_filters, regex_mapping):
    # --- Plot Optionen in Form ---
    with st.expander("⚙️ Settings"):
        with st.form("spatial_plot_form", border=False):
            col1, col2 = st.columns(2)
            with col1:
                width = st.number_input("Figure width (inch)", min_value=2.0, max_value=22.0, value=20.0, step=0.5)
                point_size = st.number_input("Point Size", min_value=10.0, max_value=80.0, value=40.0, step=5.0)
            with col2:
                height = st.number_input("Figure height (inch)", min_value=1.0, max_value=15.0, value=6.0, step=0.5)  
                font_size = st.number_input("Font Size", min_value=10.0, max_value=40.0, value=12.0, step=1.0)

            submitted = st.form_submit_button("Generate Spatial Plot")

    if submitted:
        import time
        
        # --- Daten vorbereiten ---
        df_all = prepare_df(regex_filters, regex_mapping, total_rows)
        df_all = vis.convert_spatial(df_all, spatial_col="Spatial Scope")

        fig_list = []
        tab_labels = []

        # --- Pro Property Mapping einen Plot erstellen ---
        for i, row in enumerate(regex_mapping["Property"]):
            prop_name = row[0]
            unit = regex_mapping["Unit"][i][0] if "Unit" in regex_mapping else ""
            df_prop = df_all[df_all["Property Mapping"] == prop_name]
            if df_prop.empty:
                continue

            # Liste der DataFrames pro Entity Mapping
            alphabet_labels = list(string.ascii_lowercase)
            data_list = []
            for idx, entity in enumerate(df_prop["Entity Mapping"].unique()):
                df_entity = df_prop[df_prop["Entity Mapping"] == entity]
                label_prefix = f"{alphabet_labels[idx]}) " if idx < len(alphabet_labels) else f"{idx+1}) "
                data_list.append({
                    "df": df_entity,
                    "value_column": "Value Normalized",
                    "title": f"{label_prefix}{entity}"
                })

            colorbar_title = f"{prop_name} [{unit}]"

            # --- Plot erzeugen ---
            fig = vis.plot_multiple_datasets_on_world(
                data_list,
                colorbar_title=colorbar_title,
                figsize=(width, height),
                jitter_strength=0,
                default_point_size=point_size,
                font_size=font_size
            )
            fig_list.append(fig)
            tab_labels.append(prop_name)

        with st.expander(f"🗺️ Plot", expanded=True):
            tabs = st.tabs(tab_labels)
            for tab, fig, label in zip(tabs, fig_list, tab_labels):
                with tab:
                    # SVG Ausgabe
                    buf_svg = io.StringIO()
                    fig.savefig(buf_svg, format="svg", bbox_inches="tight")
                    svg_data = buf_svg.getvalue()
                    st.write(svg_data, unsafe_allow_html=True)

                    # PDF Download
                    buf_pdf = io.BytesIO()
                    fig.savefig(buf_pdf, format="pdf", bbox_inches="tight")
                    buf_pdf.seek(0)
                    st.download_button(
                        f"Download {label} (PDF)",
                        data=buf_pdf,
                        file_name=f"{label.replace(')','').replace('(','')}_map.pdf",
                        mime="application/pdf",
                        type="primary"
                    )
