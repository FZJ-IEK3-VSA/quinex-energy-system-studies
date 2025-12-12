import os
import re
import builtins
import duckdb
import streamlit as st
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

# Basis-Pfad eine Ebene über streamlit/
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PARQUET_FILE = os.path.join(BASE_DIR, "data", "quinex", "df_quinex_adapted.parquet")
DB_FILE = os.path.join(BASE_DIR, "streamlit", "duckdb_data", "data.duckdb")

# Ordner sicherstellen
os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)

# Prüfen, ob DB-Datei existiert
db_exists = os.path.exists(DB_FILE)

# DuckDB Verbindung
con = duckdb.connect(DB_FILE)

# Tabelle nur einmal erstellen, falls DB neu ist
if not db_exists:
    print(f"DB-Datei existiert nicht. Erstelle DB und lade Parquet: {PARQUET_FILE}")
    con.execute("""
    CREATE TABLE data AS
    SELECT * FROM parquet_scan(?)
    """, (PARQUET_FILE,))
else:
    print(f"DB-Datei existiert. Verwende bestehende DB: {DB_FILE}")


def build_where_clause(regex_filters=None):
    """
    regex_filters: dict, z.B.
    {
        "Entity": ["offshore wind", "onshore wind"],
        "Property": ["capacity"]
    }
    """

    if not regex_filters:
        return ""

    clauses = []

    for col, patterns in regex_filters.items():
        if not patterns:
            continue

        if col == "unit_dimension":
            # exakte Dimension — kein Regex
            dim_clauses = [f"unit_dimension = '{d}'" for d in patterns]
            clauses.append("(" + " OR ".join(dim_clauses) + ")")
        else:
            # Regex wie bisher
            transformed = []
            for p in patterns:
                safe_p = re.escape(p)
                transformed.append(f"(?i).*{safe_p}.*")
            combined = "|".join(transformed)
            clauses.append(f"{col} ~ '{combined}'")


    if clauses:
        return "WHERE " + " AND ".join(clauses)

    return ""


def get_total_rows(regex_filters=None):
    where_clause = build_where_clause(regex_filters)
    query = f"SELECT COUNT(*) FROM data {where_clause}"
    return con.execute(query).fetchone()[0]


def get_page(regex_filters=None, limit=100, offset=0):
    where_clause = build_where_clause(regex_filters)
    query = f"""
        SELECT *
        FROM data
        {where_clause}
        LIMIT {limit}
        OFFSET {offset}
    """
    return con.execute(query).df()


# def flatten_regex_filters(mapping_dict):
#     """
#     mapping_dict: output von regex_mapping_ui()
#     Rückgabe: dict mit flachen Listen pro Spalte für DuckDB
#     Nur Variants werden übernommen, Master ausgeschlossen.
#     """
#     flat = {}
#     for col, groups in mapping_dict.items():
#         lst = []
#         for row in groups:
#             # Master ist row[0], nur row[1:] filtern
#             for val in row[1:]:
#                 if val:
#                     lst.append(val)
#         flat[col] = lst
#     return flat

def flatten_regex_filters(mapping_dict):
    """
    mapping_dict enthält Entity / Property / Unit.
    Unit-Strings werden hier in Dimensionen konvertiert.
    """
    flat = {}
    
    # --- Entity & Property wie immer ---
    for col, groups in mapping_dict.items():
        if col == "Unit":
            continue  # später separat

        lst = []
        for row in groups:
            for val in row[1:]:  # nur Variants
                if val:
                    lst.append(val)
        flat[col] = lst

    # --- Unit: Dimensionen erzeugen ---
    if "Unit" in mapping_dict:
        dim_list = []
        for row in mapping_dict["Unit"]:
            unit_str = row[0]  # nur 1 Feld pro Zeile
            dim = unit_string_to_dimension(unit_str)
            if dim:
                dim_list.append(dim)

        flat["unit_dimension"] = dim_list

    return flat




def apply_master_mapping(df, mapping_dict):
    """
    df: DataFrame mit 'Entity' und 'Property'
    mapping_dict: Output von regex_mapping_ui()
    """
    df = df.copy()

    for col in ["Entity", "Property"]:
        mapping_col = f"{col} Mapping"
        df[mapping_col] = ""

        for row in mapping_dict[col]:
            if not row or not row[0]:
                continue
            master = row[0]
            variants = [v for v in row[1:] if v]
            # Case-insensitive contains
            import re
            pattern = "|".join([re.escape(master)] + [re.escape(v) for v in variants])
            mask = df[col].str.contains(pattern, case=False, regex=True)
            df.loc[mask, mapping_col] = master

    return df


def unit_string_to_dimension(unit_str):
    """
    Wandelt einen Unit-String ('kWh/kg') in einen Dimension-String um.
    """
    if not unit_str or unit_str.strip() == "":
        return None

    try:
        parsed = unit_parser.parse(unit_str)

        # Compound
        if len(parsed) > 1:
            info = unit_parser.get_compound_unit_conversion_info(parsed)
            return str(info[1])   # dimension_vector

        # Simple
        if len(parsed) == 1:
            baseunit = parsed[0][2]
            info = unit_parser.unit_dimensions_and_kinds.get(baseunit)
            if info:
                return str(info["dimension_vector"])

    except Exception:
        return None

    return None


