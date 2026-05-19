import streamlit as st


def render(logo_file):
    """Header mit Sidebar-Logo und Titel."""

    # --- CSS einfügen, um oberen Abstand zu reduzieren ---
    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 0.5rem;
            padding-bottom: 1rem;
            padding-left: 2rem;
            padding-right: 2rem;
        }
        section[data-testid="stSidebar"] {
            background-color: #eef3f8 !important;
        }
        section[data-testid="stSidebar"] > div:first-child {
            background-color: #eef3f8 !important;
        }
        div[data-testid="stSidebarContent"] {
            background-color: #eef3f8 !important;
        }
        [data-testid="stSidebar"] .sidebar-logo-spacer {
            margin-top: 0.35rem;
            margin-bottom: 0.55rem;
        }
        [data-testid="stSidebar"] [data-testid="stImage"] {
            padding-right: 0.4rem;
            padding-bottom: 0.4rem;
            overflow: visible !important;
        }
        [data-testid="stSidebar"] [data-testid="stImage"] img {
            display: block;
            margin: 0 auto;
            width: 100% !important;
            max-width: 188px !important;
            height: auto !important;
            object-fit: contain;
            overflow: visible !important;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    with st.sidebar:
        st.markdown('<div class="sidebar-logo-spacer"></div>', unsafe_allow_html=True)
        _, center_col, _ = st.columns([1, 4, 1])
        with center_col:
            st.image(logo_file, width=200)

    st.title("Techno-economic Data for Energy Systems Analysis", anchor="TechnoeconomicData")
