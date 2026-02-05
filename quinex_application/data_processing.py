"""
Data processing utilities for quinex visualizations.

This module provides helper functions for data cleaning, filtering,
aggregation, and transformation operations used across visualization modules.
"""

import ast
import requests
import numpy as np
import pandas as pd
import scipy.stats as st


# =============================================================================
# Unit Conversion
# =============================================================================

def convert_unit(
    value: float,
    input_unit: str,
    output_unit: str,
    year: int,
    parse: bool = False,
    api_url: str = "http://134.94.117.230:8000/api/units/convert_units/"
) -> dict:
    """
    Convert a value from one unit to another using the quinex API.
    
    Args:
        value: Numeric value to convert.
        input_unit: Source unit string.
        output_unit: Target unit string.
        year: Year for time-dependent conversions.
        parse: Whether to parse the units.
        api_url: URL of the conversion API.
        
    Returns:
        API response as dictionary.
    """
    payload = {
        "value": value,
        "input_unit": str(input_unit),
        "output_unit": str(output_unit),
        "year": year,
        "parse": parse,
    }
    response = requests.post(api_url, json=payload)
    return response.json()


def convert_row(
    row: pd.Series,
    target_unit: str,
    year: int = None,
    unit_col: str = "unit_normalized",
    value_col: str = "value_normalized",
    year_col: str = "publication_year"
) -> float:
    """
    Convert a DataFrame row's value to a target unit.
    
    Args:
        row: DataFrame row with unit and value columns.
        target_unit: Target unit for conversion.
        year: Override year for conversion. If None, uses row's year.
        unit_col: Column name for input unit.
        value_col: Column name for value.
        year_col: Column name for year.
        
    Returns:
        Converted value or None if conversion fails.
    """
    input_unit = row[unit_col]
    value = row[value_col]
    conversion_year = year if year else row[year_col]
    
    if pd.isna(value):
        return None
    
    try:
        result = convert_unit(value, input_unit, target_unit, conversion_year, False)
        return result[0]
    except Exception:
        return None


# =============================================================================
# Outlier Filtering
# =============================================================================

def apply_iqr_filter(
    df: pd.DataFrame,
    value_column: str,
    group_column: str,
    lower_quantile: float = 0.2,
    upper_quantile: float = 0.8,
    iqr_multiplier: float = 1.5
) -> pd.DataFrame:
    """
    Remove outliers using the IQR (Interquartile Range) method.
    
    Args:
        df: Input DataFrame.
        value_column: Column to filter outliers from.
        group_column: Column to group by for IQR calculation.
        lower_quantile: Lower quantile boundary (default 0.2).
        upper_quantile: Upper quantile boundary (default 0.8).
        iqr_multiplier: Multiplier for IQR range (default 1.5).
        
    Returns:
        DataFrame with outliers removed.
    """
    Q1 = df.groupby(group_column)[value_column].transform(
        lambda x: x.quantile(lower_quantile)
    )
    Q3 = df.groupby(group_column)[value_column].transform(
        lambda x: x.quantile(upper_quantile)
    )
    IQR = Q3 - Q1
    lower = Q1 - iqr_multiplier * IQR
    upper = Q3 + iqr_multiplier * IQR
    
    mask = (df[value_column] >= lower) & (df[value_column] <= upper)
    return df[mask]


# =============================================================================
# Temporal Data Processing
# =============================================================================

def parse_temporal_scope(
    df: pd.DataFrame,
    temporal_col: str = "temporal_scope",
    fallback_col: str = "publication_year",
    output_col: str = "jahr"
) -> pd.DataFrame:
    """
    Parse temporal scope column and extract year information.
    
    Args:
        df: Input DataFrame.
        temporal_col: Column containing temporal scope data.
        fallback_col: Column to use if temporal scope is missing.
        output_col: Name for the output year column.
        
    Returns:
        DataFrame with parsed year column.
    """
    df = df.copy()
    
    df[temporal_col] = df[temporal_col].apply(
        lambda x: x if isinstance(x, dict) 
        else ({'year': ast.literal_eval(x)['year']} if isinstance(x, str) else {'year': x})
    )
    
    df[output_col] = df[temporal_col].apply(lambda x: x.get('year', pd.NA))
    df[output_col] = pd.to_numeric(df[output_col], errors='coerce')
    df[output_col] = df[output_col].fillna(df[fallback_col]).astype(int)
    
    return df


def filter_by_min_papers(
    df: pd.DataFrame,
    year_col: str,
    doi_col: str = 'DOI',
    min_papers: int = None
) -> pd.DataFrame:
    """
    Filter DataFrame to keep only years with minimum number of unique papers.
    
    Args:
        df: Input DataFrame.
        year_col: Column containing year information.
        doi_col: Column containing DOI/paper identifiers.
        min_papers: Minimum number of papers required per year.
        
    Returns:
        Filtered DataFrame.
    """
    if min_papers is None:
        return df
    
    papers_per_year = df.groupby(year_col)[doi_col].nunique()
    valid_years = papers_per_year[papers_per_year >= min_papers].index
    return df[df[year_col].isin(valid_years)]


# =============================================================================
# Spatial Data Processing
# =============================================================================

def parse_spatial_scope(
    df: pd.DataFrame,
    spatial_col: str = "spatial_scope"
) -> pd.DataFrame:
    """
    Parse spatial scope column and extract latitude/longitude.
    
    Args:
        df: Input DataFrame.
        spatial_col: Column containing spatial scope data.
        
    Returns:
        DataFrame with latitude and longitude columns.
    """
    df = df[df[spatial_col].notna()].copy()
    
    df['spatial_scope'] = df[spatial_col].apply(
        lambda x: x if isinstance(x, dict)
        else ast.literal_eval(x) if isinstance(x, str)
        else {'country': None, 'latitude': None, 'longitude': None}
    )

    df['latitude'] = df[spatial_col].apply(
        lambda x: float(x['latitude']) if isinstance(x, dict) and 'latitude' in x else None
    )
    df['longitude'] = df[spatial_col].apply(
        lambda x: float(x['longitude']) if isinstance(x, dict) and 'longitude' in x else None
    )
    
    return df


def apply_jitter(
    df: pd.DataFrame,
    lat_col: str = 'latitude',
    lon_col: str = 'longitude',
    jitter_strength: float = 0.2
) -> pd.DataFrame:
    """
    Apply random jitter to coordinates to reduce point overlap.
    
    Args:
        df: Input DataFrame with coordinate columns.
        lat_col: Latitude column name.
        lon_col: Longitude column name.
        jitter_strength: Maximum shift in degrees.
        
    Returns:
        DataFrame with jittered coordinates.
    """
    df = df.copy()
    df[lat_col] += np.random.uniform(-jitter_strength, jitter_strength, size=len(df))
    df[lon_col] += np.random.uniform(-jitter_strength, jitter_strength, size=len(df))
    return df


def apply_jitter_to_datasets(
    datasets: list,
    jitter_strength: float = 0.2
) -> list:
    """
    Apply jitter to all DataFrames in a datasets list.
    
    Args:
        datasets: List of dicts with 'df' key containing DataFrames.
        jitter_strength: Maximum shift in degrees.
        
    Returns:
        List of datasets with jittered coordinates.
    """
    jittered = []
    for d in datasets:
        d_copy = d.copy()
        d_copy['df'] = apply_jitter(d_copy['df'], jitter_strength=jitter_strength)
        jittered.append(d_copy)
    return jittered


# =============================================================================
# Statistical Aggregation
# =============================================================================

def calculate_aggregates(
    df: pd.DataFrame,
    group_col: str,
    value_col: str,
    year_col: str = 'jahr',
    central_tendency: str = "mean",
    error_type: str = "se"
) -> pd.DataFrame:
    """
    Calculate statistical aggregates by year and group.
    
    Args:
        df: Input DataFrame.
        group_col: Column to group by (e.g., entity type).
        value_col: Column containing values to aggregate.
        year_col: Column containing year information.
        central_tendency: 'mean', 'median', or 'moving average'.
        error_type: 'se' (standard error) or 'ci' (confidence interval).
        
    Returns:
        DataFrame with aggregated statistics.
    """
    if central_tendency == "median":
        agg_df = _aggregate_median(df, year_col, group_col, value_col)
        
    elif central_tendency == "mean":
        agg_df = _aggregate_mean(df, year_col, group_col, value_col, error_type)
        
    elif central_tendency == "moving average":
        agg_df = _aggregate_moving_average(df, year_col, group_col, value_col, error_type)
        
    else:
        raise ValueError(f"Unknown central_tendency: {central_tendency}")

    # Remove first year if gap is >= 10 years
    unique_years = sorted(agg_df[year_col].unique())
    if len(unique_years) >= 2 and (unique_years[1] - unique_years[0]) >= 10:
        agg_df = agg_df[agg_df[year_col] != unique_years[0]]

    agg_df['n'] = agg_df['n'].astype(float)
    return agg_df.sort_values(by='n', ascending=False)


def _aggregate_median(
    df: pd.DataFrame,
    year_col: str,
    group_col: str,
    value_col: str
) -> pd.DataFrame:
    """Calculate median-based aggregates."""
    agg_df = df.groupby([year_col, group_col])[value_col].agg(
        ['median', 'count']
    ).reset_index()
    agg_df = agg_df.rename(columns={'median': 'value_central', 'count': 'n'})
    agg_df['std_dev'] = df.groupby([year_col, group_col])[value_col].std().values
    agg_df['se'] = agg_df['std_dev'] / np.sqrt(agg_df['n'])
    return agg_df


def _aggregate_mean(
    df: pd.DataFrame,
    year_col: str,
    group_col: str,
    value_col: str,
    error_type: str
) -> pd.DataFrame:
    """Calculate mean-based aggregates."""
    agg_df = df.groupby([year_col, group_col])[value_col].agg(
        ['mean', 'std', 'count']
    ).reset_index()
    agg_df = agg_df.rename(columns={
        'mean': 'value_central', 
        'std': 'std_dev', 
        'count': 'n'
    })
    agg_df['se'] = agg_df['std_dev'] / np.sqrt(agg_df['n'])
    agg_df['se'] = agg_df['se'].astype(float)

    if error_type == "ci":
        agg_df['t_val'] = agg_df['n'].apply(
            lambda n: st.t.ppf(0.975, n-1) if n > 1 else np.nan
        )
        agg_df['ci'] = agg_df['t_val'] * agg_df['se']
        agg_df['ci_lower'] = agg_df['value_central'] - agg_df['ci']
        agg_df['ci_upper'] = agg_df['value_central'] + agg_df['ci']
    
    return agg_df


def _aggregate_moving_average(
    df: pd.DataFrame,
    year_col: str,
    group_col: str,
    value_col: str,
    error_type: str,
    window: int = 3
) -> pd.DataFrame:
    """Calculate moving average aggregates."""
    all_years = pd.DataFrame({year_col: range(df[year_col].min(), df[year_col].max() + 1)})
    entities = df[group_col].unique()
    full_index = pd.MultiIndex.from_product(
        [all_years[year_col], entities], 
        names=[year_col, group_col]
    ).to_frame(index=False)

    mean_values = df.groupby([year_col, group_col])[value_col].mean().reset_index()
    agg_df = full_index.merge(
        mean_values, 
        on=[year_col, group_col], 
        how='left'
    ).sort_values([group_col, year_col])
    
    agg_df['value_central'] = agg_df.groupby(group_col)[value_col].transform(
        lambda x: x.rolling(window=window, center=True, min_periods=1).mean()
    )
    
    count_df = df.groupby([year_col, group_col]).size().reset_index(name='n')
    agg_df = agg_df.merge(count_df, on=[year_col, group_col], how='left')
    agg_df = agg_df[~agg_df[value_col].isna()]

    agg_df['std_dev'] = agg_df.groupby(group_col)[value_col].transform(
        lambda x: x.rolling(window=window, center=True, min_periods=1).std()
    )
    agg_df['n_window'] = agg_df.groupby(group_col)[value_col].transform(
        lambda x: x.rolling(window=window, center=True, min_periods=1).count()
    )
    agg_df['se'] = agg_df['std_dev'] / np.sqrt(agg_df['n_window'])

    if error_type == "ci":
        agg_df['t_val'] = agg_df['n_window'].apply(
            lambda n: st.t.ppf(0.975, n-1) if n > 1 else np.nan
        )
        agg_df['ci'] = agg_df['t_val'] * agg_df['se']
        agg_df['ci_lower'] = agg_df['value_central'] - agg_df['ci']
        agg_df['ci_upper'] = agg_df['value_central'] + agg_df['ci']
    
    return agg_df


# =============================================================================
# Keyword Mapping
# =============================================================================

def map_to_keyword_group(text: str, keywords_dict: dict) -> str:
    """
    Map text to a keyword group based on keyword matching.
    
    Args:
        text: Text to search for keywords.
        keywords_dict: Dict mapping group names to keyword lists.
        
    Returns:
        Matched group name or None.
    """
    for group, keywords in keywords_dict.items():
        for kw in keywords:
            if kw.lower() in str(text).lower():
                return group
    return None


def apply_keyword_mapping(
    df: pd.DataFrame,
    column: str,
    keywords_dict: dict,
    output_col: str = None
) -> pd.DataFrame:
    """
    Apply keyword mapping to a DataFrame column.
    
    Args:
        df: Input DataFrame.
        column: Column to search for keywords.
        keywords_dict: Dict mapping group names to keyword lists.
        output_col: Name for output column. Defaults to '{column}_group'.
        
    Returns:
        DataFrame with new group column.
    """
    df = df.copy()
    if output_col is None:
        output_col = f"{column}_group"
    
    df[output_col] = df[column].apply(
        lambda x: map_to_keyword_group(x, keywords_dict)
    )
    return df


# =============================================================================
# Share Calculations
# =============================================================================

def calculate_yearly_shares(
    df: pd.DataFrame,
    year_col: str,
    group_col: str,
    doi_col: str = 'DOI'
) -> pd.DataFrame:
    """
    Calculate share of papers per group per year.
    
    Args:
        df: Input DataFrame.
        year_col: Column containing year information.
        group_col: Column to group by.
        doi_col: Column containing paper identifiers.
        
    Returns:
        DataFrame with count and share columns.
    """
    total_per_year = df.groupby(year_col)[doi_col].nunique()
    
    counts = df.groupby([year_col, group_col])[doi_col].nunique().reset_index(name='count')
    counts['share'] = counts.apply(
        lambda row: row['count'] / total_per_year[row[year_col]],
        axis=1
    )
    
    return counts


def calculate_total_shares(
    df: pd.DataFrame,
    group_col: str,
    doi_col: str = 'DOI'
) -> pd.DataFrame:
    """
    Calculate total share of papers per group.
    
    Args:
        df: Input DataFrame.
        group_col: Column to group by.
        doi_col: Column containing paper identifiers.
        
    Returns:
        DataFrame with count and share columns.
    """
    total_papers = df[doi_col].nunique()
    
    counts = df.groupby(group_col)[doi_col].nunique().reset_index(name='count')
    counts['share'] = counts['count'] / total_papers
    
    return counts
