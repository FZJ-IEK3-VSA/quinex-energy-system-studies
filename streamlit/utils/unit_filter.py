import ast
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
    Konvertiert Units auf dem bereits (per unit_dimension) gefilterten DataFrame.
    - Fügt neue Spalten 'Value Converted' und 'Unit Mapping' hinzu.
    - Entfernt KEINE Zeilen; Zeilen ohne erfolgreiche Konvertierung behalten None.
    - Die Dimensionsfilterung erfolgt bereits auf DB-Ebene (unit_dimension).
    """
    df = df.copy()
    df["Value Converted"] = None
    df["Unit Mapping"] = None

    # Unit-Filters nur anwenden, wenn vorhanden
    unit_filters = regex_mapping.get("Unit", [])
    property_filters = regex_mapping.get("Property", [])

    if not unit_filters or all((not u[0].strip()) for u in unit_filters):
        return df

    if df.empty:
        return df

    prop_to_unit = {}
    prop_to_year = {}
    year_filters = regex_mapping.get("Year", [])
    for i, (prop_row, unit_row) in enumerate(zip(property_filters, unit_filters)):
        prop = prop_row[0].strip() if prop_row and prop_row[0] else None
        unit = unit_row[0].strip() if unit_row and unit_row[0] else None
        if prop and unit:
            prop_to_unit[prop] = unit
            # Jahr aus Year-Filter extrahieren
            if i < len(year_filters) and year_filters[i][0].strip():
                try:
                    prop_to_year[prop] = int(year_filters[i][0].strip())
                except ValueError:
                    pass

    if not prop_to_unit:
        return df

    # Target Unit zuweisen (None für Zeilen ohne passendes Property Mapping)
    df["Target Unit"] = df["Property Mapping"].map(prop_to_unit)

    # Nur konvertierbare Zeilen identifizieren
    convertible_mask = (
        df["Target Unit"].notna()
        & df["Unit Normalized"].notna()
        & df["Value Normalized"].notna()
    )

    # Target Units parsen
    parsed_target_units = {}
    for u in df.loc[convertible_mask, "Target Unit"].unique():
        try:
            parsed_target_units[u] = unit_parser.parse(u)
        except Exception:
            parsed_target_units[u] = None

    def _extract_row_year(row):
        """Jahr aus Temporal Scope extrahieren, Fallback auf Publication Year."""
        temporal_scope = row.get("Temporal Scope")
        if temporal_scope is not None:
            if isinstance(temporal_scope, dict):
                y = temporal_scope.get("year")
                if y is not None:
                    return int(y)
            elif isinstance(temporal_scope, str):
                try:
                    y = ast.literal_eval(temporal_scope).get("year")
                    if y is not None:
                        return int(y)
                except Exception:
                    pass
        pub_year = row.get("Publication Year")
        if pub_year is not None and pd.notna(pub_year):
            return int(pub_year)
        return None

    def convert_row(row):
        target_str = row["Target Unit"]
        parsed_target = parsed_target_units.get(target_str)
        if parsed_target is None:
            return None, None
        try:
            from_unit = normalize_unit_normalized(row["Unit Normalized"])
            if not from_unit:
                return None, None

            from_default_year = _extract_row_year(row)
      
            prop_mapping = row.get("Property Mapping")
            to_default_year = prop_to_year.get(prop_mapping)

            val, conv_unit = unit_parser.unit_conversion(
                value=row["Value Normalized"],
                from_compound_unit=from_unit,
                to_compound_unit=parsed_target,
                from_default_year=from_default_year,
                to_default_year=to_default_year,
            )
            if val is None:
                print(f"[UNIT CONV FAILED] from={from_unit} → to={parsed_target} | from_year={from_default_year}, to_year={to_default_year} | returned: val={val}, unit={conv_unit}")
                print("-----------------------------------------------------")
            return val, target_str
        except Exception as e:
            print(f"[UNIT CONV ERROR] from={normalize_unit_normalized(row['Unit Normalized'])} → to={parsed_target} | from_year={_extract_row_year(row)}, to_year={prop_to_year.get(row.get('Property Mapping'))} | error: {e}")
            print("-----------------------------------------------------")
            return None, None

    # Konvertierung nur auf konvertierbaren Zeilen ausführen
    if convertible_mask.any():
        convertible_indices = df.loc[convertible_mask].index
        total = len(convertible_indices)
        converted_vals = [None] * total
        converted_units = [None] * total

        progress_bar = st.progress(0, text="Converting units...")
        for i, idx in enumerate(convertible_indices):
            row = df.loc[idx]
            val, unit = convert_row(row)
            converted_vals[i] = val
            converted_units[i] = unit
            progress_bar.progress((i + 1) / total, text=f"Converting units... ({i + 1}/{total})")
        progress_bar.empty()

        df.loc[convertible_mask, "Value Converted"] = converted_vals
        df.loc[convertible_mask, "Unit Mapping"] = converted_units

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

        year = item.get("year")
        if year is not None:
            year = int(year)

        uri = item.get("unit_uri") or ""

        # EUR-PER-KiloW und EUR-PER-W in zwei Bestandteile aufteilen
        if "EUR-PER-KiloW" in uri:
            converted.append(("€", 1.0, "http://qudt.org/vocab/unit/CCY_EUR", year))
            converted.append(("kW", -1.0, "http://qudt.org/vocab/unit/KiloW", year))
        elif "EUR-PER-W" in uri:
            converted.append(("€", 1.0, "http://qudt.org/vocab/unit/CCY_EUR", year))
            converted.append(("W", -1.0, "http://qudt.org/vocab/unit/W", year))
        else:
            converted.append((
                item.get("text"),
                float(item.get("exponent", 1.0)) if item.get("exponent") is not None else 1.0,
                uri or None,
                year,
            ))

    return converted
