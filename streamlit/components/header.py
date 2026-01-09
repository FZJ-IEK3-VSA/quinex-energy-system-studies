import streamlit as st


def render(logo_file):
    """Header mit Logo und Titel"""

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
        """,
        unsafe_allow_html=True
    )
    
    with open(logo_file, "r", encoding="utf-8") as f:
        svg_logo = f.read()

    col_logo, col_title = st.columns([1, 4])
    with col_logo:
        st.image(svg_logo)  # "stretch" funktioniert nicht direkt
    with col_title:
        st.title("Technoeconomic Data for Energy Technologies", anchor="TechnoeconomicData")
