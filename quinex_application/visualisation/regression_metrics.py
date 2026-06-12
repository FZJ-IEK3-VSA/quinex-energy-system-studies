"""Utilities for temporal log-regression slope and MAE metrics."""

from __future__ import annotations

import numpy as np
import pandas as pd


def _calculate_mean_absolute_error(
    reference_values: np.ndarray,
    comparison_values: np.ndarray,
) -> float | None:
    """Return mean absolute error in original units."""
    if len(reference_values) == 0 or len(comparison_values) == 0:
        return None

    mae = np.nanmean(np.abs(comparison_values - reference_values))
    if not np.isfinite(mae):
        return None

    return float(mae)


def _resolve_year_range(regression_year_range: tuple | None) -> tuple[float, float] | None:
    """Validate and normalize regression year range."""
    if regression_year_range is None:
        return None

    if len(regression_year_range) != 2:
        raise ValueError("regression_year_range must be a tuple of (min_year, max_year).")

    start_year, end_year = regression_year_range
    if start_year is None or end_year is None:
        raise ValueError("regression_year_range values cannot be None.")

    start_year = float(start_year)
    end_year = float(end_year)
    if start_year > end_year:
        start_year, end_year = end_year, start_year

    return start_year, end_year


def _prepare_additional_df(
    additional_df: pd.DataFrame | None,
    year_range: tuple[float, float] | None,
) -> pd.DataFrame | None:
    """Prepare additional data with the same transformation logic used in plotting."""
    if additional_df is None:
        return None

    required_cols = {'year', 'entity', 'value'}
    if not required_cols.issubset(additional_df.columns):
        return None

    prepared = additional_df.copy()
    prepared['year'] = pd.to_numeric(prepared['year'], errors='coerce')
    prepared['value'] = pd.to_numeric(prepared['value'], errors='coerce')
    prepared = prepared.dropna(subset=['year', 'entity', 'value'])
    prepared = prepared[prepared['value'] > 0]

    if year_range is not None:
        start_year, end_year = year_range
        prepared = prepared[(prepared['year'] >= start_year) & (prepared['year'] <= end_year)]

    return prepared.groupby(['entity', 'year'], as_index=False)['value'].mean()


def build_log_regression_metric_labels(
    fit_df: pd.DataFrame,
    entity_col: str,
    additional_df: pd.DataFrame | None = None,
    regression_year_range: tuple | None = None,
) -> list[str]:
    """Return labels with %/yr slope and MAE using unchanged existing logic."""
    prepared_fit_df = fit_df.copy()
    year_range = _resolve_year_range(regression_year_range)

    if year_range is not None:
        start_year, end_year = year_range
        prepared_fit_df = prepared_fit_df[
            (prepared_fit_df['jahr'] >= start_year)
            & (prepared_fit_df['jahr'] <= end_year)
        ]

    prepared_additional_df = _prepare_additional_df(additional_df, year_range)
    slope_labels: list[str] = []

    for entity in prepared_fit_df[entity_col].dropna().unique():
        entity_df = prepared_fit_df[prepared_fit_df[entity_col] == entity].copy()
        entity_df = entity_df.sort_values('jahr')
        entity_df = entity_df[np.isfinite(entity_df['value_central'])]
        entity_df = entity_df[entity_df['value_central'] > 0]

        if len(entity_df) < 2:
            continue

        x = entity_df['jahr'].astype(float).to_numpy()
        y = entity_df['value_central'].astype(float).to_numpy()

        slope_log, _intercept_log = np.polyfit(x, np.log(y), 1)
        slope_pct_per_year = (np.exp(slope_log) - 1.0) * 100.0
        slope_labels.append(f"{entity}: {slope_pct_per_year:+.2f}%/yr")

    if prepared_additional_df is not None:
        for entity in prepared_additional_df['entity'].dropna().unique():
            entity_df = prepared_additional_df[prepared_additional_df['entity'] == entity].copy()
            entity_df = entity_df.sort_values('year')
            entity_df = entity_df[np.isfinite(entity_df['value'])]
            entity_df = entity_df[entity_df['value'] > 0]

            if len(entity_df) < 2:
                continue

            x = entity_df['year'].astype(float).to_numpy()
            y = entity_df['value'].astype(float).to_numpy()

            slope_log, _intercept_log = np.polyfit(x, np.log(y), 1)
            slope_pct_per_year = (np.exp(slope_log) - 1.0) * 100.0
            label = f"{entity}_Additional: {slope_pct_per_year:+.2f}%/yr"

            input_entity_df = prepared_fit_df[prepared_fit_df[entity_col] == entity].copy()
            comparison_df = pd.merge(
                input_entity_df[['jahr', 'value_central']],
                entity_df[['year', 'value']],
                left_on='jahr',
                right_on='year',
                how='inner',
            ).dropna(subset=['value_central', 'value'])

            if len(comparison_df) >= 1:
                comparison_df = comparison_df.sort_values('jahr')
                reference_values = comparison_df['value_central'].astype(float).to_numpy()
                comparison_values = comparison_df['value'].astype(float).to_numpy()
                mean_absolute_error = _calculate_mean_absolute_error(
                    reference_values,
                    comparison_values,
                )
                if mean_absolute_error is not None:
                    label += f" | MAE={mean_absolute_error:.1f}"

            slope_labels.append(label)

    return slope_labels
