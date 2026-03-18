"""
Quinex visualization module for research data analysis.

This module provides visualization functions for analyzing extracted
research data, including temporal trends, spatial distributions,
and multi-dataset comparisons.
"""

import os
import math
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.colors import LogNorm
from matplotlib.gridspec import GridSpec
import seaborn as sns
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import cartopy.io.shapereader as shpreader

from quinex_application.postprocessing.country_codes import CONTINENT_BOUNDS, normalize_country_code, convert_iso3_to_iso2
from quinex_application.visualisation.plot_utils import (
    set_font_sizes,
    setup_plotting_environment,
    create_size_legend,
    create_line_legend_handles,
    calculate_marker_sizes,
    map_values_to_sizes,
    get_color_map,
    create_entity_color_palette,
    style_legend_frame,
    flatten_axes,
)
from quinex_application.postprocessing.data_processing import (
    convert_unit,
    convert_row,
    apply_iqr_filter,
    parse_temporal_scope,
    filter_by_min_papers,
    parse_spatial_scope,
    apply_jitter_to_datasets,
    calculate_aggregates,
)


# =============================================================================
# Default Entity Colors
# =============================================================================

DEFAULT_ENTITY_COLORS = {
    "Battery": "#8b0000",
    "Lithium-Ion Battery": "#ff0000",
    "Lead Acid Battery": "#4E0000",
    "PV": "#ffd700",
    "Utility-Scale PV": "#ff9900",
    "Wind Turbine": "#1e90ff",
    "Wind": "#1e90ff",
    "Onshore Wind": "#8bc5ff",
    "Offshore Wind": "#06223f",
    "Hydrogen": "#46250f",
    "Electrolyzer": "#32cd32",
    "Coal": "#ff69b4",
}


class QuinexVisualisation:
    """
    Visualizes research data extracted using quinex.
    
    Provides methods for temporal trends, spatial distributions,
    and comparative analysis across multiple datasets.
    """
    
    def __init__(self):
        """Initialize the visualization client with default settings."""
        pd.set_option('display.max_colwidth', None)
        
        self.color = sns.color_palette("dark:steelblue", 6)[2]
        self.color2 = sns.color_palette("dark:cyan", 6)[2]
        self.entity_colors = DEFAULT_ENTITY_COLORS.copy()
        
        setup_plotting_environment()

    # =========================================================================
    # Data Loading
    # =========================================================================

    def load_df(self, path: str = "df_quinex.parquet") -> pd.DataFrame:
        """
        Load DataFrame from disk.
        
        Args:
            path: File path of the saved DataFrame.
            
        Returns:
            Loaded DataFrame.
            
        Raises:
            FileNotFoundError: If file doesn't exist.
        """
        if not os.path.exists(path):
            raise FileNotFoundError(f"No saved DataFrame found at '{path}'")

        df = pd.read_parquet(path)
        print(f"📂 Loaded DataFrame from '{path}' with {len(df)} rows")
        return df

    # =========================================================================
    # Unit Conversion (delegates to data_processing module)
    # =========================================================================

    def convert_unit(self, value, input_unit, output_unit, year, parse=False):
        """Convert value between units using the quinex API."""
        return convert_unit(value, input_unit, output_unit, year, parse)
    
    def convert_row(self, row, target_unit, year=None):
        """Convert a DataFrame row's value to target unit."""
        return convert_row(row, target_unit, year)

    # =========================================================================
    # Basic Plots
    # =========================================================================

    def plot_top_values(
        self,
        df: pd.DataFrame,
        column: str,
        top_n: int = 10,
        ignore_empty: bool = True,
        figsize: tuple = (6, 6),
        title: str = None
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

    # =========================================================================
    # Temporal Trend Plots
    # =========================================================================

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
        font_size: int = 14,
        number_xticks: int = 5,
        point_size_range: tuple = (50, 200),
        temporal_col: str = "temporal_scope",
        publicationyear_col: str = "publication_year",
        min_datapoints_per_year: int = 5,
        min_papers_per_year: int = None,
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
            legend_title: Title for the color legend.
            color_dict: Optional color mapping for entities.
            figsize: Figure size.
            legend_position: Position for color legend.
            legend_size_position: Position for size legend.
            central_tendency: 'mean', 'median', or 'moving average'.
            error_type: 'se' (standard error) or 'ci' (confidence interval).
            error_display: 'bars', 'shade', or None.
            iqr_filter: Whether to remove outliers using IQR.
            font_size: Font size for labels.
            number_xticks: Interval for x-axis ticks.
            point_size_range: Range for marker sizes (min, max).
            temporal_col: Column containing temporal scope.
            publicationyear_col: Column containing publication year.
            min_datapoints_per_year: Minimum data points required per year.
            min_papers_per_year: Minimum unique papers required per year.
            
        Returns:
            Tuple of (fig, data_tables) where:
                - fig: Matplotlib figure
                - data_tables: Dictionary mapping subplot titles to their aggregated data (DataFrames)
        """
        set_font_sizes(font_size)

        n_plots = len(data_list)
        ncols = 2 if n_plots > 1 else 1
        nrows = math.ceil(n_plots / ncols)

        fig, axes = plt.subplots(nrows, ncols, figsize=figsize, sharey=False)
        axes = flatten_axes(axes, n_plots)

        # Prepare data and get global parameters
        prepared_data = self._prepare_temporal_data(
            data_list, iqr_filter, temporal_col, publicationyear_col,
            min_papers_per_year, min_datapoints_per_year, central_tendency, error_type
        )

        all_entities, all_n_vals, color_dict = self._get_global_plot_params(
            prepared_data, color_dict
        )

        min_n, max_n = min(all_n_vals), max(all_n_vals)

        # Plot each subplot and collect data tables
        data_tables = {}
        for i, (ax, data) in enumerate(zip(axes, data_list)):
            agg_df = prepared_data[i]['agg_df']
            entity_col = data['entity_col']
            ylabel = data['ylabel']
            title = data.get('title', '')

            additional_data = data.get('additional_data', None)
            year_range = data.get('year_range', None)
            y_range = data.get('y_range', None)

            self._plot_temporal_subplot(
                ax, agg_df, entity_col, color_dict,
                min_n, max_n, point_size_range,
                error_type, error_display, ylabel, title, number_xticks,
                additional_data=additional_data, year_range=year_range, y_range=y_range
            )
            
            # Store the aggregated data for this subplot
            data_tables[title] = agg_df

        # Add legends
        self._add_temporal_legends(
            fig, all_entities, all_n_vals, color_dict,
            legend_title, legend_position, legend_size_position, point_size_range
        )

        plt.tight_layout()
        return fig, data_tables

    def _prepare_temporal_data(
        self,
        data_list: list,
        iqr_filter: bool,
        temporal_col: str,
        publicationyear_col: str,
        min_papers_per_year: int,
        min_datapoints_per_year: int,
        central_tendency: str,
        error_type: str
    ) -> list:
        """Prepare data for temporal plots.
        
        Each entry in data_list can override min_papers_per_year and min_datapoints_per_year.
        """
        prepared = []

        for data in data_list:
            df = data['df'].copy()
            entity_col = data['entity_col']
            value_col = data['value_col']
            
            # Allow per-entry override of min thresholds
            entry_min_papers = data.get('min_papers_per_year', min_papers_per_year)
            entry_min_datapoints = data.get('min_datapoints_per_year', min_datapoints_per_year)

            if iqr_filter:
                df = apply_iqr_filter(df, value_col, entity_col)

            df = parse_temporal_scope(df, temporal_col, publicationyear_col)
            df = filter_by_min_papers(df, 'jahr', min_papers=entry_min_papers)

            agg_df = calculate_aggregates(
                df, entity_col, value_col, 'jahr', central_tendency, error_type
            )
            agg_df = agg_df[agg_df['n'] >= entry_min_datapoints]

            prepared.append({
                'df': df,
                'agg_df': agg_df,
                'entity_col': entity_col,
                'value_col': value_col
            })

        return prepared

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
        y_range: tuple = None
    ):
        """Plot a single temporal subplot."""
        # Map sizes
        agg_df = agg_df.copy()
        agg_df['size_mapped'] = map_values_to_sizes(
            agg_df['n'].fillna(min_n).values, min_n, max_n, size_range
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
        size_range: tuple
    ):
        """Add color and size legends to temporal plot."""
        # Color legend
        handles = create_line_legend_handles(all_entities, color_dict)
        fig.legend(
            handles=handles, labels=all_entities,
            title=legend_title, bbox_to_anchor=legend_position, loc='upper left'
        )

        # Size legend
        ax_temp = fig.axes[0]
        size_handles = create_size_legend(
            ax_temp, np.sort(np.unique(all_n_vals)),
            size_range[0], size_range[1]
        )
        fig.legend(
            handles=size_handles, title='Sample Size',
            bbox_to_anchor=legend_size_position, loc='upper left'
        )

    # =========================================================================
    # Spatial Plots (World Map)
    # =========================================================================

    def plot_multiple_datasets_on_world(
        self,
        datasets: list,
        colorbar_title: str = None,
        figsize: tuple = (14, 7),
        default_point_size: int = 60,
        jitter_strength: float = 0.0,
        cmap: str = "viridis",
        font_size: int = 14,
        log_scale: bool = False,
        apply_iqr: bool = True,
        continent: str = None,
        country_column: str = "country",
        aggregation: str = "mean",
        spatial_extent: list = None,
    ):
        """
        Plot multiple datasets on a world map with color-coded values.
        
        Each dataset dict can include:
            - 'plot_mode' ('points', 'choropleth', or 'size'): How to visualize the data.
              * 'points': Scatter plot on map with color-coded values
              * 'choropleth': Fill countries by aggregated values
              * 'size': Bubble chart showing GHI (x-axis) vs value (y-axis) with bubble size
                       representing number of data points. Requires 'ghi_data_path' in dataset.
            - 'continent' (str): Override the global continent for this specific plot.
            - 'spatial_extent' (list): Override the global extent [lon_min, lon_max, lat_min, lat_max].
            - 'min_datapoints' (int): Minimum number of data points a country must
              have to be colored in choropleth mode (default: 1).
            - 'ghi_data_path' (str): Required for plot_mode='size'. Path to GHI xlsx file.
            - 'highlight_countries' (list): For plot_mode='size'. List of country codes/names
              to highlight with distinct colors. All others shown as grey "Others".
            - 'x_range' (tuple): For plot_mode='size'. Explicit (min, max) limits for the
              x-axis (GHI axis), e.g. (0, 8). If not set, matplotlib auto-scales.
            - 'min_datapoints' (int): For plot_mode='size'. Minimum number of data
              points a country must have to appear in the bubble chart (default: 1).
            - 'show_regression' (bool): For plot_mode='size'. Whether to draw an OLS
              regression line through all plotted countries (default: False).
        
        Args:
            datasets: List of dicts with 'df', 'value_column', 'entity_column',
                'title', and optionally 'plot_mode', 'continent', 'spatial_extent',
                'min_datapoints', and 'ghi_data_path'.
            colorbar_title: Title for the colorbar.
            figsize: Figure size.
            default_point_size: Default marker size.
            jitter_strength: Random spatial jitter in degrees.
            cmap: Colormap name.
            font_size: Font size.
            log_scale: Whether to use logarithmic color scale.
            apply_iqr: Whether to filter outliers.
            continent: Default continent to display (can be overridden per dataset).
            spatial_extent: Default custom extent [lon_min, lon_max, lat_min, lat_max]
                (can be overridden per dataset). If set, takes precedence over continent.
            country_column: Column name containing ISO-3 country codes.
            aggregation: Aggregation method for choropleth ('mean', 'median', 'sum', 'min', 'max').
            
        Returns:
            Tuple of (fig, data_tables) where:
                - fig: Matplotlib figure
                - data_tables: Dict mapping titles to DataFrames with columns
                  (country, avg_value, n_datapoints, ghi) from size-mode plots.
        """
        set_font_sizes(font_size)

        n_plots = len(datasets)
        has_any_size = any(d.get('plot_mode', 'points') == 'size' for d in datasets)

        # Set up 2x2 (or smaller) grid layout
        ncols = 2 if n_plots > 1 else 1
        nrows = math.ceil(n_plots / ncols)

        if has_any_size:
            fig = plt.figure(figsize=figsize)
            gs = GridSpec(nrows, ncols, figure=fig, wspace=0.15, hspace=0.35)
            axes = []
            size_plot_axes = {}  # index -> ax for size-mode datasets

            for idx, data in enumerate(datasets):
                r, c = divmod(idx, ncols)
                plot_mode = data.get('plot_mode', 'points')
                if plot_mode == 'size':
                    ax = fig.add_subplot(gs[r, c])
                    size_plot_axes[idx] = ax
                    axes.append(None)  # placeholder
                else:
                    ax = fig.add_subplot(gs[r, c], projection=ccrs.Robinson())
                    axes.append(ax)
        else:
            size_plot_axes = {}
            fig, axes_arr = plt.subplots(
                nrows, ncols, figsize=figsize,
                subplot_kw={'projection': ccrs.Robinson()}
            )
            axes = flatten_axes(axes_arr, n_plots)

        # Apply jitter (only relevant for point mode)
        jittered_datasets = apply_jitter_to_datasets(datasets, jitter_strength)

        # Get entity markers
        entity_marker_map = self._create_entity_marker_map(jittered_datasets)

        # Prepare color scale (exclude size-mode datasets)
        map_jittered = [d for d in jittered_datasets if d.get('plot_mode', 'points') != 'size']
        scalar_map = self._prepare_color_scale(
            map_jittered, cmap, log_scale, apply_iqr,
            country_column=country_column, aggregation=aggregation,
        )

        # Plot each subplot
        default_color = plt.cm.get_cmap(cmap)(0.7)
        data_tables = {}

        for i, data in enumerate(jittered_datasets):
            plot_mode = data.get('plot_mode', 'points')
            dataset_extent = data.get('spatial_extent', spatial_extent)
            dataset_continent = data.get('continent', continent)

            if plot_mode == 'size':
                # Plot bubble chart on its dedicated axis
                ax = size_plot_axes.get(i)
                if ax is not None:
                    ghi_data_path = data.get('ghi_data_path')
                    if ghi_data_path:
                        ghi_data = self._load_ghi_data(ghi_data_path)
                        scatter_data = self._plot_country_scatter_subplot(
                            ax, data, ghi_data,
                            country_column=country_column,
                            aggregation=aggregation,
                            font_size=font_size,
                            highlight_countries=data.get('highlight_countries'),
                            x_range=data.get('x_range'),
                            min_datapoints=data.get('min_datapoints', 1),
                            show_regression=data.get('show_regression', False),
                        )
                        if scatter_data is not None:
                            title = data.get('title', f'size_plot_{i}')
                            data_tables[title] = scatter_data
            elif plot_mode == 'choropleth':
                self._plot_world_choropleth_subplot(
                    axes[i], data, scalar_map, dataset_continent,
                    country_column=country_column,
                    aggregation=aggregation,
                    spatial_extent=dataset_extent,
                    min_datapoints=data.get('min_datapoints', 1),
                )
            else:  # points mode
                self._plot_world_subplot(
                    axes[i], data, entity_marker_map, scalar_map,
                    default_color, default_point_size, dataset_continent,
                    spatial_extent=dataset_extent,
                )

        # Add colorbar (only for map subplots)
        map_axes = [a for a in axes if a is not None]
        if scalar_map and map_axes:
            if has_any_size:
                cbar_ax = fig.add_axes([0.92, 0.55, 0.015, 0.35])
                cbar = plt.colorbar(scalar_map, cax=cbar_ax)
                cbar.ax.set_ylabel(colorbar_title or "Value", fontsize=font_size)
            else:
                self._add_world_colorbar(fig, map_axes, scalar_map, colorbar_title, font_size)

        if not has_any_size:
            plt.subplots_adjust(
                wspace=0.02, hspace=0.02,
                right=0.88 if scalar_map else 0.98
            )

        return fig, data_tables

    def _create_entity_marker_map(self, datasets: list) -> dict:
        """Create marker mapping for entities."""
        marker_cycle = ["o", "s", "^", "D", "P", "X", "v", "<", ">"]
        
        all_entities = []
        for data in datasets:
            ent_col = data.get("entity_column")
            if ent_col:
                all_entities.extend(data["df"][ent_col].dropna().unique())

        all_entities = sorted(list(set(all_entities)))
        return {ent: marker_cycle[i % len(marker_cycle)] 
                for i, ent in enumerate(all_entities)}

    def _prepare_color_scale(
        self,
        datasets: list,
        cmap: str,
        log_scale: bool,
        apply_iqr: bool,
        country_column: str = "country",
        aggregation: str = "mean",
    ):
        """Prepare color scale for world map."""
        has_value = any(d.get("value_column") for d in datasets)
        if not has_value:
            return None

        all_vals = []
        for data in datasets:
            val_col = data.get("value_column")
            if not val_col:
                continue

            df = data["df"].copy()
            ent_col = data.get("entity_column")

            if apply_iqr and pd.api.types.is_numeric_dtype(df[val_col]):
                if ent_col:
                    df = apply_iqr_filter(df, val_col, ent_col)
                else:
                    df = apply_iqr_filter(
                        df.assign(dummy="x"), val_col, "dummy"
                    ).drop(columns="dummy")

            data['df'] = df

            plot_mode = data.get('plot_mode', 'points')
            if plot_mode == 'choropleth':
                min_dp = data.get('min_datapoints', 1)
                df_clean = df.dropna(subset=[country_column, val_col])
                # Filter countries with fewer data points than min_datapoints
                country_counts = df_clean.groupby(country_column)[val_col].count()
                valid_countries = country_counts[country_counts >= min_dp].index
                country_vals = (
                    df_clean[df_clean[country_column].isin(valid_countries)]
                    .groupby(country_column)[val_col]
                    .agg(aggregation)
                )
                all_vals.append(country_vals)
            else:
                all_vals.append(df[val_col])

        if not all_vals:
            return None

        all_vals = pd.concat(all_vals)

        if log_scale:
            min_pos = all_vals[all_vals > 0].min()
            vmin = max(min_pos, 1e-12)
            vmax = all_vals.max()
            norm = LogNorm(vmin=vmin, vmax=vmax)
        else:
            norm = plt.Normalize(vmin=all_vals.min(), vmax=all_vals.max())

        return plt.cm.ScalarMappable(cmap=cmap, norm=norm)

    def _plot_world_subplot(
        self,
        ax,
        data: dict,
        entity_marker_map: dict,
        scalar_map,
        default_color,
        default_point_size: int,
        continent: str,
        spatial_extent: list = None,
    ):
        """Plot a single world map subplot."""
        df = data['df']
        value_col = data.get('value_column')
        entity_col = data.get('entity_column')
        title = data.get('title', '')

        # Set up map
        ax.set_global()
        ax.coastlines()
        ax.add_feature(cfeature.BORDERS, edgecolor='black')
        ax.add_feature(cfeature.LAND, facecolor='white')
        ax.add_feature(cfeature.OCEAN, facecolor='white')

        # Set extent (spatial_extent takes precedence over continent)
        # For global/world views, set_global() is sufficient — calling set_extent
        # with [-180,180] in PlateCarree would clip the Robinson oval to a rectangle.
        if spatial_extent:
            ax.set_extent(spatial_extent, crs=ccrs.PlateCarree())
        elif continent and continent != 'World':
            ax.set_extent(CONTINENT_BOUNDS[continent], crs=ccrs.PlateCarree())

        # Plot points
        for _, row in df.iterrows():
            color = scalar_map.to_rgba(row[value_col]) if (value_col and scalar_map) else default_color
            marker = entity_marker_map.get(row[entity_col], 'o') if entity_col else 'o'

            ax.scatter(
                row['longitude'], row['latitude'],
                color=color, s=default_point_size, marker=marker,
                transform=ccrs.PlateCarree(),
                edgecolor='none', linewidth=0
            )

        ax.set_title(title, loc='left', fontweight='bold', pad=10)

        # Add entity legend
        if entity_col:
            handles = [
                plt.Line2D([0], [0], marker=marker, linestyle="",
                          markersize=10, color="black", label=str(ent))
                for ent, marker in entity_marker_map.items()
            ]
            ax.legend(handles=handles, loc="lower left", frameon=True)

    def _plot_world_choropleth_subplot(
        self,
        ax,
        data: dict,
        scalar_map,
        continent: str,
        country_column: str = "country",
        aggregation: str = "mean",
        spatial_extent: list = None,
        min_datapoints: int = 1,
    ):
        """Plot a single world map subplot as a choropleth (countries filled by value).
        
        Args:
            min_datapoints: Minimum number of data points a country must have
                to be colored. Countries below this threshold are shown in grey.
        """
        df = data['df']
        value_col = data.get('value_column')
        title = data.get('title', '')

        # Set up map
        ax.set_global()
        ax.coastlines()
        ax.add_feature(cfeature.BORDERS, edgecolor='black', linewidth=0.5)
        ax.add_feature(cfeature.OCEAN, facecolor='white')

        # Set extent (spatial_extent takes precedence over continent)
        # For global/world views, set_global() is sufficient — calling set_extent
        # with [-180,180] in PlateCarree would clip the Robinson oval to a rectangle.
        if spatial_extent:
            ax.set_extent(spatial_extent, crs=ccrs.PlateCarree())
        elif continent and continent != 'World':
            ax.set_extent(CONTINENT_BOUNDS[continent], crs=ccrs.PlateCarree())

        # Aggregate values per country (normalized)
        if value_col and country_column in df.columns:
            # Normalize country codes first
            df_normalized = df.copy()
            df_normalized['country_norm'] = df_normalized[country_column].apply(normalize_country_code)
            
            df_clean = df_normalized.dropna(subset=['country_norm', value_col])
            
            # Filter countries with fewer data points than min_datapoints
            country_counts = df_clean.groupby('country_norm')[value_col].count()
            valid_countries = country_counts[country_counts >= min_datapoints].index
            df_clean = df_clean[df_clean['country_norm'].isin(valid_countries)]
            
            country_agg = (
                df_clean
                .groupby('country_norm')[value_col]
                .agg(aggregation)
                .to_dict()
            )
        else:
            country_agg = {}

        # Load Natural Earth country geometries
        shpfilename = shpreader.natural_earth(
            resolution='110m', category='cultural', name='admin_0_countries'
        )
        reader = shpreader.Reader(shpfilename)

        for record in reader.records():
            country_iso3 = record.attributes.get('ADM0_A3', '')
            country_iso2 = record.attributes.get('ADM0_A2', '')
            country_name = record.attributes.get('NAME', '')
            geometry = record.geometry

            # Try matching with normalized ISO3 code first
            val = country_agg.get(country_iso3)
            
            # If no match, try other attributes
            if val is None and country_iso2:
                val = country_agg.get(country_iso2)
            
            if val is None and country_name:
                val = country_agg.get(country_name)
            
            # Also try normalizing the country name to find matches
            if val is None and country_name:
                normalized_name = normalize_country_code(country_name)
                if normalized_name != country_name:
                    val = country_agg.get(normalized_name)

            if val is not None and scalar_map is not None:
                facecolor = scalar_map.to_rgba(val)
            else:
                facecolor = '#e0e0e0'  # light grey for countries without data

            ax.add_geometries(
                [geometry], ccrs.PlateCarree(),
                facecolor=facecolor,
                edgecolor='black',
                linewidth=0.5,
            )

        ax.set_title(title, loc='left', fontweight='bold', pad=10)

    def _add_world_colorbar(
        self,
        fig,
        axes,
        scalar_map,
        colorbar_title: str,
        font_size: int
    ):
        """Add colorbar to world map figure."""
        cbar = plt.colorbar(
            scalar_map, ax=axes,
            orientation="vertical",
            fraction=0.005, pad=0.01, shrink=0.5
        )
        cbar.ax.set_ylabel(colorbar_title or "Value", fontsize=font_size)

    def _load_ghi_data(self, ghi_data_path: str) -> dict:
        """
        Load GHI (Global Horizontal Irradiance) data and return a mapping
        from ISO3 country code to GHI_mean value.

        Args:
            ghi_data_path: Path to the country_GHI_mean.xlsx file.

        Returns:
            Dict mapping ISO3 country codes to GHI_mean values.
        """
        ghi_df = pd.read_excel(ghi_data_path)

        # Build name → ISO3 mapping from Natural Earth shapefile
        shpfilename = shpreader.natural_earth(
            resolution='110m', category='cultural', name='admin_0_countries'
        )
        reader = shpreader.Reader(shpfilename)

        name_to_iso3 = {}
        for record in reader.records():
            iso3 = record.attributes.get('ADM0_A3', '')
            for key in ('NAME', 'NAME_LONG', 'FORMAL_EN', 'ABBREV'):
                name = record.attributes.get(key, '')
                if name:
                    name_to_iso3[name] = iso3

        ghi_dict = {}
        for _, row in ghi_df.iterrows():
            country_name = row['Country']
            ghi_val = row['GHI_mean']

            # Try Natural Earth name match first
            iso3 = name_to_iso3.get(country_name)

            # Fall back to normalize_country_code
            if not iso3:
                normalized = normalize_country_code(country_name)
                if normalized != country_name:
                    iso3 = normalized

            if iso3:
                ghi_dict[iso3] = ghi_val
            
            # Also store under original country name so non-ISO3
            # normalized codes (e.g. 'Mozambique') can still match
            if pd.notna(ghi_val):
                ghi_dict[country_name] = ghi_val

        return ghi_dict

    def _plot_country_scatter_subplot(
        self,
        ax,
        data: dict,
        ghi_data: dict,
        country_column: str = "country",
        aggregation: str = "mean",
        font_size: int = 14,
        highlight_countries: list = None,
        x_range: tuple = None,
        min_datapoints: int = 1,
        show_regression: bool = False,
    ):
        """
        Plot a 2D bubble chart: GHI (x) vs. aggregated value (y), sized by data point count.

        Countries specified in highlight_countries are shown with distinct colors.
        All other countries are shown in grey as "Others".

        Args:
            ax: A 2D matplotlib axes instance.
            data: Dataset dict with 'df', 'value_column', 'title', etc.
            ghi_data: Dict mapping ISO3 country codes to GHI_mean values.
            country_column: Column name containing country codes.
            aggregation: Aggregation method for the value column.
            font_size: Font size for labels.
            highlight_countries: List of country codes/names to highlight.
                Each entry is normalized via normalize_country_code.
                If None, auto-selects top/bottom countries.
            x_range: Optional (min, max) tuple for the x-axis (GHI). If None,
                matplotlib auto-scales.
            min_datapoints: Minimum number of data points a country must have
                to appear in the chart. Countries below this threshold are excluded.
            show_regression: If True, draw an OLS regression line through all
                plotted points.

        Returns:
            DataFrame with scatter data (country, avg_value, n_datapoints, ghi) or None.
        """
        df = data['df']
        value_col = data.get('value_column')
        title = data.get('title', '')

        if not value_col or country_column not in df.columns:
            ax.set_visible(False)
            return None

        # Normalize country codes
        df_clean = df.copy()
        df_clean['country_norm'] = df_clean[country_column].apply(normalize_country_code)
        df_clean = df_clean.dropna(subset=['country_norm', value_col])

        if df_clean.empty:
            ax.set_visible(False)
            return None

        # Aggregate by country
        country_avg = df_clean.groupby('country_norm')[value_col].agg(aggregation)
        country_count = df_clean.groupby('country_norm')[value_col].count()

        scatter_df = pd.DataFrame({
            'country': country_avg.index,
            'avg_value': country_avg.values,
            'n_datapoints': country_count.values,
        })

        # Apply min_datapoints filter
        if min_datapoints > 1:
            scatter_df = scatter_df[scatter_df['n_datapoints'] >= min_datapoints]

        if scatter_df.empty:
            ax.set_visible(False)
            return None

        # Add GHI data
        scatter_df['ghi'] = scatter_df['country'].map(ghi_data)
        scatter_df = scatter_df.dropna(subset=['ghi'])

        if scatter_df.empty:
            ax.set_visible(False)
            return None

        # Scale bubble sizes: map n_datapoints to a visible size range
        min_size = 30
        max_size = 600
        counts = scatter_df['n_datapoints'].values
        if counts.max() == counts.min():
            sizes = np.full_like(counts, (min_size + max_size) / 2, dtype=float)
        else:
            sizes = min_size + (counts - counts.min()) / (counts.max() - counts.min()) * (max_size - min_size)
        scatter_df['bubble_size'] = sizes

        # --- Determine highlighted countries ---
        if highlight_countries:
            # Normalize user-provided country codes
            highlighted = []
            for c in highlight_countries:
                norm = normalize_country_code(c)
                if norm in scatter_df['country'].values:
                    highlighted.append(norm)
                elif c in scatter_df['country'].values:
                    highlighted.append(c)
            # Deduplicate while preserving order
            highlighted = list(dict.fromkeys(highlighted))
        else:
            # Auto-select: top 2 by studies, bottom 2 by studies, top 2 by value
            top2_studies = scatter_df.nlargest(2, 'n_datapoints')['country'].tolist()
            bottom2_studies = scatter_df.nsmallest(2, 'n_datapoints')['country'].tolist()
            top2_values = scatter_df.nlargest(2, 'avg_value')['country'].tolist()
            highlighted = list(dict.fromkeys(top2_studies + bottom2_studies + top2_values))

        # Distinct colors for highlighted countries
        highlight_palette = ['#e41a1c', '#377eb8', '#4daf4a', '#984ea3', '#ff7f00', '#a65628']
        country_color_map = {}
        color_idx = 0
        for c in highlighted:
            if c not in country_color_map:
                country_color_map[c] = highlight_palette[color_idx % len(highlight_palette)]
                color_idx += 1

        others_color = '#c0c0c0'

        # Plot "Others" first (grey, behind)
        others_mask = ~scatter_df['country'].isin(country_color_map)
        if others_mask.any():
            ax.scatter(
                scatter_df.loc[others_mask, 'ghi'],
                scatter_df.loc[others_mask, 'avg_value'],
                s=scatter_df.loc[others_mask, 'bubble_size'],
                alpha=0.5,
                edgecolors='black', linewidth=0.5,
                c=others_color, label='Others', zorder=2,
            )

        # Plot highlighted countries individually (with label for legend)
        for country_code, color in country_color_map.items():
            mask = scatter_df['country'] == country_code
            if mask.any():
                row = scatter_df[mask].iloc[0]
                ax.scatter(
                    row['ghi'], row['avg_value'],
                    s=row['bubble_size'],
                    alpha=0.85,
                    edgecolors='black', linewidth=0.8,
                    c=color, label=country_code, zorder=3,
                )

        # Regression line
        if show_regression and len(scatter_df) >= 2:
            x_reg = scatter_df['ghi'].values
            y_reg = scatter_df['avg_value'].values
            coeffs = np.polyfit(x_reg, y_reg, 1)
            x_line = np.linspace(x_reg.min(), x_reg.max(), 200)
            y_line = np.polyval(coeffs, x_line)
            ax.plot(
                x_line, y_line,
                color='black', linewidth=1.5, linestyle='--',
                label=f'Regression (slope={coeffs[0]:.2f})', zorder=4,
            )

        # Styling
        ax.set_xlabel('Solar Radiation GHI [kWh/m²/day]', fontsize=font_size - 1)
        ax.set_ylabel(title if title else 'Value', fontsize=font_size - 1)
        ax.set_title(f'{title}', fontsize=font_size, fontweight='bold', loc='left', pad=10)
        ax.tick_params(labelsize=font_size - 2)
        ax.grid(True, linestyle='--', alpha=0.3, zorder=0)

        # Set x-axis range and ticks to step 1
        if x_range is not None:
            ax.set_xlim(x_range[0], x_range[1])
        x_min, x_max = ax.get_xlim()
        ax.set_xticks(np.arange(np.floor(x_min), np.ceil(x_max) + 1, 1))

        # Build combined legend: country colors + bubble sizes
        # First: country color + Others legend
        color_handles = []
        for country_code, color in country_color_map.items():
            color_handles.append(
                plt.Line2D([0], [0], marker='o', linestyle='', markersize=10,
                           color=color, markeredgecolor='black', markeredgewidth=0.8,
                           label=country_code)
            )
        color_handles.append(
            plt.Line2D([0], [0], marker='o', linestyle='', markersize=10,
                       color=others_color, markeredgecolor='black', markeredgewidth=0.5,
                       alpha=0.5, label='Others')
        )
        if show_regression and len(scatter_df) >= 2:
            color_handles.append(
                plt.Line2D([0], [0], linestyle='--', linewidth=1.5,
                           color='black', label=f'Regression (slope={coeffs[0]:.2f})')
            )

        # Second: bubble size legend (min and max)
        legend_counts = [counts.min(), counts.max()]
        size_handles = []
        for cnt in legend_counts:
            if counts.max() == counts.min():
                sz = (min_size + max_size) / 2
            else:
                sz = min_size + (cnt - counts.min()) / (counts.max() - counts.min()) * (max_size - min_size)
            size_handles.append(
                plt.scatter([], [], s=sz, c='white', alpha=0.7,
                            edgecolors='black', linewidth=0.8, label=f'{int(cnt)}')
            )

        # Country legend (right side)
        country_legend = ax.legend(
            handles=color_handles, loc='center left',
            fontsize=font_size - 3, title_fontsize=font_size - 2,
            framealpha=0.9, frameon=True,
            edgecolor='black', fancybox=True,
            bbox_to_anchor=(1.01, 0.5),
        )
        ax.add_artist(country_legend)

        # Size legend (below)
        ax.legend(
            handles=size_handles, title='Number of Studies', loc='lower center',
            fontsize=font_size - 3, title_fontsize=font_size - 2,
            framealpha=0.9, scatterpoints=1, frameon=True,
            edgecolor='black', fancybox=True,
            bbox_to_anchor=(0.5, -0.35), ncol=2,
        )

        return scatter_df.reset_index(drop=True)

    # =========================================================================
    # Helper Methods (delegating to modules)
    # =========================================================================

    def apply_iqr_filter(self, df: pd.DataFrame, value_column: str, entity_col: str) -> pd.DataFrame:
        """Remove outliers using IQR method."""
        return apply_iqr_filter(df, value_column, entity_col)

    def calculate_aggregates(
        self,
        df: pd.DataFrame,
        entity_col: str,
        value_col: str,
        central_tendency: str,
        error_type: str
    ) -> pd.DataFrame:
        """Aggregate DataFrame by year and entity."""
        return calculate_aggregates(df, entity_col, value_col, 'jahr', central_tendency, error_type)

    def create_size_legend_handles(self, ax, n_vals, min_size=20, max_size=100):
        """Create legend handles for sample sizes."""
        return create_size_legend(ax, n_vals, min_size, max_size)

    def style_legend_frame(self, legend):
        """Style a legend frame."""
        style_legend_frame(legend)

    def get_color_map(self, datasets, color_column, palette=None):
        """Create color mapping for categorical values."""
        return get_color_map(datasets, color_column, palette)

    def apply_jitter_to_datasets(self, datasets, jitter_strength=0.2):
        """Apply jitter to datasets."""
        return apply_jitter_to_datasets(datasets, jitter_strength)

    def convert_spatial(self, df, spatial_col="spatial_scope"):
        """Parse spatial scope data."""
        return parse_spatial_scope(df, spatial_col)

    def calculate_marker_sizes(self, values, min_size=30, max_size=600):
        """Scale values to marker sizes."""
        return calculate_marker_sizes(values, min_size, max_size)

    # =========================================================================
    # Plot Dataset Helper
    # =========================================================================

    def plot_dataset_on_ax(
        self,
        ax,
        fig,
        dataset: dict,
        color_map: dict,
        default_point_size: float,
        i: int
    ):
        """
        Plot a dataset on a given axis with optional sizing and coloring.
        
        Args:
            ax: Matplotlib axes to plot on.
            fig: Figure object.
            dataset: Dict with 'df' and optional 'value_column', 'color_column'.
            color_map: Mapping from category to color.
            default_point_size: Default marker size.
            i: Dataset index for legend positioning.
        """
        df = dataset['df']
        marker = dataset.get('marker', 'o')
        value_column = dataset.get('value_column')
        color_column = dataset.get('color_column')
        size_legend_title = dataset.get('size_legend_title')
        size_legend_position = dataset.get('size_legend_position')

        # Calculate sizes
        if value_column:
            values = df[value_column]
            min_size, max_size = default_point_size, default_point_size * 20
            sizes = calculate_marker_sizes(values, min_size, max_size)
        else:
            sizes = np.full(len(df), default_point_size)

        # Plot points
        if color_column:
            for cat in df[color_column].unique():
                subset = df[df[color_column] == cat]
                subset_sizes = sizes[subset.index] if value_column else default_point_size
                ax.scatter(
                    subset['longitude'], subset['latitude'],
                    s=subset_sizes, color=color_map[cat],
                    alpha=1, transform=ccrs.PlateCarree(),
                    edgecolor='black', linewidth=0.5, marker=marker
                )
        else:
            ax.scatter(
                df['longitude'], df['latitude'],
                s=sizes, color='steelblue', alpha=0.6,
                transform=ccrs.PlateCarree(),
                edgecolor='black', linewidth=0.5, marker=marker
            )

        # Add size legend
        if value_column:
            self._add_size_legend(
                ax, fig, values, default_point_size, marker,
                size_legend_title, size_legend_position
            )

    def _add_size_legend(
        self,
        ax,
        fig,
        values,
        default_point_size: float,
        marker: str,
        title: str,
        position: tuple
    ):
        """Add size legend to plot."""
        legend_values = np.quantile(values, [0.1, 0.5, 0.9])
        legend_values = np.round(legend_values, 1)
        
        min_size, max_size = default_point_size, default_point_size * 20
        legend_sizes = calculate_marker_sizes(np.array(legend_values), min_size, max_size)
        
        handles = [
            plt.scatter([], [], s=s, color='steelblue', alpha=0.6,
                       edgecolor='black', marker=marker, label=f"{v:.2f}")
            for s, v in zip(legend_sizes, legend_values)
        ]
        
        size_legend = fig.legend(
            handles=handles, title=title,
            loc='lower left', bbox_to_anchor=position, frameon=True
        )
        ax.add_artist(size_legend)
        style_legend_frame(size_legend)

    def create_color_legend(
        self,
        ax,
        fig,
        color_map: dict,
        categories: list,
        color_legend_title: str,
        color_legend_position: tuple = (0, 0)
    ):
        """
        Add a color legend to the plot.
        
        Args:
            ax: Matplotlib axes.
            fig: Figure object.
            color_map: Mapping from category to color.
            categories: List of categories to include.
            color_legend_title: Legend title.
            color_legend_position: Legend position.
        """
        import matplotlib.lines as mlines
        
        handles = [
            mlines.Line2D(
                [], [], marker='X', linestyle='None',
                markersize=10, markerfacecolor=color_map[cat],
                markeredgecolor='black', label=cat
            )
            for cat in categories
        ]
        
        color_legend = fig.legend(
            handles=handles, title=color_legend_title,
            loc='lower left', bbox_to_anchor=color_legend_position, frameon=True
        )
        ax.add_artist(color_legend)
        style_legend_frame(color_legend)

    # =========================================================================
    # Country Comparison Plots
    # =========================================================================

    def plot_boxplot_with_regional_medians(
        self,
        data_list: list,
        figsize: tuple = (12, 8),
        font_size: int = 14,
        ncols: int = None,
        show_outliers: bool = True,
        notch: bool = False,
        whis: float = 1.5,
        iqr_filter: bool = True,
        iqr_multiplier: float = 1.5,
        lower_quantile: float = 0.2,
        upper_quantile: float = 0.8
    ):
        """
        Create boxplots with regional median overlay lines.
        
        Each plot shows a main boxplot from the overall DataFrame, with overlay
        lines showing the median values for each region/country. Multiple plots
        can be created in a grid layout.
        
        Args:
            data_list: List of dicts, each with:
                - 'df': Main DataFrame for boxplot
                - 'df_region': List of regional DataFrames
                - 'region_labels': List of region/country names (matching df_region)
                - 'value_col': Column name containing values
                - 'ylabel': Label for y-axis
                - 'title': Optional plot title
                - 'xlabel': Optional label for x-axis
            figsize: Figure size as tuple (width, height).
            font_size: Font size for labels and ticks.
            ncols: Number of columns in the subplot grid. If None, automatic
                  (2 columns if multiple plots, 1 column if single plot).
            show_outliers: Whether to display outlier points.
            notch: Whether to show notched boxes.
            whis: Whisker length as multiple of IQR.
            iqr_filter: Whether to remove outliers using IQR filter.
            iqr_multiplier: Multiplier for IQR range.
            lower_quantile: Lower quantile boundary.
            upper_quantile: Upper quantile boundary.
            
        Returns:
            tuple: (fig, axes, all_stats) - Figure, axes array, and statistics.
            
        Example:
            >>> data = [
            ...     {
            ...         'df': df_all,
            ...         'df_region': [df_eu, df_asia, df_na],
            ...         'region_labels': ['Europe', 'Asia', 'North America'],
            ...         'value_col': 'efficiency',
            ...         'ylabel': 'Efficiency (%)',
            ...         'title': 'a) Overall Distribution',
            ...         'xlabel': 'Technology'
            ...     }
            ... ]
            >>> fig, axes, stats = vis.plot_boxplot_with_regional_medians(data)
        """
        set_font_sizes(font_size)
        
        n_plots = len(data_list)
        if ncols is None:
            ncols = 2 if n_plots > 1 else 1
        nrows = math.ceil(n_plots / ncols)
        
        fig, axes = plt.subplots(nrows, ncols, figsize=figsize)
        axes = flatten_axes(axes, n_plots)
        
        all_stats = []
        
        for ax, data in zip(axes, data_list):
            df_main = data['df']
            df_regions = data['df_region']
            region_labels = data.get('region_labels', [f'Region {i}' for i in range(len(df_regions))])
            value_col = data['value_col']
            ylabel = data['ylabel']
            title = data.get('title', '')
            xlabel = data.get('xlabel', None)
            
            # Validate input
            if value_col not in df_main.columns:
                raise ValueError(f"Column '{value_col}' not found in main DataFrame")
            
            # Filter main data
            df_main_filtered = df_main.copy()
            if iqr_filter and len(df_main_filtered) > 0:
                df_main_filtered['_dummy_group'] = 'all'
                df_main_filtered = apply_iqr_filter(
                    df_main_filtered, value_col, '_dummy_group',
                    lower_quantile, upper_quantile, iqr_multiplier
                )
            
            main_data = df_main_filtered[value_col].dropna().values
            
            # Create color palette for regions
            region_colors = sns.color_palette("husl", len(df_regions))
            
            # Calculate regional medians
            region_stats = {}
            region_medians = []
            region_colors_list = []
            
            for region_df, region_label, region_color in zip(df_regions, region_labels, region_colors):
                if value_col not in region_df.columns:
                    raise ValueError(f"Column '{value_col}' not found in region DataFrame")
                
                region_data = region_df[value_col].dropna().values
                
                if len(region_data) > 0:
                    median_val = np.median(region_data)
                    region_medians.append(median_val)
                    region_colors_list.append(region_color)
                    region_stats[region_label] = {
                        'median': median_val,
                        'mean': np.mean(region_data),
                        'n': len(region_data)
                    }
            
            # Create main boxplot (subtle gray/black)
            box_width = 0.5  # width of boxplot
            bp = ax.boxplot(
                [main_data],
                patch_artist=True,
                notch=notch,
                showfliers=show_outliers,
                showmeans=False,
                widths=[box_width],  # Explicitly set box width
                flierprops=dict(
                    marker='o',
                    markerfacecolor='none',
                    markeredgecolor='lightgray',
                    markersize=5,
                    alpha=0.4
                ),
                whiskerprops=dict(color='darkgray', linewidth=1.5),
                capprops=dict(color='darkgray', linewidth=1.5),
                medianprops=dict(color='black', linewidth=2.5),
                boxprops=dict(linewidth=1),
                whis=whis
            )
            
            # Color main box in subtle gray
            for patch in bp['boxes']:
                patch.set_facecolor('#D3D3D3')  # Light gray
                patch.set_alpha(0.6)
                patch.set_edgecolor('black')
                patch.set_linewidth(1.5)
            
            # Add regional median lines
            x_pos = 1  # x position for boxplot
            x_min = x_pos - box_width / 2
            x_max = x_pos + box_width / 2
            
            for median_val, region_color in zip(region_medians, region_colors_list):
                ax.hlines(
                    median_val, x_min, x_max,
                    color=region_color, linewidth=3,
                    label=None, zorder=10
                )
            
            # Styling
            ax.set_ylabel(ylabel, fontsize=font_size)
            ax.set_xticks([])
            if xlabel:
                ax.set_xlabel(xlabel, fontsize=font_size)
            ax.grid(axis='y', linestyle='--', alpha=0.4)
            ax.set_title(title, loc='left', fontweight='bold', fontsize=font_size)
            
            all_stats.append({
                'main_stats': {
                    'median': np.median(main_data),
                    'mean': np.mean(main_data),
                    'q1': np.percentile(main_data, 25),
                    'q3': np.percentile(main_data, 75),
                    'min': np.min(main_data),
                    'max': np.max(main_data),
                    'n': len(main_data)
                },
                'region_stats': region_stats
            })
        
        # Add legend for regions (on first plot)
        import matplotlib.patches as mpatches
        legend_handles = [
            mpatches.Patch(facecolor=color, edgecolor='black', label=label)
            for label, color in zip(region_labels, region_colors)
        ]
        fig.legend(
            handles=legend_handles,
            title='Regions',
            bbox_to_anchor=(1.02, 0.98),
            loc='upper left',
            frameon=True
        )
        
        plt.tight_layout()
        
        return fig, axes, all_stats
