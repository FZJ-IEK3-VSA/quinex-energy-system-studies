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
