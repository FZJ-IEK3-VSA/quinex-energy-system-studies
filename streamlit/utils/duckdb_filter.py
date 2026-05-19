import os
import re
import ast
import json
import builtins
import duckdb
import pandas as pd
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
PARQUET_FILE = os.path.join(BASE_DIR, "streamlit", "duckdb_data", "df_quinex.parquet")
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


def _run_query(query, params=None, fetch="all", retries=1):
    """
    Führt eine Query robust aus und versucht bei DuckDB-"cancelled"-Fehlern
    einmal mit neuer Verbindung erneut.
    """
    global con

    params = params or ()
    attempts = retries + 1

    for attempt in range(attempts):
        try:
            result = con.execute(query, params)
            if fetch == "one":
                return result.fetchone()
            if fetch == "df":
                return result.df()
            return result.fetchall()
        except duckdb.InvalidInputException as exc:
            msg = str(exc).lower()
            can_retry = "cancelled" in msg and attempt < attempts - 1
            if not can_retry:
                raise

            try:
                con.close()
            except (RuntimeError, duckdb.Error):
                pass

            con = duckdb.connect(DB_FILE)


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

    author_origin_values = regex_filters.get("__author_origin_values", [])
    publication_year_range = regex_filters.get("__publication_year_range")
    temporal_scope_values = regex_filters.get("__temporal_scope_values", [])
    spatial_scope_values = regex_filters.get("__spatial_scope_values", [])

    for col, patterns in regex_filters.items():
        if col.startswith("__"):
            continue

        if not patterns:
            continue

        if col == "unit_dimension":
            # exakte Dimension — kein Regex
            dim_clauses = [f"unit_dimension = '{_sql_quote(d)}'" for d in patterns]
            clauses.append("(" + " OR ".join(dim_clauses) + ")")
        elif col in {"Entity", "Property"}:
            exact_one_clause = _build_exactly_one_match_clause(col, patterns)
            if exact_one_clause:
                clauses.append(exact_one_clause)
        else:
            # Regex wie bisher
            transformed = []
            for p in patterns:
                safe_p = re.escape(p)
                transformed.append(f"(?i).*{safe_p}.*")
            combined = "|".join(transformed)
            clauses.append(f"{col} ~ '{_sql_quote(combined)}'")

    if author_origin_values:
        author_clause = _build_contains_any_clause("Author Origin", author_origin_values)
        if author_clause:
            clauses.append(author_clause)

    if temporal_scope_values:
        temporal_clause = _build_temporal_year_clause(temporal_scope_values)
        if temporal_clause:
            clauses.append(temporal_clause)

    if spatial_scope_values:
        spatial_clause = _build_spatial_country_clause(spatial_scope_values)
        if spatial_clause:
            clauses.append(spatial_clause)

    if (
        isinstance(publication_year_range, (list, tuple))
        and len(publication_year_range) == 2
    ):
        year_min, year_max = publication_year_range
        try:
            year_min = int(year_min)
            year_max = int(year_max)
            clauses.append(
                f"TRY_CAST(\"Publication Year\" AS INTEGER) BETWEEN {year_min} AND {year_max}"
            )
        except (TypeError, ValueError):
            pass


    if clauses:
        return "WHERE " + " AND ".join(clauses)

    return ""


def get_total_rows(regex_filters=None):
    where_clause = build_where_clause(regex_filters)
    query = f"SELECT COUNT(*) FROM data {where_clause}"
    row = _run_query(query, fetch="one")
    return row[0] if row else 0


def get_page(regex_filters=None, limit=100, offset=0):
    where_clause = build_where_clause(regex_filters)
    query = f"""
        SELECT *
        FROM data
        {where_clause}
        LIMIT {limit}
        OFFSET {offset}
    """
    return _run_query(query, fetch="df")


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
        if col in {"Unit", "Year"} or col.startswith("__"):
            continue  # später separat

        if not isinstance(groups, list):
            continue

        lst = []
        for row in groups:
            if not isinstance(row, (list, tuple)):
                continue

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

    for key in [
        "__author_origin_values",
        "__temporal_scope_values",
        "__spatial_scope_values",
    ]:
        vals = mapping_dict.get(key, [])
        if vals:
            flat[key] = vals

    year_range = mapping_dict.get("__publication_year_range")
    if isinstance(year_range, (list, tuple)) and len(year_range) == 2:
        flat["__publication_year_range"] = tuple(year_range)

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


def get_columns():
    """Gibt die Spaltennamen der data-Tabelle zurück."""
    result = _run_query("SELECT column_name FROM information_schema.columns WHERE table_name = 'data'", fetch="all")
    return [row[0] for row in result]


def get_value_counts(column, regex_filters=None, top_n=20):
    """
    Zählt die häufigsten Werte einer Spalte.
    Bei LIST-Spalten wird UNNEST verwendet.
    """
    where_clause = build_where_clause(regex_filters)
    not_null_connector = "AND" if where_clause else "WHERE"

    if column == "Spatial Scope":
        query = f'''
            SELECT CAST("{column}" AS VARCHAR) AS value
            FROM data
            {where_clause}
            {not_null_connector} "{column}" IS NOT NULL AND TRIM(CAST("{column}" AS VARCHAR)) != ''
        '''
        rows = _run_query(query, fetch="all")

        counts = {}
        for (raw_val,) in rows:
            countries = _extract_spatial_countries(raw_val)
            for country in countries:
                key = str(country).strip()
                if not key:
                    continue
                counts[key] = counts.get(key, 0) + 1

        if not counts:
            return pd.DataFrame(columns=["value", "count"])

        def _spatial_sort_key(item):
            return (-item[1], item[0].lower())

        sorted_items = sorted(counts.items(), key=_spatial_sort_key)
        top_items = sorted_items[: int(top_n)]
        return pd.DataFrame(top_items, columns=["value", "count"])

    # Spaltentyp prüfen
    col_type = _run_query(
        "SELECT data_type FROM information_schema.columns WHERE table_name = 'data' AND column_name = ?",
        (column,),
        fetch="one",
    )

    if col_type and col_type[0].upper().startswith("VARCHAR[]"):
        # VARCHAR-LIST-Spalte → UNNEST
        query = f"""
            SELECT unnested_val AS value, COUNT(*) AS count
            FROM (
                SELECT UNNEST("{column}") AS unnested_val
                FROM data
                {where_clause}
            )
            WHERE unnested_val IS NOT NULL AND unnested_val != ''
            GROUP BY value
            ORDER BY count DESC
            LIMIT {int(top_n)}
        """
    elif col_type and "[]" in col_type[0]:
        # Nicht-VARCHAR-LIST (z.B. STRUCT[]) → ganzen Eintrag als VARCHAR casten, kein UNNEST
        query = f"""
            SELECT CAST("{column}" AS VARCHAR) AS value, COUNT(*) AS count
            FROM data
            {where_clause}
            {not_null_connector} "{column}" IS NOT NULL
            GROUP BY value
            ORDER BY count DESC
            LIMIT {int(top_n)}
        """
    else:
        query = f"""
            SELECT CAST("{column}" AS VARCHAR) AS value, COUNT(*) AS count
            FROM data
            {where_clause}
            {not_null_connector} "{column}" IS NOT NULL AND CAST("{column}" AS VARCHAR) != ''
            GROUP BY value
            ORDER BY count DESC
            LIMIT {int(top_n)}
        """

    return _run_query(query, fetch="df")


def _sql_quote(value):
    return str(value).replace("'", "''")


def _build_contains_any_clause(column, values):
    conditions = []
    for v in values:
        token = str(v).strip()
        if not token:
            continue

        token_sql = _sql_quote(token)
        token_pattern = re.escape(token)
        token_pattern_sql = _sql_quote(
            f"(?i)(^|[^A-Za-z0-9]){token_pattern}([^A-Za-z0-9]|$)"
        )

        conditions.append(
            f"(CAST(\"{column}\" AS VARCHAR) = '{token_sql}' "
            f"OR regexp_matches(CAST(\"{column}\" AS VARCHAR), '{token_pattern_sql}'))"
        )

    if not conditions:
        return ""

    return "(" + " OR ".join(conditions) + ")"


def _build_spatial_country_clause(values):
    conditions = []
    for country in _dedupe_values(values):
        token = str(country).strip()
        if not token:
            continue

        token_sql = _sql_quote(token)
        escaped = re.escape(token)
        country_key_regex_quoted = _sql_quote(
            f"(?i).*['\\\"]country['\\\"]\\s*:\\s*['\\\"]{escaped}['\\\"].*"
        )
        country_key_regex_unquoted = _sql_quote(
            f"(?i).*['\\\"]country['\\\"]\\s*:\\s*{escaped}\\s*(,|}}).*"
        )

        conditions.append(
            f"(LOWER(TRIM(CAST(\"Spatial Scope\" AS VARCHAR))) = LOWER('{token_sql}') "
            f"OR regexp_matches(CAST(\"Spatial Scope\" AS VARCHAR), '{country_key_regex_quoted}') "
            f"OR regexp_matches(CAST(\"Spatial Scope\" AS VARCHAR), '{country_key_regex_unquoted}'))"
        )

    if not conditions:
        return ""

    return "(" + " OR ".join(conditions) + ")"


def _build_temporal_year_clause(values):
    conditions = []
    for year_val in _dedupe_values(values):
        year_token = _normalize_year_token(year_val)
        if year_token is None:
            continue

        year_int = int(year_token)
        year_sql = _sql_quote(str(year_int))

        # Unterstützt "{'year': 1800.0}", "{'year': 1800}" und reine Jahreswerte
        year_key_regex = _sql_quote(
            f"(?i).*['\\\"]year['\\\"]\\s*:\\s*{year_int}(?:\\.0+)?\\s*(,|}}).*"
        )

        conditions.append(
            f"(TRY_CAST(CAST(\"Temporal Scope\" AS VARCHAR) AS DOUBLE) = {year_int} "
            f"OR regexp_matches(CAST(\"Temporal Scope\" AS VARCHAR), '{year_key_regex}') "
            f"OR regexp_matches(CAST(\"Temporal Scope\" AS VARCHAR), '(?i)^\\s*{year_sql}(?:\\.0+)?\\s*$'))"
        )

    if not conditions:
        return ""

    return "(" + " OR ".join(conditions) + ")"


def _build_exactly_one_match_clause(column, patterns):
    pattern_terms = []
    for p in _dedupe_values(patterns):
        token = str(p).strip()
        if not token:
            continue

        regex = _sql_quote(f"(?i).*{re.escape(token)}.*")
        pattern_terms.append(
            f"CASE WHEN regexp_matches(CAST(\"{column}\" AS VARCHAR), '{regex}') THEN 1 ELSE 0 END"
        )

    if not pattern_terms:
        return ""

    return "(" + " + ".join(pattern_terms) + ") = 1"


def _dedupe_values(values):
    seen = set()
    result = []
    for v in values:
        token = str(v).strip()
        if not token:
            continue
        key = token.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(token)
    return result


def _parse_list_like(value):
    if isinstance(value, (list, tuple)):
        return list(value)

    if value is None:
        return None

    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        if s.startswith("[") and s.endswith("]"):
            try:
                parsed = ast.literal_eval(s)
                if isinstance(parsed, (list, tuple)):
                    return list(parsed)
            except Exception:
                pass
            try:
                parsed = json.loads(s)
                if isinstance(parsed, (list, tuple)):
                    return list(parsed)
            except Exception:
                pass

    return None


def _parse_structure_like(value):
    if isinstance(value, (dict, list, tuple)):
        return value

    if not isinstance(value, str):
        return None

    s = value.strip()
    if not s:
        return None

    if (s.startswith("{") and s.endswith("}")) or (s.startswith("[") and s.endswith("]")):
        try:
            return ast.literal_eval(s)
        except (ValueError, SyntaxError):
            pass
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            pass

    return None


def _extract_spatial_countries(raw_value):
    parsed = _parse_structure_like(raw_value)
    countries = set()

    def _collect(item):
        if isinstance(item, dict):
            country = item.get("country")
            if country is not None:
                country_s = str(country).strip()
                if country_s:
                    countries.add(country_s)
            return

        if isinstance(item, (list, tuple)):
            for sub_item in item:
                _collect(sub_item)
            return

        if isinstance(item, str):
            token = item.strip()
            if token:
                countries.add(token)

    if parsed is not None:
        _collect(parsed)
    elif isinstance(raw_value, str):
        for country in _extract_country_tokens_from_string(raw_value):
            countries.add(country)

    return countries


def _extract_country_tokens_from_string(text):
    if not isinstance(text, str):
        return []

    # Unterstützt sowohl quoted als auch unquoted country-Werte:
    # {'country': 'Spain', ...} und {'country': Spain, ...}
    pattern = r"['\"]country['\"]\s*:\s*(?:['\"]([^'\"]+)['\"]|([^,}\]]+))"
    matches = re.findall(pattern, text, flags=re.IGNORECASE)

    tokens = []
    for quoted, unquoted in matches:
        raw = quoted if quoted else unquoted
        token = str(raw).strip().strip("'\"")
        if token:
            tokens.append(token)

    return tokens


def _extract_temporal_years(raw_value):
    parsed = _parse_structure_like(raw_value)
    years = set()

    def _collect(item):
        if isinstance(item, dict):
            if "year" in item:
                normalized = _normalize_year_token(item.get("year"))
                if normalized is not None:
                    years.add(str(int(normalized)))
            return

        if isinstance(item, (list, tuple)):
            for sub_item in item:
                _collect(sub_item)
            return

        normalized = _normalize_year_token(item)
        if normalized is not None:
            years.add(str(int(normalized)))

    if parsed is not None:
        _collect(parsed)
    elif isinstance(raw_value, str):
        for year in _extract_year_tokens_from_string(raw_value):
            years.add(year)

    return years


def _extract_year_tokens_from_string(text):
    if not isinstance(text, str):
        return []

    tokens = []

    # year aus Dict-ähnlicher Struktur extrahieren
    matches = re.findall(r"['\"]year['\"]\s*:\s*([-+]?\d+(?:\.\d+)?)", text, flags=re.IGNORECASE)
    for m in matches:
        normalized = _normalize_year_token(m)
        if normalized is not None:
            tokens.append(str(int(normalized)))

    # Fallback: reiner numerischer String
    if not tokens:
        normalized = _normalize_year_token(text)
        if normalized is not None:
            tokens.append(str(int(normalized)))

    return tokens


def _normalize_year_token(value):
    if value is None:
        return None

    if isinstance(value, str):
        token = value.strip()
        if not token:
            return None
        token = token.replace(",", ".")
    else:
        token = value

    try:
        year_num = float(token)
    except (TypeError, ValueError):
        return None

    if year_num != year_num:
        return None

    year_int = int(year_num)
    if year_int < 0 or year_int > 3000:
        return None

    return year_int


def _get_column_type(column):
    col_type = _run_query(
        "SELECT data_type FROM information_schema.columns WHERE table_name = 'data' AND column_name = ?",
        (column,),
        fetch="one",
    )
    if not col_type:
        return None
    return str(col_type[0])


def get_publication_year_bounds(regex_filters=None):
    if "Publication Year" not in get_columns():
        return (None, None)

    where_clause = build_where_clause(regex_filters)

    result = _run_query(
        f'''
        SELECT
            MIN(TRY_CAST("Publication Year" AS INTEGER)) AS min_year,
            MAX(TRY_CAST("Publication Year" AS INTEGER)) AS max_year
        FROM data
        {where_clause}
        ''',
        fetch="one",
    )

    if not result:
        return (None, None)

    min_year, max_year = result
    if min_year is None or max_year is None:
        return (None, None)

    return (int(min_year), int(max_year))


def get_scope_values(column, limit=400, regex_filters=None):
    if column not in get_columns():
        return []

    where_clause = build_where_clause(regex_filters)
    not_null_connector = "AND" if where_clause else "WHERE"

    col_type = _get_column_type(column)
    if column == "Spatial Scope":
        query = f'''
            SELECT DISTINCT CAST("{column}" AS VARCHAR) AS value
            FROM data
            {where_clause}
            {not_null_connector} "{column}" IS NOT NULL AND TRIM(CAST("{column}" AS VARCHAR)) != ''
            LIMIT {int(limit)}
        '''
    elif col_type and col_type.upper().startswith("VARCHAR[]"):
        query = f'''
            SELECT DISTINCT UNNEST("{column}") AS value
            FROM data
            {where_clause}
            {not_null_connector} "{column}" IS NOT NULL
            LIMIT {int(limit)}
        '''
    else:
        query = f'''
            SELECT DISTINCT CAST("{column}" AS VARCHAR) AS value
            FROM data
            {where_clause}
            {not_null_connector} "{column}" IS NOT NULL AND TRIM(CAST("{column}" AS VARCHAR)) != ''
            LIMIT {int(limit)}
        '''

    rows = _run_query(query, fetch="all")

    values = set()
    for (raw_val,) in rows:
        if column == "Spatial Scope":
            values.update(_extract_spatial_countries(raw_val))
            continue

        if column == "Temporal Scope":
            values.update(_extract_temporal_years(raw_val))
            continue

        parsed = _parse_list_like(raw_val)
        if parsed is not None:
            for item in parsed:
                item_s = str(item).strip()
                if item_s:
                    values.add(item_s)
        else:
            item_s = str(raw_val).strip()
            if item_s:
                values.add(item_s)

    if column == "Temporal Scope":
        return sorted(values, key=lambda x: int(x))

    return sorted(values, key=lambda x: x.lower())


def get_author_origin_values(limit=1000, regex_filters=None):
    column = "Author Origin"
    if column not in get_columns():
        return []

    where_clause = build_where_clause(regex_filters)
    not_null_connector = "AND" if where_clause else "WHERE"

    col_type = _get_column_type(column)
    if col_type and col_type.upper().startswith("VARCHAR[]"):
        query = f'''
            SELECT DISTINCT UNNEST("{column}") AS value
            FROM data
            {where_clause}
            {not_null_connector} "{column}" IS NOT NULL
            LIMIT {int(limit)}
        '''
    else:
        query = f'''
            SELECT DISTINCT CAST("{column}" AS VARCHAR) AS value
            FROM data
            {where_clause}
            {not_null_connector} "{column}" IS NOT NULL AND TRIM(CAST("{column}" AS VARCHAR)) != ''
            LIMIT {int(limit)}
        '''

    rows = _run_query(query, fetch="all")

    values = set()
    for (raw_val,) in rows:
        parsed = _parse_list_like(raw_val)
        if parsed is not None:
            candidates = parsed
        else:
            candidates = [raw_val]

        for item in candidates:
            token = str(item).strip().upper()
            if token:
                values.add(token)

    return sorted(values)


