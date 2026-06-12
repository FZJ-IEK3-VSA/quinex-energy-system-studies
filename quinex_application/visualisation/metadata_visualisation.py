"""
Metadata visualization module for research paper analysis.

This module provides visualization functions for analyzing metadata
from research papers, including country distributions, journal metrics,
and temporal trends.
"""

import ast
import glob
import os
import re
import math
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.cm import ScalarMappable
from matplotlib.ticker import PercentFormatter

from quinex_application.postprocessing.country_codes import ISO3_TO_ISO2
from quinex_application.visualisation.plot_utils import (
    set_font_sizes,
    setup_plotting_environment,
    flatten_axes,
    hide_empty_axes,
)
from quinex_application.postprocessing.data_processing import map_to_keyword_group


class VisualisationMetadata:
    """
    Visualizes metadata from research papers including country distributions,
    journal impact factors, and temporal trends.
    """
    
    # Use the centralized country code mapping
    ISO3_TO_ISO2 = ISO3_TO_ISO2
    
    def __init__(self, df_path: str):
        """
        Initialize the visualization settings.
        
        Args:
            df_path: Path to the parquet file containing paper metadata.
        """
        self.df_path = df_path
        self._population_cache = None
        self._gdp_cache = None

        pd.set_option('display.max_colwidth', None)
        setup_plotting_environment()
    
    def load_df(self, query: str, date: str):
        """
        Load and filter DataFrame based on query and date.
        
        Args:
            query: Query identifier.
            date: Date identifier.
        """
        self.df = pd.read_parquet(self.df_path)
        self.df = self.df[self.df[f"{query}_{date}"] == True]

    # =========================================================================
    # Data Loading Methods
    # =========================================================================

    def _load_population_data(self, population_excel_path: str) -> pd.DataFrame:
        """
        Load UN World Population Prospects data from local Excel file.
        
        Args:
            population_excel_path: Path to the WPP2024 Excel file.
            
        Returns:
            DataFrame with population data by country and year.
        """
        if self._population_cache is not None:
            return self._population_cache
        
        print(f"Loading UN World Population Prospects data from {population_excel_path}...")
        
        df_pop = self._read_population_excel(population_excel_path)
        df_pop = self._process_population_data(df_pop)
        
        self._population_cache = df_pop
        print(f"Loaded population data for {df_pop['countries'].nunique()} countries, "
              f"years {df_pop['year'].min()}-{df_pop['year'].max()}")
        
        return df_pop

    def _read_population_excel(self, path: str) -> pd.DataFrame:
        """Read and combine population data from Excel sheets."""
        df_estimates = pd.read_excel(path, sheet_name='Estimates', header=16)
        df_medium = pd.read_excel(path, sheet_name='Medium variant', header=16)
        return pd.concat([df_estimates, df_medium], ignore_index=True)

    def _process_population_data(self, df_pop: pd.DataFrame) -> pd.DataFrame:
        """Process raw population data into standardized format."""
        df_pop = df_pop[[
            'ISO2 Alpha-code', 
            'Year', 
            'Total Population, as of 1 January (thousands)'
        ]].copy()
        
        df_pop.columns = ['countries', 'year', 'population']
        df_pop = df_pop[df_pop['countries'].notna()].copy()
        df_pop['population'] = df_pop['population'] * 1000
        
        # Calculate world population and shares
        world_pop = df_pop.groupby('year')['population'].sum().reset_index()
        world_pop.columns = ['year', 'world_population']
        
        df_pop = df_pop.merge(world_pop, on='year', how='left')
        df_pop['population_share'] = df_pop['population'] / df_pop['world_population']
        df_pop['year'] = df_pop['year'].astype(int)
        
        return df_pop

    def _load_gdp_data(self, gdp_excel_path: str) -> pd.DataFrame:
        """
        Load World Bank GDP data from local Excel file.
        
        Args:
            gdp_excel_path: Path to the World Bank GDP Excel file.
            
        Returns:
            DataFrame with GDP data by country and year.
        """
        if self._gdp_cache is not None:
            return self._gdp_cache
        
        print(f"Loading World Bank GDP data from {gdp_excel_path}...")
        
        df_gdp = self._read_gdp_excel(gdp_excel_path)
        df_gdp = self._process_gdp_data(df_gdp)
        
        self._gdp_cache = df_gdp
        print(f"Loaded GDP data for {df_gdp['countries'].nunique()} countries, "
              f"years {df_gdp['year'].min()}-{df_gdp['year'].max()}")
        
        return df_gdp

    def _read_gdp_excel(self, path: str) -> pd.DataFrame:
        """Read GDP data from Excel file."""
        return pd.read_excel(path, header=3)

    def _process_gdp_data(self, df_gdp: pd.DataFrame) -> pd.DataFrame:
        """Process raw GDP data into standardized format."""
        year_columns = self._extract_year_columns(df_gdp)
        
        df_gdp = df_gdp.melt(
            id_vars=['Country Name', 'Country Code'],
            value_vars=year_columns,
            var_name='year',
            value_name='gdp'
        )
        
        df_gdp['countries'] = df_gdp['Country Code'].map(self.ISO3_TO_ISO2)
        df_gdp = df_gdp[df_gdp['countries'].notna()].copy()
        df_gdp = df_gdp[df_gdp['gdp'].notna()].copy()
        df_gdp['year'] = pd.to_numeric(df_gdp['year'], errors='coerce').astype(int)
        
        # Calculate world GDP and shares
        world_gdp = df_gdp.groupby('year')['gdp'].sum().reset_index()
        world_gdp.columns = ['year', 'world_gdp']
        
        df_gdp = df_gdp.merge(world_gdp, on='year', how='left')
        df_gdp['gdp_share'] = df_gdp['gdp'] / df_gdp['world_gdp']
        
        return df_gdp[['countries', 'year', 'gdp', 'world_gdp', 'gdp_share']]

    def _extract_year_columns(self, df: pd.DataFrame) -> list:
        """Extract year columns from GDP DataFrame."""
        year_columns = []
        skip_cols = ['Country Name', 'Country Code', 'Indicator Name', 'Indicator Code']
        
        for col in df.columns:
            if col in skip_cols:
                continue
            try:
                year = int(float(col))
                if year >= 1960:
                    year_columns.append(col)
            except (ValueError, TypeError):
                continue
        
        return year_columns

    # =========================================================================
    # Country Share Analysis
    # =========================================================================

    def countries_share_and_sjr(
        self,
        metadata_df: pd.DataFrame,
        top_n_line: int = 10,
        top_n_scatter: int = 20,
        figsize: tuple = (16, 6),
        font_size: int = 12,
        color_map: dict = None,
        legend_loc: str = 'upper right',
        legend_bbox: tuple = None,
        normalize_by_population: bool = False,
        population_excel_path: str = None,
        normalize_by_gdp: bool = False,
        gdp_excel_path: str = None,
        max_year: int = None,
        country_groups: dict = None,
        add_regression_lines: bool = True,
        regression_start_year: int = None,
        regression_end_year: int = None
    ):
        """
        Plot country share of papers and average SJR.
        
        Args:
            metadata_df: DataFrame with paper metadata.
            top_n_line: Number of countries for line plot.
            top_n_scatter: Number of countries for scatter plot.
            figsize: Figure size.
            font_size: Font size for labels.
            color_map: Optional color mapping for countries.
            legend_loc: Legend location.
            legend_bbox: Legend bounding box.
            normalize_by_population: Normalize by population share.
            population_excel_path: Path to population Excel file.
            normalize_by_gdp: Normalize by GDP share.
            gdp_excel_path: Path to GDP Excel file.
            max_year: Maximum year to include.
            country_groups: Dict mapping group names to country code lists.
            add_regression_lines: Draw log-linear trend lines per country in plot a.
            regression_start_year: Optional first year for regression fit.
            regression_end_year: Optional last year for regression fit.
            
        Returns:
            Tuple of (figure, pivot_data, scatter_data).
        """
        # Validate inputs
        self._validate_normalization_params(
            normalize_by_population, 
            normalize_by_gdp,
            population_excel_path,
            gdp_excel_path
        )
        
        set_font_sizes(font_size)

        # Load normalization data if needed
        norm_df, norm_share_col = self._get_normalization_data(
            normalize_by_population,
            normalize_by_gdp,
            population_excel_path,
            gdp_excel_path
        )

        # Prepare data
        metadata_df = self._filter_by_max_year(metadata_df, max_year)
        self._validate_regression_years(regression_start_year, regression_end_year)
        self._print_missing_info(metadata_df)
        df_clean = self._clean_country_data(metadata_df)

        # Calculate shares
        counts_year = self._calculate_country_shares_by_year(df_clean)
        top_countries_line, top_countries_scatter = self._get_top_countries(
            df_clean, counts_year, top_n_line, top_n_scatter, country_groups
        )

        # Apply normalization if needed
        plot_column = self._apply_normalization(
            counts_year, norm_df, norm_share_col,
            normalize_by_population or normalize_by_gdp
        )

        # Prepare plot data
        pivot_share_year = self._prepare_line_plot_data(
            counts_year, top_countries_line, plot_column, country_groups,
            normalize_by_population or normalize_by_gdp, norm_share_col, norm_df
        )
        
        scatter_data = self._prepare_scatter_data(
            df_clean, counts_year, top_countries_scatter, country_groups,
            normalize_by_population or normalize_by_gdp, norm_share_col, norm_df
        )

        # Create plots
        fig = self._create_country_share_figure(
            pivot_share_year, scatter_data, top_countries_line,
            figsize, color_map, legend_loc, legend_bbox,
            normalize_by_population, normalize_by_gdp, country_groups,
            add_regression_lines, regression_start_year, regression_end_year
        )

        return fig, pivot_share_year, scatter_data

    def _validate_normalization_params(
        self,
        normalize_by_population: bool,
        normalize_by_gdp: bool,
        population_path: str,
        gdp_path: str
    ):
        """Validate normalization parameters."""
        if normalize_by_population and normalize_by_gdp:
            raise ValueError("Cannot use both population and GDP normalization.")
        if normalize_by_population and population_path is None:
            raise ValueError("population_excel_path required for population normalization.")
        if normalize_by_gdp and gdp_path is None:
            raise ValueError("gdp_excel_path required for GDP normalization.")

    def _get_normalization_data(
        self,
        normalize_by_population: bool,
        normalize_by_gdp: bool,
        population_path: str,
        gdp_path: str
    ) -> tuple:
        """Load normalization data if needed."""
        if normalize_by_population:
            return self._load_population_data(population_path), 'population_share'
        elif normalize_by_gdp:
            return self._load_gdp_data(gdp_path), 'gdp_share'
        return None, None

    def _filter_by_max_year(self, df: pd.DataFrame, max_year: int) -> pd.DataFrame:
        """Filter DataFrame by maximum year."""
        if max_year is not None:
            return df[df['publication_year'] <= max_year].copy()
        return df

    def _validate_regression_years(self, start_year: int, end_year: int):
        """Validate optional regression year bounds."""
        if start_year is not None and end_year is not None and start_year > end_year:
            raise ValueError("regression_start_year must be <= regression_end_year.")

    def _to_country_list(self, value) -> list:
        """Convert country field to a list of ISO2 country codes."""
        if isinstance(value, list):
            return [str(v).strip() for v in value if pd.notna(v) and str(v).strip()]

        if isinstance(value, tuple):
            return [str(v).strip() for v in value if pd.notna(v) and str(v).strip()]

        if isinstance(value, set):
            return [str(v).strip() for v in value if pd.notna(v) and str(v).strip()]

        if hasattr(value, 'tolist') and not isinstance(value, str):
            value_list = value.tolist()
            if isinstance(value_list, (list, tuple)):
                return [str(v).strip() for v in value_list if pd.notna(v) and str(v).strip()]

        try:
            if pd.isna(value):
                return []
        except (TypeError, ValueError):
            pass

        if isinstance(value, str):
            text = value.strip()
            if not text:
                return []

            if text.startswith("[") and text.endswith("]"):
                try:
                    parsed = ast.literal_eval(text)
                    if isinstance(parsed, (list, tuple)):
                        return [
                            str(v).strip()
                            for v in parsed
                            if pd.notna(v) and str(v).strip()
                        ]
                except (ValueError, SyntaxError):
                    pass

            if "," in text:
                return [part.strip() for part in text.split(",") if part.strip()]

            return [text]

        return [str(value).strip()] if str(value).strip() else []

    def _print_missing_info(self, df: pd.DataFrame):
        """Print information about missing data."""
        total_papers = df['DOI'].nunique()
        country_lists = df['countries'].apply(self._to_country_list)
        missing_papers = df[country_lists.apply(len) == 0]['DOI'].nunique()
        missing_sjr = df['SJR'].isna().sum()
        
        print(f"Missing country info: {missing_papers} papers ({missing_papers/total_papers*100:.2f}%)")
        print(f"Missing SJR info: {missing_sjr} papers ({missing_sjr/total_papers*100:.2f}%)")

    def _clean_country_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean and explode country data."""
        df_clean = df.copy()
        df_clean['countries'] = df_clean['countries'].apply(self._to_country_list)
        df_clean = df_clean[df_clean['countries'].apply(len) > 0].explode('countries')

        sjr_series = df_clean['SJR'].apply(
            lambda x: x.replace(',', '.') if isinstance(x, str) else x
        )
        df_clean['SJR'] = pd.to_numeric(sjr_series, errors='coerce')
        return df_clean

    def _calculate_country_shares_by_year(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate country shares by publication year."""
        total_per_year = df.groupby('publication_year')['DOI'].nunique()
        counts = df.groupby(['publication_year', 'countries'])['DOI'].nunique().reset_index(name='count')
        counts['share'] = counts.apply(
            lambda row: row['count'] / total_per_year[row['publication_year']], 
            axis=1
        )
        return counts

    def _get_top_countries(
        self,
        df_clean: pd.DataFrame,
        counts_year: pd.DataFrame,
        top_n_line: int,
        top_n_scatter: int,
        country_groups: dict
    ) -> tuple:
        """Get top countries for line and scatter plots."""
        total_papers = df_clean['DOI'].nunique()
        counts_total = df_clean.groupby('countries')['DOI'].nunique().reset_index(name='count')
        counts_total['share'] = counts_total['count'] / total_papers

        # Determine countries in groups
        countries_in_groups = set()
        if country_groups is not None:
            for country_list in country_groups.values():
                countries_in_groups.update(country_list)

        # Top countries for line plot
        if country_groups is not None:
            countries_outside_groups = counts_total[~counts_total['countries'].isin(countries_in_groups)]
            n_individual = top_n_line - len(country_groups)
            top_line = countries_outside_groups.nlargest(n_individual, 'share')['countries'].tolist()
            top_line = list(country_groups.keys()) + top_line
        else:
            top_line = counts_total.nlargest(top_n_line, 'share')['countries'].tolist()

        # Top countries for scatter plot
        top_scatter = counts_total.nlargest(top_n_scatter, 'share')['countries'].tolist()

        return top_line, top_scatter

    def _apply_normalization(
        self,
        counts_year: pd.DataFrame,
        norm_df: pd.DataFrame,
        norm_share_col: str,
        normalize: bool
    ) -> str:
        """Apply normalization to yearly counts."""
        if not normalize:
            return 'share'

        counts_year_merged = counts_year.merge(
            norm_df[['countries', 'year', norm_share_col]],
            left_on=['countries', 'publication_year'],
            right_on=['countries', 'year'],
            how='left'
        )
        
        # Update the original DataFrame
        counts_year['normalized_share'] = (
            counts_year_merged['share'] / counts_year_merged[norm_share_col]
        ).fillna(0)
        
        return 'normalized_share'

    def _prepare_line_plot_data(
        self,
        counts_year: pd.DataFrame,
        top_countries: list,
        plot_column: str,
        country_groups: dict,
        normalize: bool,
        norm_share_col: str,
        norm_df: pd.DataFrame = None
    ) -> pd.DataFrame:
        """Prepare pivot data for line plot."""
        counts_top = counts_year[counts_year['countries'].isin(top_countries)]
        pivot = counts_top.pivot(
            index='publication_year', 
            columns='countries', 
            values=plot_column
        ).fillna(0)

        # Aggregate groups if provided
        if country_groups is not None:
            pivot = self._aggregate_country_groups(
                pivot, counts_year, country_groups, plot_column, 
                normalize, norm_share_col, norm_df
            )

        return pivot

    def _aggregate_country_groups(
        self,
        pivot: pd.DataFrame,
        counts_year: pd.DataFrame,
        country_groups: dict,
        plot_column: str,
        normalize: bool,
        norm_share_col: str,
        norm_df: pd.DataFrame = None
    ) -> pd.DataFrame:
        """Aggregate country groups for line plot."""
        for group_name, country_list in country_groups.items():
            if group_name in pivot.columns:
                continue

            group_data = counts_year[counts_year['countries'].isin(country_list)].copy()
            
            if normalize and norm_share_col and norm_df is not None:
                # Merge normalization data
                group_data = group_data.merge(
                    norm_df[['countries', 'year', norm_share_col]],
                    left_on=['countries', 'publication_year'],
                    right_on=['countries', 'year'],
                    how='left'
                )
                # Sum raw shares and normalization shares, then divide
                agg = group_data.groupby('publication_year').agg(
                    share_sum=('share', 'sum'),
                    norm_share_sum=(norm_share_col, 'sum')
                ).reset_index()
                agg[plot_column] = (agg['share_sum'] / agg['norm_share_sum']).fillna(0)
            else:
                agg = group_data.groupby('publication_year').agg(
                    **{plot_column: (plot_column, 'sum')}
                ).reset_index()

            pivot[group_name] = agg.set_index('publication_year')[plot_column]
            pivot[group_name] = pivot[group_name].fillna(0)

        return pivot

    def _prepare_scatter_data(
        self,
        df_clean: pd.DataFrame,
        counts_year: pd.DataFrame,
        top_countries: list,
        country_groups: dict,
        normalize: bool,
        norm_share_col: str,
        norm_df: pd.DataFrame = None
    ) -> pd.DataFrame:
        """Prepare data for scatter plot."""
        df_top = df_clean[df_clean['countries'].isin(top_countries)].copy()
        total_papers = df_clean['DOI'].nunique()

        if normalize:
            scatter_data = counts_year[counts_year['countries'].isin(top_countries)].groupby('countries').agg(
                share_of_paper=('normalized_share', 'mean')
            ).reset_index()
            
            sjr_data = df_top.groupby('countries')['SJR'].mean().reset_index()
            sjr_data.columns = ['countries', 'average_sjr']
            scatter_data = scatter_data.merge(sjr_data, on='countries', how='left')
        else:
            scatter_data = df_top.groupby('countries').agg(
                share_of_paper=('DOI', lambda x: x.nunique() / total_papers),
                average_sjr=('SJR', 'mean')
            ).reset_index()

        # Add group aggregates
        if country_groups is not None:
            scatter_data = self._add_group_scatter_data(
                scatter_data, df_clean, counts_year, country_groups, 
                normalize, total_papers, norm_share_col, norm_df
            )

        return scatter_data

    def _add_group_scatter_data(
        self,
        scatter_data: pd.DataFrame,
        df_clean: pd.DataFrame,
        counts_year: pd.DataFrame,
        country_groups: dict,
        normalize: bool,
        total_papers: int,
        norm_share_col: str = None,
        norm_df: pd.DataFrame = None
    ) -> pd.DataFrame:
        """Add aggregated group data to scatter plot data."""
        for group_name, country_list in country_groups.items():
            group_df = df_clean[df_clean['countries'].isin(country_list)]
            group_sjr = group_df['SJR'].mean()

            if normalize:
                group_data = counts_year[
                    (counts_year['countries'].isin(country_list)) &
                    (counts_year['publication_year'].notna())
                ].copy()
                
                if norm_share_col and norm_df is not None:
                    group_data = group_data.merge(
                        norm_df[['countries', 'year', norm_share_col]],
                        left_on=['countries', 'publication_year'],
                        right_on=['countries', 'year'],
                        how='left'
                    )
                    group_share = (group_data['share'] / group_data[norm_share_col]).mean()
                else:
                    group_share = group_data['normalized_share'].mean()
            else:
                group_share = group_df['DOI'].nunique() / total_papers

            scatter_data = pd.concat([scatter_data, pd.DataFrame({
                'countries': [group_name],
                'share_of_paper': [group_share],
                'average_sjr': [group_sjr]
            })], ignore_index=True)

        return scatter_data

    def _create_country_share_figure(
        self,
        pivot_data: pd.DataFrame,
        scatter_data: pd.DataFrame,
        top_countries: list,
        figsize: tuple,
        color_map: dict,
        legend_loc: str,
        legend_bbox: tuple,
        normalize_by_population: bool,
        normalize_by_gdp: bool,
        country_groups: dict,
        add_regression_lines: bool,
        regression_start_year: int,
        regression_end_year: int
    ):
        """Create the country share figure with line and scatter plots."""
        fig, axes = plt.subplots(1, 2, figsize=figsize)
        normalize = normalize_by_population or normalize_by_gdp

        # Line plot
        self._plot_country_lines(
            axes[0], pivot_data, color_map, normalize,
            add_regression_lines, regression_start_year, regression_end_year
        )
        self._style_line_plot(
            axes[0], normalize_by_population, normalize_by_gdp, add_regression_lines
        )

        # Scatter plot
        self._plot_country_scatter(
            axes[1], scatter_data, top_countries, color_map, 
            normalize, country_groups
        )
        self._style_scatter_plot(axes[1], normalize_by_population, normalize_by_gdp)

        # Legend
        self._add_country_legend(fig, axes[0], legend_loc, legend_bbox)

        fig.tight_layout(rect=[0, 0, 0.85, 1])
        return fig

    def _plot_country_lines(
        self,
        ax,
        pivot_data: pd.DataFrame,
        color_map: dict,
        normalize: bool,
        add_regression_lines: bool,
        regression_start_year: int,
        regression_end_year: int
    ):
        """Plot country share lines."""
        for country in pivot_data.columns:
            color = color_map.get(country) if color_map else None

            raw_values = pivot_data[country].astype(float)
            y_values = raw_values if normalize else raw_values * 100
            trend_years, trend_values, percent_per_year = self._fit_log_linear_trend(
                pivot_data.index,
                raw_values,
                regression_start_year,
                regression_end_year
            )

            if percent_per_year is None:
                label = country
            else:
                label = f"{country} ({percent_per_year:+.1f}%/yr)"

            ax.plot(
                pivot_data.index, y_values,
                linestyle='-', marker='o', markersize=0,
                linewidth=2, label=label, color=color
            )

            if add_regression_lines and trend_years is not None and trend_values is not None:
                trend_display = trend_values if normalize else trend_values * 100
                ax.plot(
                    trend_years,
                    trend_display,
                    linestyle='--',
                    linewidth=1.8,
                    color=color,
                    alpha=0.9,
                    label='_nolegend_'
                )

    def _fit_log_linear_trend(
        self,
        years,
        values,
        regression_start_year: int,
        regression_end_year: int
    ) -> tuple:
        """Fit log-linear trend and return fitted values and annual percent change."""
        years_arr = np.asarray(years, dtype=float)
        values_arr = np.asarray(values, dtype=float)

        period_mask = np.ones_like(years_arr, dtype=bool)
        if regression_start_year is not None:
            period_mask &= years_arr >= float(regression_start_year)
        if regression_end_year is not None:
            period_mask &= years_arr <= float(regression_end_year)

        fit_mask = period_mask & np.isfinite(values_arr) & (values_arr > 0)
        if fit_mask.sum() < 2:
            return None, None, None

        x_fit = years_arr[fit_mask]
        y_fit = values_arr[fit_mask]

        slope, intercept = np.polyfit(x_fit, np.log(y_fit), 1)
        annual_percent_change = (math.exp(slope) - 1) * 100

        trend_years = years_arr[period_mask]
        if trend_years.size == 0:
            return None, None, annual_percent_change

        trend_values = np.exp(intercept + slope * trend_years)
        return trend_years, trend_values, annual_percent_change

    def _style_line_plot(
        self,
        ax,
        normalize_by_population: bool,
        normalize_by_gdp: bool,
        add_regression_lines: bool
    ):
        """Style the line plot axis."""
        ax.set_title("a", loc='left', fontweight='bold')
        ax.set_xlabel("Publication Year")
        
        if normalize_by_population:
            ax.set_ylabel("Population-relative\npublications")
        elif normalize_by_gdp:
            ax.set_ylabel("GDP-relative\npublications")
        else:
            ax.set_ylabel("Share of Papers [%]")

        if add_regression_lines:
            ax.text(
                0.01,
                0.98,
                "Dashed: log-linear trend (%/yr in legend)",
                transform=ax.transAxes,
                ha='left',
                va='top',
                fontsize=9,
                alpha=0.8
            )
        
        ax.grid(True, linestyle='--', linewidth=0.7, alpha=0.9)

    def _plot_country_scatter(
        self,
        ax,
        scatter_data: pd.DataFrame,
        top_countries: list,
        color_map: dict,
        normalize: bool,
        country_groups: dict
    ):
        """Plot country scatter points."""
        group_names = set(country_groups.keys()) if country_groups else set()
        rest_labeled = False

        for _, row in scatter_data.iterrows():
            country = row['countries']
            
            # Determine color and label
            if country in top_countries or country in group_names:
                color = color_map.get(country) if color_map else None
                label = country
            else:
                color = 'lightgray'
                label = 'Others' if not rest_labeled else None
                rest_labeled = True

            x_val = row['share_of_paper'] if normalize else row['share_of_paper'] * 100
            ax.scatter(x_val, row['average_sjr'], s=100, label=label, color=color)

    def _style_scatter_plot(self, ax, normalize_by_population: bool, normalize_by_gdp: bool):
        """Style the scatter plot axis."""
        ax.set_title("b", loc='left', fontweight='bold')
        
        if normalize_by_population:
            ax.set_xlabel("Population-relative publications")
        elif normalize_by_gdp:
            ax.set_xlabel("GDP-relative publications")
        else:
            ax.set_xlabel("Share of Papers [%]")
        
        ax.set_ylabel("Average SJR")
        ax.grid(True, linestyle='--', linewidth=0.7, alpha=0.9)

    def _add_country_legend(self, fig, ax, legend_loc: str, legend_bbox: tuple):
        """Add legend to the figure."""
        handles, labels = ax.get_legend_handles_labels()
        if legend_bbox is not None:
            fig.legend(handles, labels, loc='center', bbox_to_anchor=legend_bbox,
                      frameon=True, title='Countries')
        else:
            fig.legend(handles, labels, loc=legend_loc, frameon=True, title='Countries')

    # =========================================================================
    # Keyword Distribution
    # =========================================================================

    def keywords_distribution(
        self,
        quinex_df: pd.DataFrame,
        keywords: dict,
        column: str = "entity",
        figsize: tuple = (10, 6)
    ):
        """
        Plot keyword distribution as a horizontal bar chart.
        
        Args:
            quinex_df: DataFrame with paper data.
            keywords: Dict mapping groups to keyword lists.
            column: Column to search for keywords.
            figsize: Figure size.
            
        Returns:
            Tuple of (figure, percentages Series).
        """
        df = quinex_df.copy()
        all_keywords = [kw for kws in keywords.values() for kw in kws]

        # Filter rows with keywords
        mask = df[column].str.lower().apply(
            lambda x: any(kw.lower() in x for kw in all_keywords)
        )
        df_filtered = df[mask].copy()

        # Map to groups
        df_filtered['keyword_group'] = df_filtered[column].apply(
            lambda x: map_to_keyword_group(x, keywords)
        )

        # Calculate percentages
        unique_per_paper = df_filtered.drop_duplicates(subset=['DOI', 'keyword_group'])
        counts = unique_per_paper['keyword_group'].value_counts()
        total_papers = df['DOI'].nunique()
        percentages = (counts / total_papers * 100).sort_values(ascending=True)

        # Plot
        fig, ax = plt.subplots(figsize=figsize)
        ax.barh(percentages.index, percentages.values, color="steelblue")
        ax.set_xlabel('Percentage of Papers (%)')
        ax.set_ylabel('Technology' if column == 'entity' else 'Property')
        ax.grid(True, linestyle='--', alpha=0.7)
        fig.tight_layout()

        return fig, percentages

    # =========================================================================
    # Heatmap Visualizations
    # =========================================================================

    def mention_trend_heatmap_multi_entities(
        self,
        dfs,
        entity_col: str = "entity_base_mapping",
        year_col: str = "publication_year",
        titles=None,
        top_n: int = 6,
        figsize: tuple = (16, 6),
        cmap: str = "viridis",
        color_scale_percent: tuple = None,
        font_size: int = 12,
        n_cols: int = 2
    ):
        """
        Create multiple heatmaps showing entity mention trends.
        
        Args:
            dfs: DataFrame or list of DataFrames.
            entity_col: Column containing entity names.
            year_col: Column containing publication year.
            titles: List of titles for each subplot.
            top_n: Number of top entities to show.
            figsize: Base figure size.
            cmap: Colormap name.
            color_scale_percent: Optional tuple (min_percent, max_percent) for color scale.
            font_size: Font size.
            n_cols: Number of columns in grid.
            
        Returns:
            Tuple of (figure, list of pivot tables).
        """
        # Normalize inputs
        if not isinstance(dfs, list):
            dfs = [dfs]

        n_plots = len(dfs)
        titles = titles or [f"({chr(97+i)})" for i in range(n_plots)]

        if len(titles) != n_plots:
            raise ValueError("titles must have same length as dfs")

        set_font_sizes(font_size)

        # Calculate global entity ranking and prepare pivots
        global_top_entities = self._get_global_top_entities(dfs, entity_col, year_col, top_n)
        pivots, vmax_global = self._prepare_heatmap_pivots(
            dfs, entity_col, year_col, global_top_entities
        )
        vmin, vmax = self._resolve_color_scale_percent(color_scale_percent, vmax_global)

        # Create figure
        fig, axes = self._create_heatmap_grid(n_plots, n_cols, figsize)

        # Plot heatmaps
        for idx, (ax, pivot, title) in enumerate(zip(axes, pivots, titles)):
            self._plot_single_heatmap(ax, pivot, cmap, vmin, vmax, title)
            self._style_heatmap_axes(ax, idx, n_cols, n_plots)

        hide_empty_axes(axes, n_plots)

        # Add colorbar
        self._add_heatmap_colorbar(fig, axes[:n_plots], cmap, vmin, vmax)

        fig.tight_layout(rect=[0, 0.12, 1, 1])
        return fig, pivots

    def _get_global_top_entities(
        self,
        dfs: list,
        entity_col: str,
        year_col: str,
        top_n: int
    ) -> list:
        """Get globally top entities across all DataFrames."""
        global_scores = {}

        for df in dfs:
            df_temp = df[df[year_col].notnull()].copy()
            df_temp[year_col] = df_temp[year_col].astype(int)

            total_per_year = df_temp.groupby(year_col)['DOI'].nunique()
            counts = df_temp.groupby([year_col, entity_col])['DOI'].nunique().reset_index(name='count')
            counts['share'] = counts.apply(
                lambda r: r['count'] / total_per_year[r[year_col]], axis=1
            )

            entity_sums = counts.groupby(entity_col)['share'].sum()
            for entity, score in entity_sums.items():
                global_scores[entity] = global_scores.get(entity, 0) + score

        return sorted(global_scores.keys(), key=lambda x: global_scores[x], reverse=True)[:top_n]

    def _prepare_heatmap_pivots(
        self,
        dfs: list,
        entity_col: str,
        year_col: str,
        top_entities: list
    ) -> tuple:
        """Prepare pivot tables for heatmaps."""
        pivots = []
        vmax_global = 0

        for df in dfs:
            df = df[df[year_col].notnull()].copy()
            df[year_col] = df[year_col].astype(int)

            total_per_year = df.groupby(year_col)['DOI'].nunique()
            counts = df.groupby([year_col, entity_col])['DOI'].nunique().reset_index(name='count')
            counts['share'] = counts.apply(
                lambda r: r['count'] / total_per_year[r[year_col]], axis=1
            )

            pivot = (
                counts[counts[entity_col].isin(top_entities)]
                .pivot(index=entity_col, columns=year_col, values='share')
                .fillna(0)
            )
            pivot = pivot.reindex([e for e in top_entities if e in pivot.index])

            pivots.append(pivot)
            vmax_global = max(vmax_global, pivot.values.max())

        return pivots, vmax_global

    def _create_heatmap_grid(self, n_plots: int, n_cols: int, figsize: tuple):
        """Create subplot grid for heatmaps."""
        n_rows = math.ceil(n_plots / n_cols)

        fig, axes = plt.subplots(
            n_rows, n_cols,
            figsize=(figsize[0], figsize[1] * n_rows),
            gridspec_kw={'wspace': 0.1, 'hspace': 0.35}
        )

        return fig, flatten_axes(axes, n_plots)

    def _plot_single_heatmap(self, ax, pivot, cmap: str, vmin: float, vmax: float, title: str):
        """Plot a single heatmap."""
        sns.heatmap(
            pivot, ax=ax, cmap=cmap,
            vmin=vmin, vmax=vmax, cbar=False, linewidths=0.5
        )
        ax.set_title(title, loc='left', fontweight='bold')

    def _resolve_color_scale_percent(self, color_scale_percent: tuple, data_vmax: float) -> tuple:
        """Resolve optional percent tuple to heatmap vmin/vmax in share scale (0..1)."""
        if color_scale_percent is None:
            return 0, data_vmax

        if not isinstance(color_scale_percent, tuple) or len(color_scale_percent) != 2:
            raise ValueError("color_scale_percent must be a tuple like (0, 60).")

        min_percent, max_percent = color_scale_percent
        try:
            min_percent = float(min_percent)
            max_percent = float(max_percent)
        except (TypeError, ValueError) as exc:
            raise ValueError("color_scale_percent must contain numeric values.") from exc

        if min_percent < 0 or max_percent < 0:
            raise ValueError("color_scale_percent values must be non-negative.")
        if max_percent <= min_percent:
            raise ValueError("color_scale_percent requires max > min.")

        return min_percent / 100, max_percent / 100

    def _style_heatmap_axes(self, ax, idx: int, n_cols: int, n_plots: int):
        """Style heatmap axes based on position in grid."""
        n_rows = math.ceil(n_plots / n_cols)
        row_idx = idx // n_cols
        col_idx = idx % n_cols
        is_bottom_row = (row_idx == n_rows - 1) or (idx >= n_plots - n_cols)
        is_left_col = (col_idx == 0)

        # Y-axis
        if is_left_col:
            ax.set_ylabel("Technology")
        else:
            ax.set_ylabel("")
            ax.set_yticks([])

        # X-axis
        xticks = ax.get_xticks()
        labels = [l.get_text() for l in ax.get_xticklabels()]

        if is_bottom_row:
            ax.set_xticks(xticks[::4])
            ax.set_xticklabels(labels[::4], rotation=0)
            ax.set_xlabel("Publication Year")
        else:
            ax.set_xticks([])
            ax.set_xticklabels([])
            ax.set_xlabel("")

    def _add_heatmap_colorbar(self, fig, axes, cmap: str, vmin: float, vmax: float):
        """Add shared colorbar to heatmap figure."""
        sm = ScalarMappable(cmap=cmap, norm=plt.Normalize(vmin=vmin, vmax=vmax))
        sm.set_array([])

        cbar = fig.colorbar(
            sm, ax=axes,
            orientation='horizontal',
            pad=0.15, aspect=40, shrink=0.8
        )
        cbar.set_label("Share of Papers [%]")
        cbar.ax.xaxis.set_major_formatter(PercentFormatter(xmax=1))

    def mention_trend_heatmap(
        self,
        quinex_df: pd.DataFrame,
        entity_col: str = "entity_base_mapping",
        property_col: str = "property_base_mapping",
        year_col: str = "publication_year",
        top_n: int = 6,
        figsize: tuple = (16, 6),
        cmap: str = "viridis",
        color_scale_percent: tuple = None,
        font_size: int = 12
    ):
        """
        Plot heatmaps for entity and property mention trends.
        
        Args:
            quinex_df: DataFrame with paper data.
            entity_col: Column containing entity names.
            property_col: Column containing property names.
            year_col: Column containing publication year.
            top_n: Number of top items to show.
            figsize: Figure size.
            cmap: Colormap name.
            color_scale_percent: Optional tuple (min_percent, max_percent) for color scale.
            font_size: Font size.
            
        Returns:
            Tuple of (figure, entity_pivot, property_pivot).
        """
        set_font_sizes(font_size)

        df = quinex_df[quinex_df[year_col].notnull()].copy()
        df[year_col] = df[year_col].astype(int)

        total_per_year = df.groupby(year_col)['DOI'].nunique()

        # Prepare entity and property pivots
        pivot_entity = self._create_mention_pivot(
            df, year_col, entity_col, total_per_year, top_n
        )
        pivot_property = self._create_mention_pivot(
            df, year_col, property_col, total_per_year, top_n
        )

        vmax_data = max(pivot_entity.values.max(), pivot_property.values.max())
        vmin, vmax = self._resolve_color_scale_percent(color_scale_percent, vmax_data)

        # Create figure
        fig, axes = plt.subplots(1, 2, figsize=figsize,
                                  gridspec_kw={'width_ratios': [1, 1], 'wspace': 0.35})

        # Plot heatmaps
        sns.heatmap(pivot_entity, ax=axes[0], cmap=cmap, vmin=vmin, vmax=vmax,
                   cbar=False, linewidths=0.5)
        axes[0].set_title("c", loc='left', fontweight='bold')
        axes[0].set_xlabel("Publication Year")
        axes[0].set_ylabel("Entity")

        sns.heatmap(pivot_property, ax=axes[1], cmap=cmap, vmin=vmin, vmax=vmax,
                   cbar=False, linewidths=0.5)
        axes[1].set_title("d", loc='left', fontweight='bold')
        axes[1].set_xlabel("Publication Year")
        axes[1].set_ylabel("Property")

        # Add colorbar
        sm = ScalarMappable(cmap=cmap, norm=plt.Normalize(vmin=vmin, vmax=vmax))
        sm.set_array([])
        cbar = fig.colorbar(sm, ax=axes, fraction=0.05, pad=0.02)
        cbar.set_label('Share of Papers [%]')
        cbar.ax.yaxis.set_major_formatter(PercentFormatter(xmax=1))

        # Format x-ticks
        for ax in axes:
            self._format_heatmap_xticks(ax, interval=4)

        fig.tight_layout()
        return fig, pivot_entity, pivot_property

    def _create_mention_pivot(
        self,
        df: pd.DataFrame,
        year_col: str,
        value_col: str,
        total_per_year: pd.Series,
        top_n: int
    ) -> pd.DataFrame:
        """Create pivot table for mention trends."""
        counts = df.groupby([year_col, value_col])['DOI'].nunique().reset_index(name='count')
        counts['share'] = counts.apply(
            lambda row: row['count'] / total_per_year[row[year_col]], axis=1
        )

        top_items = counts.groupby(value_col)['share'].sum().nlargest(top_n).index
        counts = counts[counts[value_col].isin(top_items)]

        pivot = counts.pivot(index=value_col, columns=year_col, values='share').fillna(0)
        return pivot.loc[pivot.mean(axis=1).sort_values(ascending=False).index]

    def _format_heatmap_xticks(self, ax, interval: int = 4):
        """Format heatmap x-ticks at specified interval."""
        xticks = ax.get_xticks()
        labels = [item.get_text() for item in ax.get_xticklabels()]
        new_ticks = xticks[::interval]
        new_labels = labels[::interval]
        ax.set_xticks(new_ticks)
        ax.set_xticklabels(new_labels, rotation=0)

    # =========================================================================
    # Sankey Diagram
    # =========================================================================

    def entity_property_sankey(
        self,
        df: pd.DataFrame,
        entity_keywords: dict,
        property_keywords: dict,
        entity_col: str = "entity",
        property_col: str = "property",
        year_col: str = "publication_year",
        top_n_entities: int = 6,
        top_n_properties: int = 6,
        figsize: tuple = (12, 6)
    ):
        """
        Create a Sankey diagram showing entity-property relationships.
        
        Args:
            df: DataFrame with paper data.
            entity_keywords: Dict mapping entity groups to keywords.
            property_keywords: Dict mapping property groups to keywords.
            entity_col: Column containing entity text.
            property_col: Column containing property text.
            year_col: Column containing publication year.
            top_n_entities: Number of top entities to show.
            top_n_properties: Number of top properties to show.
            figsize: Figure size.
            
        Returns:
            Tuple of (figure, link_counts DataFrame).
        """
        df = df[df[year_col].notnull()].copy()
        df[year_col] = df[year_col].astype(int)

        # Map to groups
        df['entity_group'] = df[entity_col].apply(
            lambda x: map_to_keyword_group(x, entity_keywords)
        )
        df['property_group'] = df[property_col].apply(
            lambda x: map_to_keyword_group(x, property_keywords)
        )

        # Filter to papers with both entity and property
        df_filtered = df[df['entity_group'].notna() & df['property_group'].notna()]

        # Get top entities and properties
        top_entities = df_filtered['entity_group'].value_counts().head(top_n_entities).index
        top_properties = df_filtered['property_group'].value_counts().head(top_n_properties).index
        df_filtered = df_filtered[
            df_filtered['entity_group'].isin(top_entities) &
            df_filtered['property_group'].isin(top_properties)
        ]

        # Count links
        link_counts = df_filtered.groupby(
            ['entity_group', 'property_group']
        )['DOI'].nunique().reset_index(name='count')

        # Create Sankey
        all_nodes = list(top_entities) + list(top_properties)
        node_indices = {name: i for i, name in enumerate(all_nodes)}

        fig = go.Figure(data=[go.Sankey(
            node=dict(
                pad=15, thickness=20,
                line=dict(color="black", width=0.5),
                label=all_nodes,
                color="steelblue"
            ),
            link=dict(
                source=link_counts['entity_group'].map(node_indices),
                target=link_counts['property_group'].map(node_indices),
                value=link_counts['count'],
                color="lightblue"
            )
        )])

        fig.update_layout(title_text="Entity-Property Relationships", font_size=12)
        fig.show()

        return fig, link_counts

    # =========================================================================
    # SJR Data Integration
    # =========================================================================

    def add_sjr_to_metadata(
        self,
        metadata_df: pd.DataFrame,
        sjr_folder: str,
        source_col: str = 'Source',
        year_col: str = 'publication_year',
        source_rename_dict: dict = None
    ) -> pd.DataFrame:
        """
        Add SJR values from SCImago CSVs to metadata DataFrame.
        
        Args:
            metadata_df: DataFrame with paper metadata.
            sjr_folder: Folder containing SCImago CSV files.
            source_col: Column containing journal names.
            year_col: Column containing publication year.
            source_rename_dict: Optional dict for journal name normalization.
            
        Returns:
            DataFrame with added SJR column.
        """
        # Load all SJR data
        sjr_all = self._load_sjr_files(sjr_folder)

        # Prepare metadata
        metadata_clean = self._prepare_metadata_for_sjr(
            metadata_df, source_col, source_rename_dict
        )

        # Merge SJR data
        merged = metadata_clean.merge(
            sjr_all,
            left_on=[source_col, year_col],
            right_on=['Title', 'Year'],
            how='left'
        )

        # Handle fuzzy matching for missing values
        merged = self._fuzzy_match_sjr(merged, sjr_all, source_col, year_col)

        return merged.drop(columns=['Title', 'Year'])

    def _load_sjr_files(self, sjr_folder: str) -> pd.DataFrame:
        """Load and combine all SCImago CSV files."""
        all_files = glob.glob(os.path.join(sjr_folder, "*.csv"))
        sjr_list = []

        for f in all_files:
            df = pd.read_csv(f, sep=';', low_memory=False)

            year_match = re.search(r'\b(\d{4})\b', os.path.basename(f))
            if not year_match:
                raise ValueError(f"Could not extract year from filename: {f}")

            df['Year'] = int(year_match.group(1))
            df['Title'] = df['Title'].str.upper().str.strip()
            df['SJR'] = df['SJR'].astype(str).str.replace(',', '.').str.strip()
            df['SJR'] = pd.to_numeric(df['SJR'], errors='coerce')
            sjr_list.append(df[['Title', 'Year', 'SJR']])

        sjr_all = pd.concat(sjr_list, ignore_index=True)
        sjr_all = sjr_all.sort_values('SJR', ascending=False).drop_duplicates(
            subset=['Title', 'Year'], keep='first'
        )
        return sjr_all

    def _prepare_metadata_for_sjr(
        self,
        df: pd.DataFrame,
        source_col: str,
        rename_dict: dict
    ) -> pd.DataFrame:
        """Prepare metadata DataFrame for SJR matching."""
        df_clean = df.copy()

        df_clean[source_col] = (
            df_clean[source_col]
            .astype(str)
            .str.upper()
            .str.replace("&", "AND", regex=False)
            .str.strip()
        )

        if rename_dict is not None:
            rename_dict = {k.upper(): v.upper() for k, v in rename_dict.items()}
            df_clean[source_col] = df_clean[source_col].replace(rename_dict)

        if 'SJR' in df_clean.columns:
            df_clean = df_clean.drop(columns=['SJR'])

        return df_clean

    def _fuzzy_match_sjr(
        self,
        merged: pd.DataFrame,
        sjr_all: pd.DataFrame,
        source_col: str,
        year_col: str
    ) -> pd.DataFrame:
        """Perform fuzzy matching for missing SJR values."""
        mask_missing = merged['SJR'].isna()

        for idx in merged[mask_missing].index:
            src = merged.at[idx, source_col]
            year = merged.at[idx, year_col]
            candidates = sjr_all[sjr_all['Year'] == year]['Title'].tolist()

            src_clean = src.replace(',', '').replace(':', '').strip()

            for candidate in candidates:
                candidate_clean = candidate.replace(',', '').replace(':', '').strip()
                if src_clean == candidate_clean:
                    merged.at[idx, 'SJR'] = sjr_all.loc[
                        (sjr_all['Title'] == candidate) & (sjr_all['Year'] == year),
                        'SJR'
                    ].values[0]
                    break

        return merged
