"""
Memory-efficient loading of the quinex parquet datasets.
"""

import re
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq


# Large text columns that are not needed for plotting. Compared after
# normalising the column name (see normalize_column_name).
DEFAULT_EXCLUDED_COLUMNS = (
    "quote",
    "title",
    "authors",
    "author",
    "quantity",
    "quantity_text",
    "quantity_normalized",
    "classification",
    "__index_level_0__",
)

PROPERTY_COLUMN = "property_mapping"
UNIT_COLUMN = "unit_normalized"


def normalize_column_name(name: str) -> str:
    """Return snake_case column name, e.g. 'Property Mapping' -> 'property_mapping'. 'DOI' stays 'DOI'."""
    if name == "DOI":
        return name
    return re.sub(r"\s+", "_", str(name).strip()).lower()


def load_property_data(
    path: str,
    properties: list | str | None,
    unit_uris: list | str = None,
    columns: list = None,
    exclude_columns: tuple = DEFAULT_EXCLUDED_COLUMNS,
    snake_case: bool = True,
) -> pd.DataFrame:
    """
    Load only the rows of the given property mappings from a parquet file.

    Rows are filtered while reading, so the full dataset is never held in memory.

    Args:
        path: Path to the parquet file.
        properties: Property mapping(s) to load, e.g. ["Lifetime", "Efficiency"].
            None loads all rows; combine it with columns to keep memory low.
        unit_uris: Optional unit URI(s); keeps only rows with exactly one unit
            matching one of them (see filter_by_unit_uri).
        columns: Optional columns to load (either naming style). If None, all
            columns except exclude_columns are loaded.
        exclude_columns: Columns to skip when columns is None.
        snake_case: Rename columns to snake_case so both dataset versions share
            the same names ('Entity Mapping' -> 'entity_mapping').

    Returns:
        Filtered DataFrame.
    """
    if isinstance(properties, str):
        properties = [properties]

    file_columns = pq.read_schema(path).names
    normalized_to_file = {normalize_column_name(c): c for c in file_columns}

    property_col = normalized_to_file.get(PROPERTY_COLUMN)
    if property_col is None:
        raise KeyError(f"No property mapping column found in {path}. Columns: {file_columns}")

    if columns is None:
        excluded = {normalize_column_name(c) for c in exclude_columns}
        read_columns = [c for c in file_columns if normalize_column_name(c) not in excluded]
    else:
        missing = [c for c in columns if normalize_column_name(c) not in normalized_to_file]
        if missing:
            raise KeyError(f"Columns {missing} not found in {path}. Columns: {file_columns}")
        read_columns = [normalized_to_file[normalize_column_name(c)] for c in columns]
        if property_col not in read_columns:
            read_columns.append(property_col)

    df = pd.read_parquet(
        path,
        columns=read_columns,
        filters=[(property_col, "in", list(properties))] if properties is not None else None,
    )

    if snake_case:
        df = df.rename(columns=normalize_column_name)

    if unit_uris is not None:
        df = filter_by_unit_uri(df, unit_uris)

    return df.reset_index(drop=True)


def filter_by_unit_uri(
    df: pd.DataFrame,
    unit_uris: list | str,
    unit_col: str = None,
) -> pd.DataFrame:
    """
    Keep rows whose normalized unit is exactly one unit with one of the given URIs.

    Args:
        df: Input DataFrame.
        unit_uris: Unit URI(s), e.g. 'http://qudt.org/vocab/unit/PERCENT'.
        unit_col: Unit column. If None, 'unit_normalized' or 'Unit Normalized' is used.

    Returns:
        Filtered copy of the DataFrame.
    """
    if isinstance(unit_uris, str):
        unit_uris = [unit_uris]
    unit_uris = set(unit_uris)

    if unit_col is None:
        unit_col = next(
            (c for c in df.columns if normalize_column_name(c) == UNIT_COLUMN), None
        )
        if unit_col is None:
            raise KeyError(f"No unit column found. Columns: {list(df.columns)}")

    def _matches(units) -> bool:
        if units is None or isinstance(units, float):
            return False
        return len(units) == 1 and units[0].get('unit_uri') in unit_uris

    return df[df[unit_col].apply(_matches)].copy()


def load_reference_series(folder: str | list) -> pd.DataFrame:
    """
    Load external reference series (e.g. IRENA) to compare extracted values with.

    Every CSV file in the folder is one comparison line, with the columns entity,
    year and value (further columns such as unit and source are kept). The result
    is passed as 'additional_data' to plot_multiple_properties_over_time, which
    draws the line in the color of its entity. Several lines of the same entity
    (e.g. new projects and existing fleet) are told apart by the optional columns
    'series' (name shown in the line style legend) and 'linestyle' (matplotlib
    style, default '--').

    Args:
        folder: Folder with one CSV file per reference series, or a list of such
            folders (e.g. the new-project and the existing-fleet folder).

    Returns:
        DataFrame with all series of the folder(s).
    """
    folders = [folder] if isinstance(folder, (str, Path)) else folder
    files = sorted(f for d in folders for f in Path(d).glob("*.csv"))
    if not files:
        raise FileNotFoundError(f"No CSV files found in {folder}")

    series = [pd.read_csv(f) for f in files]
    for f, s in zip(files, series):
        missing = {"entity", "year", "value"} - set(s.columns)
        if missing:
            raise KeyError(f"{f.name} is missing the columns {sorted(missing)}")
    return pd.concat(series, ignore_index=True)
