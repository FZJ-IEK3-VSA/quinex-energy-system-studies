import streamlit as st

def add_textinput_style():
    st.markdown("""
        <style>
        .stTextInput > div > div > input {
            border: 2px solid #337AB7 !important;
            border-radius: 8px !important;
            padding: 6px 10px !important;
            background-color: #ffffffff !important;
            color: #333 !important;
        }
        </style>
    """, unsafe_allow_html=True)

def set_vertical_alignment():
    st.markdown("""
        <style>
        div.stButton > button {
            display: flex;
            align-items: center;
            justify-content: center;
            height: 2.3em !important;
            padding: 0 6px !important;
            margin-top: 1 !important;
        }
        .stTextInput > div > div > input {
            height: 2.3em !important;
            padding: 6px 10px !important;
        }
        </style>
    """, unsafe_allow_html=True)

def set_warning_color():
    st.markdown("""
        <style>
        div.stAlert[data-testid="stAlert"] > div:first-child {
            background-color: #cce5ff !important;
            color: #333 !important;
            border-left: 5px solid #337AB7 !important;
            border-radius: 8px;
            padding: 10px;
        }
        </style>
    """, unsafe_allow_html=True)

def add_form_input_border():
    st.markdown("""
        <style>
        /* Number inputs: border on the outermost wrapper */
        [data-testid="stNumberInput"] > div {
            border: 2px solid #337AB7 !important;
            border-radius: 8px !important;
            overflow: hidden;
        }
        /* Kill ALL inner borders, outlines, shadows inside number input */
        [data-testid="stNumberInput"] > div > div,
        [data-testid="stNumberInput"] > div > div > div,
        [data-testid="stNumberInput"] input,
        [data-testid="stNumberInput"] button {
            border: none !important;
            border-radius: 0 !important;
            box-shadow: none !important;
            outline: none !important;
        }
        /* Select boxes */
        [data-testid="stSelectbox"] > div > div {
            border: 2px solid #337AB7 !important;
            border-radius: 8px !important;
        }
        .stSelectbox > div > div {
            border: 2px solid #337AB7 !important;
            border-radius: 8px !important;
        }
        /* Multiselect */
        [data-testid="stMultiSelect"] > div > div {
            border: 2px solid #337AB7 !important;
            border-radius: 8px !important;
        }
        .stMultiSelect > div > div {
            border: 2px solid #337AB7 !important;
            border-radius: 8px !important;
        }
        /* Text inputs inside forms */
        [data-testid="stTextInput"] input {
            border: 2px solid #337AB7 !important;
            border-radius: 8px !important;
        }
        </style>
    """, unsafe_allow_html=True)
