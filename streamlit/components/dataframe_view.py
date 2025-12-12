import streamlit as st
import numpy as np
import ast


def style_dataframe(df):
    highlight_cols = ['Entity Mapping', 'Property Mapping']

    def highlight_cell(val):
        if val:
            return 'background-color: #cce5ff; font-weight: bold'
        return ''

    styler = df.style
    for col in highlight_cols:
        if col in df.columns:
            styler = styler.map(highlight_cell, subset=[col])
    return styler.set_properties(**{
        'text-align': 'left',
        'max-width': '200px',
        'overflow-wrap': 'break-word',
        'font-family': 'sans-serif'
    })


def parse_unit_column(u):
    # Already list-like?
    if isinstance(u, (list, tuple)):
        return u

    # Numpy array → Liste machen
    if isinstance(u, np.ndarray):
        try:
            return u.tolist()
        except:
            return None

    # Already dict → in Liste packen
    if isinstance(u, dict):
        return [u]

    # Something with to_list()
    if hasattr(u, "to_list"):
        try:
            return u.to_list()
        except:
            pass

    # String case
    if isinstance(u, str):
        s = u.strip()
        if s.startswith("[") and s.endswith("]"):
            try:
                return ast.literal_eval(s)
            except:
                return None

    return None


def format_unit_list(u):
    if not isinstance(u, (list, tuple)):
        return ""

    parts = []
    for item in u:
        if isinstance(item, dict):
            sym = item.get("text")
            exp = item.get("exponent")
        else:
            continue

        if sym is None:
            continue

        if exp in (None, 1, 1.0):
            parts.append(f"{sym}")
        else:
            parts.append(f"{sym}^{exp}")

    return " * ".join(parts)


def format_units_for_display(df):
    df = df.copy()
    df["Unit Normalized"] = df["Unit Normalized"].apply(parse_unit_column)
    df["Unit Normalized"] = df["Unit Normalized"].apply(format_unit_list)
    return df


def render(df, rows_per_page):
    df = format_units_for_display(df)

    desired_columns = [
        "DOI",
        "Publication Year",
        "Entity",
        "Property",
        "Quantity Text",
        "Value Normalized",
        "Unit Normalized",
        "Quote",
        "Temporal Scope",
        "Spatial Scope",
        "Entity Mapping",
        "Property Mapping"
    ]

    # nur die existierenden Spalten auswählen (vermeidet Fehler, falls eine fehlt)
    df = df[[col for col in desired_columns if col in df.columns]]

    st.dataframe(
        style_dataframe(df),
        height=rows_per_page * 40,
        width=2000
    )
