import streamlit as st

def render(logo_file):
    """Header mit Logo und Titel"""
    with open(logo_file, "r", encoding="utf-8") as f:
        svg_logo = f.read()

    col_logo, col_title = st.columns([1, 4])
    with col_logo:
        st.markdown(
            f'<div style="width:120px">{svg_logo}</div>',
            unsafe_allow_html=True
        )
    with col_title:
        st.title("Technoeconomic Data for Energy Technologies")
