import builtins
import numpy as np
import streamlit as st
import pandas as pd
from quinex_utils.parsers.unit_parser import FastSymbolicUnitParser

# Monkeypatch open innerhalb quinex_utils, um UTF-8 zu erzwingen
_open = builtins.open
def open_utf8(file, mode='r', *args, **kwargs):
    if 'b' not in mode:  # nur textmodus
        kwargs.setdefault('encoding', 'utf-8')
    return _open(file, mode, *args, **kwargs)

builtins.open = open_utf8

if 'unit_parser' not in st.session_state:
    st.session_state.unit_parser = FastSymbolicUnitParser()

unit_parser = st.session_state.unit_parser

def apply_unit_filters(df: pd.DataFrame, regex_mapping: dict) -> pd.DataFrame:
    """
    Filtert Zeilen des DataFrames nach Unit, basierend auf Property Mapping.
    - Fügt neue Spalten 'Value Converted' und 'Unit Mapping' hinzu.
    - Entfernt Zeilen, bei denen unit_conversion nicht möglich ist.
    """
    df = df.copy()
    df["Value Converted"] = None
    df["Unit Mapping"] = None

    # Unit-Filters nur anwenden, wenn vorhanden
    unit_filters = regex_mapping.get("Unit", [])
    property_filters = regex_mapping.get("Property", [])

    if not unit_filters or all((not u[0].strip()) for u in unit_filters):
        return df


    prop_to_unit = {}
    for prop_row, unit_row in zip(property_filters, unit_filters):
        prop = prop_row[0].strip() if prop_row and prop_row[0] else None
        unit = unit_row[0].strip() if unit_row and unit_row[0] else None
        if prop and unit:
            prop_to_unit[prop] = unit

    if not prop_to_unit:
        return df
    
    df = df[df["Property Mapping"].isin(prop_to_unit.keys())].copy()
    df["Target Unit"] = df["Property Mapping"].map(prop_to_unit)

    df = df[
        df["Unit Normalized"].notna()
        & df["Value Normalized"].notna()
    ].copy()

    parsed_target_units = {}
    for u in df["Target Unit"].unique():
        try:
            parsed_target_units[u] = unit_parser.parse(u)
        except Exception:
            parsed_target_units[u] = None

    df["Parsed Target Unit"] = df["Target Unit"].map(parsed_target_units)

    df = df[df["Parsed Target Unit"].notna()].copy()

    def convert_row(row):
        try:
            from_unit = normalize_unit_normalized(row["Unit Normalized"])
            if not from_unit:
                return None, None

            val, _ = unit_parser.unit_conversion(
                value=row["Value Normalized"],
                from_compound_unit=from_unit,
                to_compound_unit=row["Parsed Target Unit"],
            )
            return val, row["Target Unit"]
        except Exception:
            return None, None
    
    converted = df.apply(convert_row, axis=1, result_type="expand")
    df["Value Converted"] = converted[0]
    df["Unit Mapping"] = converted[1]

    df = df[df["Value Converted"].notna()].copy()

    return df.reset_index(drop=True)


def normalize_unit_normalized(unit_norm):
    """
    Erwartet: [{'exponent': 1.0, 'text': 'years', ...}]
    oder numpy.ndarray mit denselben Einträgen.
    Gibt zurück: [('years', 1.0, 'http://.../YR', None)]
    """

    # Falls None oder leer
    if unit_norm is None:
        return None

    # numpy array → in Python-Liste konvertieren
    if isinstance(unit_norm, np.ndarray):
        unit_norm = unit_norm.tolist()

    # Muss jetzt Liste sein
    if not isinstance(unit_norm, list):
        return None

    converted = []
    for item in unit_norm:
        if not isinstance(item, dict):
            return None

        converted.append((
            item.get("text"),
            float(item.get("exponent", 1.0)) if item.get("exponent") is not None else 1.0,
            item.get("unit_uri"),
            item.get("year")
        ))

    return converted
