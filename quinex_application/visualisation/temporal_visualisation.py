"""Temporal visualization methods for Quinex."""

import math
import importlib
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns

from quinex_application.visualisation.plot_utils import (
    set_font_sizes,
    setup_plotting_environment,
    create_line_legend_handles,
    map_values_to_sizes,
    create_entity_color_palette,
    flatten_axes,
    add_corpus_note,
)
from quinex_application.visualisation.entity_colors import DEFAULT_ENTITY_COLORS
from quinex_application.postprocessing.data_processing import (
    apply_iqr_filter,
    parse_temporal_scope,
    filter_by_min_papers,
    calculate_aggregates,
    split_dois_by_text_availability,
    merge_text_availability_splits,
    format_text_availability_counts,
    describe_corpus,
    restrict_datasets_to_full_text,
)


class TemporalVisualisation:
    """Temporal and time-series visualization functionality."""

    def __init__(self):
        """Initialize temporal visualization defaults and entity colors."""
        pd.set_option('display.max_colwidth', None)

        self.color = sns.color_palette("dark:steelblue", 6)[2]
        self.color2 = sns.color_palette("dark:cyan", 6)[2]
        self.entity_colors = DEFAULT_ENTITY_COLORS.copy()

        setup_plotting_environment()

    def plot_top_values(
        self,
        df: pd.DataFrame,
        column: str,
        top_n: int = 10,
        ignore_empty: bool = True,
        figsize: tuple = (6, 6),
    ):
        """
        Create a bar plot of the top N most frequent values.

        Args:
            df: DataFrame containing the data.
            column: Column name to analyze.
            top_n: Number of top values to display.
            ignore_empty: Whether to exclude empty/null values.
            figsize: Figure size.
            title: Plot title.

        Returns:
            Matplotlib figure.
        """
        data = df[column]

        if ignore_empty:
            data = data.dropna()

        cleaned_data = (
            data.astype(str)
            .str.replace(r"\s+", " ", regex=True)
            .str.strip()
        )
        cleaned_data = cleaned_data[cleaned_data != ""]

        value_counts = cleaned_data.value_counts().nlargest(top_n)

        fig, ax = plt.subplots(figsize=figsize)
        sns.barplot(x=value_counts.values, y=value_counts.index, ax=ax, color="steelblue")

        ax.set_xlabel("Count")
        ax.set_ylabel(column.capitalize())
        ax.grid(axis='x')

        plt.tight_layout()
        return fig

    def plot_multiple_properties_over_time(
        self,
        data_list: list,
        legend_title: str,
        color_dict: dict = None,
        figsize: tuple = (16, 8),
        legend_position: tuple = (1, 1),
        legend_size_position: tuple = (1, 0),
        central_tendency: str = "mean",
        error_type: str = "se",
        error_display: str = None,
        iqr_filter: bool = True,
        iqr_lower_quantile: float = 0.25,
        iqr_upper_quantile: float = 0.75,
        iqr_multiplier: float = 1.5,
        font_size: int = 14,
        number_xticks: int = 5,
        point_size_range: tuple = (50, 200),
        bubble_value_clip: tuple = None,
        bubble_legend_values: list = None,
        temporal_col: str = "temporal_scope",
        publicationyear_col: str = "publication_year",
        min_datapoints_per_year: int = 5,
        min_papers_per_year: int = None,
        show_log_regression: bool = False,
        regression_year_range: tuple = None,
        doi_col: str = "DOI",
        source_col: str = "Source",
        print_summary: bool = True,
        full_text_only: bool = False,
        corpus_note: bool = True,
    ):
        """
        Plot properties over time with customizable styling and statistics.

        Args:
            data_list: List of dicts with 'df', 'entity_col', 'value_col', 'ylabel', 'title',
                       and optionally:
                       - 'additional_data' (DataFrame with columns 'year', 'entity', 'value')
                         which is plotted as raw dashed lines
                       - 'year_range' (tuple of min, max year) to set the x-axis range
                       - 'y_range' (tuple of min, max value) to set the y-axis range
                       - 'min_datapoints_per_year' (int) to override global min for this entry
                       - 'min_papers_per_year' (int) to override global min for this entry
                       - 'number_xticks' (int) to override global x-tick interval for this entry
                                             - 'show_log_regression' (bool) to override global log-regression toggle
                                             - 'regression_year_range' (tuple min_year, max_year) to override
                                                 global regression interval for this entry
            legend_title: Title for the color legend.
            color_dict: Optional color mapping for entities.
            figsize: Figure size.
            legend_position: Position for color legend.
            legend_size_position: Position for size legend.
            central_tendency: 'mean', 'median', or 'moving average'.
            error_type: 'se' (standard error) or 'ci' (confidence interval).
            error_display: 'bars', 'shade', or None.
            iqr_filter: Whether to remove outliers using IQR.
            iqr_lower_quantile: Lower quantile for IQR filter (default 0.25 = Q1).
            iqr_upper_quantile: Upper quantile for IQR filter (default 0.75 = Q3).
            iqr_multiplier: Multiplier for IQR fence (default 1.5, Tukey method).
            font_size: Font size for labels.
            number_xticks: Interval for x-axis ticks.
            point_size_range: Range for marker sizes (min, max).
            bubble_value_clip: Optional tuple (min_n, max_n) for bubble scaling.
                Values below min_n use minimum bubble size; values above max_n
                use maximum bubble size.
            bubble_legend_values: Optional list of sample sizes (n) that should
                be shown in the size legend.
            temporal_col: Column containing temporal scope.
            publicationyear_col: Column containing publication year.
            min_datapoints_per_year: Minimum data points required per year.
            min_papers_per_year: Minimum unique papers required per year.
            show_log_regression: Whether to overlay a log-linear regression per entity.
                The regression is fitted as ln(y) = a + b*year and visualized as
                y_hat = exp(a + b*year).
            regression_year_range: Optional tuple (min_year, max_year) limiting years
                used for regression fit.
            doi_col: Default DOI column used to count contributing studies.
                Can be overridden per entry via data['doi_col'].
            source_col: Default column containing the text source, used to split
                contributing studies into full text and abstract-only.
                Can be overridden per entry via data['source_col'].
            print_summary: Whether to print temporal filter and DOI summary stats.
            full_text_only: If True, only records from full-text publications are
                used. The restriction is applied before any filtering, so IQR
                filter, thresholds, aggregates, regression lines and the returned
                data tables (and statistics computed from them) all refer to
                full-text publications only. 'additional_data' (external reference
                series) is not affected.
            corpus_note: Whether to add a note stating the corpus and the number of
                contributing publications below the figure (see add_corpus_note).

        Returns:
            Tuple of (fig, data_tables) where:
                - fig: Matplotlib figure
                - data_tables: Dictionary mapping subplot titles to their aggregated data (DataFrames)
        """
        set_font_sizes(font_size)

        if full_text_only:
            data_list = restrict_datasets_to_full_text(data_list, doi_col, source_col)

        n_plots = len(data_list)
        ncols = 2 if n_plots > 1 else 1
        nrows = math.ceil(n_plots / ncols)

        fig, axes = plt.subplots(nrows, ncols, figsize=figsize, sharey=False)
        axes = flatten_axes(axes, n_plots)

        # Prepare data and get global parameters
        prepared_data = self._prepare_temporal_data(
            data_list,
            iqr_filter,
            iqr_lower_quantile,
            iqr_upper_quantile,
            iqr_multiplier,
            temporal_col,
            publicationyear_col,
            min_papers_per_year,
            min_datapoints_per_year,
            central_tendency,
            error_type,
            doi_col,
            source_col,
        )

        if print_summary:
            self._print_temporal_generation_summary(prepared_data, iqr_filter)

        all_entities, all_n_vals, color_dict = self._get_global_plot_params(
            prepared_data, color_dict
        )

        min_n, max_n = self._resolve_temporal_size_scale(all_n_vals, bubble_value_clip)

        # Plot each subplot and collect data tables
        data_tables = {}
        for i, (ax, data) in enumerate(zip(axes, data_list)):
            agg_df = prepared_data[i]['agg_df']
            entity_col = data['entity_col']
            ylabel = data['ylabel']
            title = data.get('title', '')
            xticks = data.get('number_xticks', number_xticks)

            additional_data = data.get('additional_data', None)
            year_range = data.get('year_range', None)
            y_range = data.get('y_range', None)
            show_reg = data.get('show_log_regression', show_log_regression)
            reg_year_range = data.get('regression_year_range', regression_year_range)

            self._plot_temporal_subplot(
                ax, agg_df, entity_col, color_dict,
                min_n, max_n, point_size_range,
                error_type, error_display, ylabel, title, xticks,
                additional_data=additional_data,
                year_range=year_range,
                y_range=y_range,
                show_log_regression=show_reg,
                regression_year_range=reg_year_range,
            )

            # Store the aggregated data for this subplot
            data_tables[title] = agg_df

        # Add legends
        self._add_temporal_legends(
            fig, all_entities, all_n_vals, color_dict,
            legend_title, legend_position, legend_size_position, point_size_range,
            min_n=min_n, max_n=max_n, bubble_legend_values=bubble_legend_values
        )

        plt.tight_layout()

        # Contributing DOIs of this figure, e.g. to merge with other figures
        # (see save_text_availability_split).
        total_split = merge_text_availability_splits(
            [data['text_availability'] for data in prepared_data]
        )
        self.last_contributing_split = total_split

        if corpus_note:
            note = describe_corpus('full_text' if full_text_only else 'all', split=total_split)
            add_corpus_note(fig, note)
            print(note)

        return fig, data_tables

    def _prepare_temporal_data(
        self,
        data_list: list,
        iqr_filter: bool,
        iqr_lower_quantile: float,
        iqr_upper_quantile: float,
        iqr_multiplier: float,
        temporal_col: str,
        publicationyear_col: str,
        min_papers_per_year: int,
        min_datapoints_per_year: int,
        central_tendency: str,
        error_type: str,
        doi_col: str,
        source_col: str = "Source",
    ) -> list:
        """Prepare data for temporal plots.

        Each entry in data_list can override min_papers_per_year and min_datapoints_per_year.
        """
        prepared = []

        for data in data_list:
            df = data['df'].copy()
            entity_col = data['entity_col']
            value_col = data['value_col']
            title = data.get('title', '')
            entry_doi_col = self._resolve_existing_column(
                df,
                [data.get('doi_col', doi_col), 'DOI', 'doi']
            )
            entry_source_col = self._resolve_existing_column(
                df,
                [data.get('source_col', source_col), 'Source', 'source_url']
            )

            # Allow per-entry override of min thresholds
            entry_min_papers = data.get('min_papers_per_year', min_papers_per_year)
            entry_min_datapoints = data.get('min_datapoints_per_year', min_datapoints_per_year)

            rows_before_iqr = len(df)

            if iqr_filter:
                df = apply_iqr_filter(df, value_col, entity_col,
                                      lower_quantile=iqr_lower_quantile,
                                      upper_quantile=iqr_upper_quantile,
                                      iqr_multiplier=iqr_multiplier)

            rows_after_iqr = len(df)
            iqr_removed_rows = rows_before_iqr - rows_after_iqr

            df = parse_temporal_scope(df, temporal_col, publicationyear_col)
            df = filter_by_min_papers(df, 'jahr', min_papers=entry_min_papers)

            agg_df = calculate_aggregates(
                df, entity_col, value_col, 'jahr', central_tendency, error_type
            )
            agg_df = agg_df[agg_df['n'] >= entry_min_datapoints]

            if agg_df.empty:
                contributing_df = df.iloc[0:0]
            else:
                included_groups = agg_df[['jahr', entity_col]].drop_duplicates()
                contributing_df = df.merge(included_groups, on=['jahr', entity_col], how='inner')

            if entry_doi_col is not None and entry_doi_col in contributing_df.columns:
                contributing_dois = set(
                    contributing_df[entry_doi_col]
                    .dropna()
                    .astype(str)
                    .str.strip()
                )
                contributing_dois.discard('')
            else:
                contributing_dois = set()

            text_availability = split_dois_by_text_availability(
                contributing_df, contributing_dois, entry_doi_col, entry_source_col
            )

            prepared.append({
                'df': df,
                'agg_df': agg_df,
                'entity_col': entity_col,
                'value_col': value_col,
                'title': title,
                'doi_col': entry_doi_col,
                'rows_before_iqr': rows_before_iqr,
                'rows_after_iqr': rows_after_iqr,
                'iqr_removed_rows': iqr_removed_rows,
                'contributing_dois': contributing_dois,
                'text_availability': text_availability,
            })

        return prepared

    def _resolve_existing_column(self, df: pd.DataFrame, candidates: list) -> str | None:
        """Return first matching column from candidates (case-insensitive)."""
        if df is None or df.empty:
            return None

        lower_to_original = {col.lower(): col for col in df.columns}
        for candidate in candidates:
            if not candidate:
                continue
            if candidate in df.columns:
                return candidate
            resolved = lower_to_original.get(str(candidate).lower())
            if resolved is not None:
                return resolved
        return None

    def _print_temporal_generation_summary(self, prepared_data: list, iqr_filter: bool):
        """Print per-dataset filter stats and overall unique DOI contribution."""
        print("\n=== Temporal Plot Generation Summary ===")

        total_unique_dois = set()
        dataset_splits = []
        doi_available_any = False

        for idx, data in enumerate(prepared_data, start=1):
            title = data.get('title') or f"Dataset {idx}"
            removed = int(data.get('iqr_removed_rows', 0))
            before = int(data.get('rows_before_iqr', 0))
            after = int(data.get('rows_after_iqr', 0))

            if iqr_filter:
                print(
                    f"[{idx}] {title} | IQR removed: {removed} values "
                    f"(before={before}, after={after})"
                )
            else:
                print(f"[{idx}] {title} | IQR filter disabled")

            doi_col = data.get('doi_col')
            dataset_dois = data.get('contributing_dois', set())
            if doi_col is None:
                print("    Contributing studies: DOI column not found")
                continue

            doi_available_any = True
            total_unique_dois.update(dataset_dois)
            dataset_split = data['text_availability']
            dataset_splits.append(dataset_split)
            print(
                f"    Contributing studies ({doi_col}): "
                f"{len(dataset_dois)} unique DOI(s) "
                f"({format_text_availability_counts(dataset_split)})"
            )

        if doi_available_any:
            total_split = merge_text_availability_splits(dataset_splits)
            print(
                "Total contributing studies in this generated figure: "
                f"{len(total_unique_dois)} unique DOI(s) "
                f"({format_text_availability_counts(total_split)})"
            )
        else:
            print("Total contributing studies in this generated figure: DOI column unavailable")

    def _get_global_plot_params(
        self,
        prepared_data: list,
        color_dict: dict
    ) -> tuple:
        """Get global parameters across all subplots."""
        all_entities = []
        all_n_vals = []

        for data in prepared_data:
            agg_df = data['agg_df']
            entity_col = data['entity_col']
            all_entities.extend(agg_df[entity_col].unique())
            all_n_vals.extend(agg_df['n'].dropna().astype(int).unique())

        all_entities = sorted(list(set(all_entities)))
        all_n_vals = sorted(list(set(all_n_vals)))

        if color_dict is None:
            color_dict = create_entity_color_palette(all_entities)

        return all_entities, all_n_vals, color_dict

    def _resolve_temporal_size_scale(self, all_n_vals: list, bubble_value_clip: tuple = None) -> tuple:
        """Resolve min/max n used for temporal bubble-size mapping."""
        if not all_n_vals:
            raise ValueError("No temporal data available for bubble-size scaling.")

        data_min, data_max = float(min(all_n_vals)), float(max(all_n_vals))
        if bubble_value_clip is None:
            return data_min, data_max

        if len(bubble_value_clip) != 2:
            raise ValueError("bubble_value_clip must be a tuple of (min_n, max_n).")

        lower, upper = bubble_value_clip
        if lower is None or upper is None:
            raise ValueError("bubble_value_clip values cannot be None.")

        lower = float(lower)
        upper = float(upper)
        if lower > upper:
            lower, upper = upper, lower
        if lower == upper:
            upper = lower + 1.0

        return lower, upper

    def _plot_temporal_subplot(
        self,
        ax,
        agg_df: pd.DataFrame,
        entity_col: str,
        color_dict: dict,
        min_n: float,
        max_n: float,
        size_range: tuple,
        error_type: str,
        error_display: str,
        ylabel: str,
        title: str,
        number_xticks: int,
        additional_data: pd.DataFrame = None,
        year_range: tuple = None,
        y_range: tuple = None,
        show_log_regression: bool = False,
        regression_year_range: tuple = None,
    ):
        """Plot a single temporal subplot."""
        # Map sizes
        agg_df = agg_df.copy()
        n_for_scaling = agg_df['n'].fillna(min_n).clip(lower=min_n, upper=max_n)
        agg_df['size_mapped'] = map_values_to_sizes(
            n_for_scaling.values, min_n, max_n, size_range
        )

        # Line plot
        sns.lineplot(
            data=agg_df,
            x='jahr', y='value_central',
            hue=entity_col, palette=color_dict, ax=ax
        )

        # Scatter plot
        ax.scatter(
            agg_df['jahr'], agg_df['value_central'],
            s=agg_df['size_mapped'],
            c=agg_df[entity_col].map(color_dict),
            edgecolor='w', linewidth=0.3, alpha=0.9
        )

        # Error display
        if error_display:
            self._add_error_display(ax, agg_df, entity_col, color_dict, error_type, error_display)

        # Optional per-entity log-linear regression overlays with %/yr slope annotation.
        if show_log_regression:
            self._add_log_regression_overlays(
                ax=ax,
                agg_df=agg_df,
                entity_col=entity_col,
                color_dict=color_dict,
                regression_year_range=regression_year_range,
                additional_data=additional_data,
            )

        # Styling
        ax.set_xlabel('Year')
        ax.set_ylabel(ylabel)
        ax.grid(linestyle='--', alpha=0.6)
        ax.xaxis.set_major_locator(mticker.MultipleLocator(number_xticks))
        ax.set_title(title, loc='left', fontweight='bold')

        # Set x-axis range if provided
        if year_range is not None:
            ax.set_xlim(year_range[0], year_range[1])

        # Set y-axis range if provided
        if y_range is not None:
            ax.set_ylim(y_range[0], y_range[1])

        # Additional data (raw values, dashed lines)
        if additional_data is not None:
            for entity in additional_data['entity'].unique():
                entity_df = additional_data[additional_data['entity'] == entity].sort_values('year')
                color = color_dict.get(entity, 'gray')
                ax.plot(
                    entity_df['year'], entity_df['value'],
                    color=color, linestyle='--', linewidth=6, alpha=0.8
                )

        if ax.get_legend() is not None:
            ax.get_legend().remove()

    def _add_log_regression_overlays(
        self,
        ax,
        agg_df: pd.DataFrame,
        entity_col: str,
        color_dict: dict,
        regression_year_range: tuple = None,
        additional_data: pd.DataFrame = None,
    ):
        """Add per-entity log-linear regression lines."""
        fit_df = agg_df.copy()
        add_df = None

        if regression_year_range is not None:
            if len(regression_year_range) != 2:
                raise ValueError("regression_year_range must be a tuple of (min_year, max_year).")
            start_year, end_year = regression_year_range
            if start_year is None or end_year is None:
                raise ValueError("regression_year_range values cannot be None.")
            start_year = float(start_year)
            end_year = float(end_year)
            if start_year > end_year:
                start_year, end_year = end_year, start_year
            fit_df = fit_df[(fit_df['jahr'] >= start_year) & (fit_df['jahr'] <= end_year)]

        if additional_data is not None:
            required_cols = {'year', 'entity', 'value'}
            if required_cols.issubset(additional_data.columns):
                add_df = additional_data.copy()
                add_df['year'] = pd.to_numeric(add_df['year'], errors='coerce')
                add_df['value'] = pd.to_numeric(add_df['value'], errors='coerce')
                add_df = add_df.dropna(subset=['year', 'entity', 'value'])
                add_df = add_df[add_df['value'] > 0]
                if regression_year_range is not None:
                    add_df = add_df[(add_df['year'] >= start_year) & (add_df['year'] <= end_year)]
                add_df = add_df.groupby(['entity', 'year'], as_index=False)['value'].mean()

        for entity in fit_df[entity_col].dropna().unique():
            entity_df = fit_df[fit_df[entity_col] == entity].copy()
            entity_df = entity_df.sort_values('jahr')
            entity_df = entity_df[np.isfinite(entity_df['value_central'])]
            entity_df = entity_df[entity_df['value_central'] > 0]

            if len(entity_df) < 2:
                continue

            x = entity_df['jahr'].astype(float).to_numpy()
            y = entity_df['value_central'].astype(float).to_numpy()

            slope_log, intercept_log = np.polyfit(x, np.log(y), 1)
            y_hat = np.exp(intercept_log + slope_log * x)

            color = color_dict.get(entity, 'gray')
            ax.plot(x, y_hat, linestyle='--', linewidth=2.0, color=color, alpha=0.9)

        if add_df is not None:
            for entity in add_df['entity'].dropna().unique():
                entity_df = add_df[add_df['entity'] == entity].copy()
                entity_df = entity_df.sort_values('year')
                entity_df = entity_df[np.isfinite(entity_df['value'])]
                entity_df = entity_df[entity_df['value'] > 0]

                if len(entity_df) < 2:
                    continue

                x = entity_df['year'].astype(float).to_numpy()
                y = entity_df['value'].astype(float).to_numpy()

                slope_log, intercept_log = np.polyfit(x, np.log(y), 1)
                y_hat = np.exp(intercept_log + slope_log * x)

                color = color_dict.get(entity, 'gray')
                ax.plot(x, y_hat, linestyle=':', linewidth=2.0, color=color, alpha=0.9)

    def calculate_log_regression_metrics(
        self,
        fit_df: pd.DataFrame,
        additional_df: pd.DataFrame = None,
        entity_col: str = 'entity',
        regression_year_range: tuple = None,
    ) -> list[str]:
        """Return regression slope (%/yr) and MAE labels for two input DataFrames."""
        metrics_module = importlib.import_module(
            'quinex_application.visualisation.regression_metrics'
        )
        return metrics_module.build_log_regression_metric_labels(
            fit_df=fit_df,
            entity_col=entity_col,
            additional_df=additional_df,
            regression_year_range=regression_year_range,
        )

    def _calculate_mean_absolute_error(
        self,
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

    def _add_error_display(
        self,
        ax,
        agg_df: pd.DataFrame,
        entity_col: str,
        color_dict: dict,
        error_type: str,
        error_display: str
    ):
        """Add error bars or shading to plot."""
        for entity in agg_df[entity_col].unique():
            entity_df = agg_df[agg_df[entity_col] == entity].copy()

            if error_display == "bars":
                self._add_error_bars(ax, entity_df, error_type)
            elif error_display == "shade":
                self._add_error_shade(ax, entity_df, color_dict[entity], error_type)

    def _add_error_bars(self, ax, entity_df: pd.DataFrame, error_type: str):
        """Add error bars to plot."""
        if error_type == "se" and 'se' in entity_df.columns:
            yerr = entity_df['se']
        elif error_type == "ci" and 'ci' in entity_df.columns:
            yerr = entity_df['ci']
        else:
            return

        ax.errorbar(
            x=entity_df['jahr'], y=entity_df['value_central'],
            yerr=yerr, fmt='none',
            ecolor='gray', elinewidth=1, capsize=3, alpha=0.6
        )

    def _add_error_shade(self, ax, entity_df: pd.DataFrame, color, error_type: str):
        """Add error shading to plot."""
        entity_df = entity_df.sort_values('jahr')

        if error_type == "se" and 'se' in entity_df.columns:
            lower = entity_df['value_central'] - entity_df['se']
            upper = entity_df['value_central'] + entity_df['se']
        elif error_type == "ci" and 'ci_lower' in entity_df.columns:
            lower = entity_df['ci_lower']
            upper = entity_df['ci_upper']
        else:
            return

        ax.fill_between(entity_df['jahr'], lower, upper, color=color, alpha=0.2)

    def _add_temporal_legends(
        self,
        fig,
        all_entities: list,
        all_n_vals: list,
        color_dict: dict,
        legend_title: str,
        legend_position: tuple,
        legend_size_position: tuple,
        size_range: tuple,
        min_n: float,
        max_n: float,
        bubble_legend_values: list = None,
    ):
        """Add color and size legends to temporal plot."""
        # Color legend
        handles = create_line_legend_handles(all_entities, color_dict)
        fig.legend(
            handles=handles, labels=all_entities,
            title=legend_title, bbox_to_anchor=legend_position, loc='upper left'
        )

        # Size legend
        if bubble_legend_values is not None:
            legend_values = [v for v in bubble_legend_values if pd.notna(v)]
        else:
            sorted_vals = np.sort(np.unique(all_n_vals))
            if len(sorted_vals) >= 3:
                legend_values = [sorted_vals[0], int(np.median(sorted_vals)), sorted_vals[-1]]
            elif len(sorted_vals) == 2:
                legend_values = [sorted_vals[0], sorted_vals[1]]
            elif len(sorted_vals) == 1:
                legend_values = [sorted_vals[0]]
            else:
                legend_values = [min_n, max_n]

        size_handles = self._create_temporal_size_legend_handles(
            legend_values=legend_values,
            min_n=min_n,
            max_n=max_n,
            size_range=size_range,
        )
        fig.legend(
            handles=size_handles, title='Sample Size',
            bbox_to_anchor=legend_size_position, loc='upper left'
        )

    def _create_temporal_size_legend_handles(
        self,
        legend_values: list,
        min_n: float,
        max_n: float,
        size_range: tuple,
    ) -> list:
        """Create size legend handles consistent with temporal bubble scaling."""
        if not legend_values:
            return []

        legend_values = list(dict.fromkeys(legend_values))
        legend_array = np.asarray(legend_values, dtype=float)
        clipped = np.clip(legend_array, min_n, max_n)
        mapped_sizes = map_values_to_sizes(clipped, min_n, max_n, size_range)

        handles = []
        for original_value, mapped_size in zip(legend_values, mapped_sizes):
            if float(original_value).is_integer():
                label_value = str(int(original_value))
            else:
                label_value = f"{float(original_value):.2f}"

            handles.append(
                plt.Line2D(
                    [], [],
                    marker='o',
                    linestyle='None',
                    markersize=np.sqrt(mapped_size),
                    markerfacecolor='gray',
                    markeredgecolor='none',
                    alpha=0.6,
                    label=f'n = {label_value}'
                )
            )

        return handles
