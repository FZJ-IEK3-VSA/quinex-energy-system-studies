import io
import math
import streamlit as st
from utils import duckdb_filter

MAX_DOWNLOAD_ROWS = 100_000


def _get_total_pages(total_rows, rows_per_page):
    return max(1, math.ceil(total_rows / rows_per_page))

def prepare_csv(regex_filters, regex_mapping, total_rows):
    df_all = duckdb_filter.get_page(regex_filters, limit=total_rows, offset=0)
    df_all = duckdb_filter.apply_master_mapping(df_all, regex_mapping)
    csv_buffer = io.StringIO()
    df_all.to_csv(csv_buffer, index=False)
    st.session_state.download_csv = csv_buffer.getvalue()

def pagination_ui(total_rows, rows_per_page):
    if 'page' not in st.session_state:
        st.session_state.page = 1

    total_pages = _get_total_pages(total_rows, rows_per_page)

    col1, col2 = st.columns(2, width=200)

    # Buttons: Wenn gedrückt, direkt im Session State verändern
    if col1.button("<< Previous", key="prev_page"):
        st.session_state.page = max(1, st.session_state.page - 1)
        st.rerun() # Seite direkt neu laden

    if col2.button("Next >>", key="next_page"): 
        st.session_state.page = min(total_pages, st.session_state.page + 1)
        st.rerun() # Seite direkt neu laden

    return st.session_state.page

def render(total_rows, rows_per_page, regex_filters, regex_mapping):
    if 'download_csv' not in st.session_state:
        st.session_state.download_csv = None

    with st.container():
        col_info, col_pagination, col_download = st.columns([2, 3, 2], gap="medium")

        # Matches & Page Info
        with col_info:
            st.markdown(
                f"**Matches:** {total_rows:,}  |  "
                f"**Page:** {st.session_state.page} / {_get_total_pages(total_rows, rows_per_page)}"
            )

        # Pagination
        with col_pagination:
            st.session_state.page = pagination_ui(total_rows, rows_per_page)

        # Prepare Download & Download Button nebeneinander
        with col_download:
            if total_rows <= MAX_DOWNLOAD_ROWS:
                col_prepare, col_download_btn = st.columns([1, 1], gap="small")

                with col_prepare:
                    if st.button("Prepare Download", type="primary"):
                        prepare_csv(regex_filters, regex_mapping, total_rows)

                with col_download_btn:
                    if st.session_state.download_csv:
                        st.download_button(
                            label="Download all",
                            data=st.session_state.download_csv,
                            file_name="filtered_data.csv",
                            mime="text/csv",
                            type="primary"
                        )
            else:
                st.warning("Download disabled: too many rows. Please filter.")
