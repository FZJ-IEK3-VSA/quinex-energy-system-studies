import streamlit as st
import numpy as np
import ast


def is_missing_display_value(val):
    if val is None:
        return True

    if isinstance(val, str):
        return val.strip() == "<NA>"

    if getattr(type(val), "__name__", "") == "NAType":
        return True

    if isinstance(val, (float, np.floating)):
        return np.isnan(val)

    return False


def style_dataframe(df):
    highlight_cols = ['Entity Mapping', 'Property Mapping', 'Unit Mapping', 'Value Converted']

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
        except Exception:
            return None

    # Already dict → in Liste packen
    if isinstance(u, dict):
        return [u]

    # Something with to_list()
    if hasattr(u, "to_list"):
        try:
            return u.to_list()
        except Exception:
            pass

    # String case
    if isinstance(u, str):
        s = u.strip()
        if s.startswith("[") and s.endswith("]"):
            try:
                return ast.literal_eval(s)
            except Exception:
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


def format_list_column(val):
    if is_missing_display_value(val):
        return None

    if isinstance(val, (list, tuple, np.ndarray)):
        items = list(val) if isinstance(val, np.ndarray) else val
        return str(items)
    if isinstance(val, str):
        return val
    return str(val)


def format_references_column(val):
    if is_missing_display_value(val):
        return None

    if isinstance(val, str):
        s = val.strip()
        if s.startswith("["):
            try:
                val = ast.literal_eval(s)
            except Exception:
                return s
        else:
            return s

    if isinstance(val, dict):
        return str([val])

    if isinstance(val, (list, tuple)):
        return str(list(val))

    if isinstance(val, np.ndarray):
        try:
            return str(val.tolist())
        except Exception:
            return str(val)

    return str(val)


def format_units_for_display(df):
    df = df.copy()
    df["Unit Normalized"] = df["Unit Normalized"].apply(parse_unit_column)
    df["Unit Normalized"] = df["Unit Normalized"].apply(format_unit_list)
    return df


def render(df, rows_per_page):
    df = format_units_for_display(df)

    if "Associated Countries" in df.columns:
        df["Associated Countries"] = df["Associated Countries"].apply(format_list_column)
    if "Reference" in df.columns:
        df["Reference"] = df["Reference"].apply(format_references_column)

    # Build desired columns: place mapping columns directly after the raw columns
    desired_columns = [
        "DOI",
        "Source",
        "Publication Year",
        "Associated Countries",
        "License Information",
    ]

    # Entity + its mapping
    desired_columns.append("Entity")
    desired_columns.append("Entity Mapping")

    # Property + its mapping
    desired_columns.append("Property")
    desired_columns.append("Property Mapping")

    # Quantity, Value Normalized + Value Converted
    desired_columns.append("Quantity")
    desired_columns.append("Value Normalized")
    desired_columns.append("Value Converted")

    # Unit Normalized + Unit Mapping
    desired_columns.append("Unit Normalized")
    desired_columns.append("Unit Mapping")

    # Remaining contextual columns
    desired_columns.extend([
        "Quote",
        "Temporal Scope",
        "Spatial Scope",
        "Reference",
        "Method",
        "Qualifier",
    ])

    # nur die existierenden Spalten auswählen (vermeidet Fehler, falls eine fehlt)
    df = df[[col for col in desired_columns if col in df.columns]]

    st.dataframe(
        style_dataframe(df),
        height=rows_per_page * 40,
        width=2000
    )
