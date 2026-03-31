import sys
import os
import io
import string
import math
import streamlit as st
from utils import duckdb_filter, unit_filter

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__)))
sys.path.append(os.path.abspath(os.path.join(BASE_DIR, "..", "..")))


from quinex_application.visualisation.quinex_visualisation import QuinexVisualisation  # Klasse mit den Plot-Funktionen

if 'vis' not in st.session_state:
    st.session_state.vis = QuinexVisualisation()

vis = st.session_state.vis

CONTINENT_OPTIONS = ["World", "Europe", "Asia", "North America", "South America", "Africa", "Oceania"]


def prepare_df(regex_filters, regex_mapping, total_rows):
    df_all = duckdb_filter.get_page(regex_filters, limit=total_rows, offset=0)
    df_all = duckdb_filter.apply_master_mapping(df_all, regex_mapping)
    df_all = unit_filter.apply_unit_filters(df_all, regex_mapping)
    return df_all



# =========================================================================
# Temporal Plots
# =========================================================================

def _auto_temporal_figsize(n_plots):
    """Compute (width, height) based on number of subplots."""
    if n_plots <= 1:
        return (6, 3)
    if n_plots == 2:
        return (12, 3)
    nrows = math.ceil(n_plots / 2)
    return (12, nrows * 3)


def _auto_temporal_style(n_plots):
    """Return (font_size, point_size_min, point_size_max) based on number of subplots."""
    if n_plots <= 2:
        return 12, 60, 180
    if n_plots <= 4:
        return 14, 90, 270
    if n_plots <= 6:
        return 16, 120, 360
    return 9, 20, 80


def render_temporal(total_rows, regex_filters, regex_mapping):
    with st.expander("⚙️ Settings"):
        with st.form("temporal_plot_form", border=False):
            st.markdown("##### Subplot Settings")

            # Build property labels for per-subplot inputs
            subplot_labels = []
            for i, row in enumerate(regex_mapping["Property"]):
                prop_name = row[0]
                unit = regex_mapping["Unit"][i][0] if "Unit" in regex_mapping else ""
                alphabet_labels = list(string.ascii_lowercase)
                label_prefix = alphabet_labels[i] if i < len(alphabet_labels) else str(i + 1)
                subplot_labels.append((label_prefix, prop_name, unit))

            range_inputs = {}
            per_subplot_settings = {}
            for i, (label_prefix, prop_name, unit) in enumerate(subplot_labels):
                st.markdown(f"**{label_prefix})** {prop_name} [{unit}]")
                r1, r2, r3, r4 = st.columns(4)
                with r1:
                    y_min_str = st.text_input("Y min", value="", key=f"temp_ymin_{i}", placeholder="auto")
                with r2:
                    y_max_str = st.text_input("Y max", value="", key=f"temp_ymax_{i}", placeholder="auto")
                with r3:
                    yr_min_str = st.text_input("Year min", value="", key=f"temp_xmin_{i}", placeholder="auto")
                with r4:
                    yr_max_str = st.text_input("Year max", value="", key=f"temp_xmax_{i}", placeholder="auto")
                range_inputs[i] = (y_min_str, y_max_str, yr_min_str, yr_max_str)

                s1, s2, s3 = st.columns(3)
                with s1:
                    sp_xticks = st.number_input("Year-Tick Interval", min_value=1, max_value=20, value=5, step=1, key=f"temp_sp_xticks_{i}")
                with s2:
                    sp_min_dp = st.number_input("Min Datapoints", min_value=0, max_value=100, value=3, step=1, key=f"temp_sp_mindp_{i}")
                with s3:
                    sp_min_papers = st.number_input("Min Papers", min_value=0, max_value=100, value=3, step=1, key=f"temp_sp_minpap_{i}")
                per_subplot_settings[i] = (sp_xticks, sp_min_dp, sp_min_papers)

            submitted = st.form_submit_button("Generate Plot", type="primary")

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
                df_prop = df_prop[df_prop["Value Converted"].notna()]
                if df_prop.empty:
                    continue
                entry = {
                    'df': df_prop,
                    'entity_col': 'Entity Mapping',
                    'value_col': 'Value Converted',
                    'ylabel': f"{prop_name} [{unit}]",
                    'title': label_prefix
                }
                # Apply user-specified ranges
                if i in range_inputs:
                    y_min_s, y_max_s, yr_min_s, yr_max_s = range_inputs[i]
                    if y_min_s.strip() and y_max_s.strip():
                        try:
                            entry['y_range'] = (float(y_min_s), float(y_max_s))
                        except ValueError:
                            pass
                    if yr_min_s.strip() and yr_max_s.strip():
                        try:
                            entry['year_range'] = (int(yr_min_s), int(yr_max_s))
                        except ValueError:
                            pass
                # Apply per-subplot settings
                if i in per_subplot_settings:
                    sp_xticks_v, sp_min_dp_v, sp_min_pap_v = per_subplot_settings[i]
                    entry['number_xticks'] = sp_xticks_v
                    entry['min_datapoints_per_year'] = sp_min_dp_v
                    entry['min_papers_per_year'] = None if sp_min_pap_v == 0 else sp_min_pap_v
                data_over_time.append(entry)

        if not data_over_time:
            st.warning("No data available for plotting. Check your filters and unit conversion.")
            return

        # --- Auto figsize & style ---
        n = len(data_over_time)
        figsize = _auto_temporal_figsize(n)
        font_size, ps_min, ps_max = _auto_temporal_style(n)

        # --- Plot erzeugen ---
        fig, data_tables = vis.plot_multiple_properties_over_time(
            data_list=data_over_time,
            legend_title='Technology Type',
            figsize=figsize,
            legend_position=(0.3, 0),
            legend_size_position=(0.7, 0),
            font_size=font_size,
            number_xticks=5,
            point_size_range=(ps_min, ps_max),
            temporal_col="Temporal Scope",
            publicationyear_col="Publication Year",
            min_datapoints_per_year=5,
            min_papers_per_year=None,
        )

        # Cache SVG and PDF in session_state
        buf_svg = io.StringIO()
        fig.savefig(buf_svg, format='svg', bbox_inches='tight')
        buf_pdf = io.BytesIO()
        fig.savefig(buf_pdf, format='pdf', bbox_inches='tight')
        buf_pdf.seek(0)
        st.session_state['temporal_plot_svg'] = buf_svg.getvalue()
        st.session_state['temporal_plot_pdf'] = buf_pdf.getvalue()

    # Always render from session_state if available
    if 'temporal_plot_svg' in st.session_state:
        with st.expander("📊 Plot", expanded=True):
            st.write(st.session_state['temporal_plot_svg'], unsafe_allow_html=True)

            st.download_button(
                "Download Plot as PDF",
                data=st.session_state['temporal_plot_pdf'],
                file_name="temporal_plot.pdf",
                mime="application/pdf",
                type="primary"
            )



# =========================================================================
# Spatial Plots
# =========================================================================


def _auto_spatial_figsize(n_plots):
    """Compute (width, height) based on number of spatial subplots."""
    if n_plots <= 1:
        return (10, 6)
    if n_plots == 2:
        return (20, 6)
    nrows = math.ceil(n_plots / 2)
    return (20, nrows * 6)


def _auto_spatial_style(n_plots):
    """Return (font_size, default_point_size) based on number of spatial subplots."""
    if n_plots <= 2:
        return 12.0, 40.0
    if n_plots <= 4:
        return 14.0, 50.0
    if n_plots <= 6:
        return 16.0, 60.0
    return 10.0, 30.0


def render_spatial(total_rows, regex_filters, regex_mapping):
    with st.expander("⚙️ Settings"):
        with st.form("spatial_plot_form", border=False):
            st.markdown("##### Subplot Settings")

            # Build property labels
            subplot_labels = []
            for i, row in enumerate(regex_mapping["Property"]):
                prop_name = row[0]
                unit = regex_mapping["Unit"][i][0] if "Unit" in regex_mapping else ""
                alphabet_labels = list(string.ascii_lowercase)
                label_prefix = alphabet_labels[i] if i < len(alphabet_labels) else str(i + 1)
                subplot_labels.append((label_prefix, prop_name, unit))

            spatial_subplot_settings = {}
            for i, (label_prefix, prop_name, unit) in enumerate(subplot_labels):
                st.markdown(f"**{label_prefix})** {prop_name} [{unit}]")
                c1, c2 = st.columns(2)
                with c1:
                    plot_mode = st.selectbox(
                        "Plot Mode", options=["points", "choropleth"], index=0, key=f"sp_mode_{i}"
                    )
                with c2:
                    continent = st.selectbox(
                        "Continent", options=CONTINENT_OPTIONS, index=0, key=f"sp_cont_{i}"
                    )
                spatial_subplot_settings[i] = {
                    'plot_mode': plot_mode,
                    'continent': continent,
                }

            submitted = st.form_submit_button("Generate Spatial Plot", type="primary")

    if submitted:
        # --- Daten vorbereiten ---
        df_all = prepare_df(regex_filters, regex_mapping, total_rows)
        df_all = vis.convert_spatial(df_all, spatial_col="Spatial Scope")

        spatial_plots = []  # list of (label, svg_str, pdf_bytes)

        # --- Pro Property Mapping einen Plot erstellen ---
        for i, row in enumerate(regex_mapping["Property"]):
            prop_name = row[0]
            unit = regex_mapping["Unit"][i][0] if "Unit" in regex_mapping else ""
            df_prop = df_all[df_all["Property Mapping"] == prop_name]
            if df_prop.empty:
                continue

            settings = spatial_subplot_settings.get(i, {})
            sp_plot_mode = settings.get('plot_mode', 'points')
            sp_continent = settings.get('continent', None)

            alphabet_labels = list(string.ascii_lowercase)
            data_list = []
            for idx, entity in enumerate(df_prop["Entity Mapping"].unique()):
                df_entity = df_prop[df_prop["Entity Mapping"] == entity]
                label_prefix = f"{alphabet_labels[idx]}) " if idx < len(alphabet_labels) else f"{idx+1}) "
                data_list.append({
                    "df": df_entity,
                    "value_column": "Value Converted",
                    "title": f"{label_prefix}{entity}",
                    "plot_mode": sp_plot_mode,
                })

            colorbar_title = f"{prop_name} [{unit}]"

            # Auto figsize & style
            n = len(data_list)
            figsize = _auto_spatial_figsize(n)
            font_size, default_point_size = _auto_spatial_style(n)

            # --- Plot erzeugen ---
            fig, _ = vis.plot_multiple_datasets_on_world(
                data_list,
                colorbar_title=colorbar_title,
                figsize=figsize,
                jitter_strength=0.0,
                default_point_size=default_point_size,
                cmap="viridis",
                font_size=font_size,
                log_scale=False,
                apply_iqr=True,
                continent=sp_continent,
            )

            buf_svg = io.StringIO()
            fig.savefig(buf_svg, format="svg", bbox_inches="tight")
            buf_pdf = io.BytesIO()
            fig.savefig(buf_pdf, format="pdf", bbox_inches="tight")
            buf_pdf.seek(0)
            spatial_plots.append((prop_name, buf_svg.getvalue(), buf_pdf.getvalue()))

        # Cache in session_state
        st.session_state['spatial_plots'] = spatial_plots

    # Always render from session_state if available
    if 'spatial_plots' in st.session_state and st.session_state['spatial_plots']:
        spatial_plots = st.session_state['spatial_plots']
        with st.expander(f"🗺️ Plot", expanded=True):
            tab_labels = [p[0] for p in spatial_plots]
            tabs = st.tabs(tab_labels)
            for tab, (label, svg_data, pdf_data) in zip(tabs, spatial_plots):
                with tab:
                    st.write(svg_data, unsafe_allow_html=True)

                    st.download_button(
                        f"Download {label} (PDF)",
                        data=pdf_data,
                        file_name=f"{label.replace(')','').replace('(','')}_map.pdf",
                        mime="application/pdf",
                        type="primary"
                    )
