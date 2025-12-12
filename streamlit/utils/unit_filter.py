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
    - Fügt neue Spalten 'unit_converted' und 'unit_mapping' hinzu.
    - Entfernt Zeilen, bei denen unit_conversion nicht möglich ist.
    """
    df = df.copy()
    df["unit_converted"] = None
    df["unit_mapping"] = None

    # Unit-Filters nur anwenden, wenn vorhanden
    unit_filters = regex_mapping.get("unit", [])
    property_filters = regex_mapping.get("Property", [])

    if not unit_filters or all((not u[0].strip()) for u in unit_filters):
        return df


    filtered_rows = []

    for idx, (prop_row, unit_row) in enumerate(zip(property_filters, unit_filters)):
        prop_master = prop_row[0].strip()
        to_unit_str = unit_row[0].strip()

        if not prop_master or not to_unit_str:
            continue

        # Parse Target Unit
        try:
            to_unit = unit_parser.parse(to_unit_str)
        except Exception:
            continue

        # Filter Zeilen, die diese Property betreffen
        df_subset = df[df["Property Mapping"] == prop_master]

        for _, row in df_subset.iterrows():
            from_unit = row["Unit Normalized"]
            if not from_unit:
                continue
            try:
                unit_norm = normalize_unit_normalized(from_unit)
                if not unit_norm:
                    continue
                
                conv_value, conv_unit = unit_parser.unit_conversion(
                    value=row["Value Normalized"],
                    from_compound_unit=unit_norm,
                    to_compound_unit=to_unit
                )
                if conv_value is None:
                    continue

                row["unit_converted"] = conv_value
                row["unit_mapping"] = to_unit_str
                filtered_rows.append(row)
            except Exception:
                continue

    if filtered_rows:
        return pd.DataFrame(filtered_rows).reset_index(drop=True)
    else:
        return pd.DataFrame(columns=df.columns)
    

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
