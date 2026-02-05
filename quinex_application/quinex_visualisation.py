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
import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.colors import LogNorm
import seaborn as sns
import cartopy.crs as ccrs
import cartopy.feature as cfeature

from .country_codes import CONTINENT_BOUNDS
from .plot_utils import (
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
from .data_processing import (
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
            data_list: List of dicts with 'df', 'entity_col', 'value_col', 'ylabel', 'title'.
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
            Matplotlib figure.
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

        # Plot each subplot
        for i, (ax, data) in enumerate(zip(axes, data_list)):
            agg_df = prepared_data[i]['agg_df']
            entity_col = data['entity_col']
            ylabel = data['ylabel']
            title = data.get('title', '')

            self._plot_temporal_subplot(
                ax, agg_df, entity_col, color_dict,
                min_n, max_n, point_size_range,
                error_type, error_display, ylabel, title, number_xticks
            )

        # Add legends
        self._add_temporal_legends(
            fig, all_entities, all_n_vals, color_dict,
            legend_title, legend_position, legend_size_position, point_size_range
        )

        plt.tight_layout()
        return fig

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
        """Prepare data for temporal plots."""
        prepared = []

        for data in data_list:
            df = data['df'].copy()
            entity_col = data['entity_col']
            value_col = data['value_col']

            if iqr_filter:
                df = apply_iqr_filter(df, value_col, entity_col)

            df = parse_temporal_scope(df, temporal_col, publicationyear_col)
            df = filter_by_min_papers(df, 'jahr', min_papers=min_papers_per_year)

            agg_df = calculate_aggregates(
                df, entity_col, value_col, 'jahr', central_tendency, error_type
            )
            agg_df = agg_df[agg_df['n'] >= min_datapoints_per_year]

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
        number_xticks: int
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
    ):
        """
        Plot multiple datasets on a world map with color-coded values.
        
        Args:
            datasets: List of dicts with 'df', 'value_column', 'entity_column', 'title'.
            colorbar_title: Title for the colorbar.
            figsize: Figure size.
            default_point_size: Default marker size.
            jitter_strength: Random spatial jitter in degrees.
            cmap: Colormap name.
            font_size: Font size.
            log_scale: Whether to use logarithmic color scale.
            apply_iqr: Whether to filter outliers.
            continent: Limit view to specific continent.
            
        Returns:
            Matplotlib figure.
        """
        set_font_sizes(font_size)

        n_plots = len(datasets)
        ncols = 2 if n_plots > 1 else 1
        nrows = math.ceil(n_plots / ncols)

        fig, axes = plt.subplots(
            nrows, ncols, figsize=figsize,
            subplot_kw={'projection': ccrs.PlateCarree()}
        )
        axes = flatten_axes(axes, n_plots)

        # Apply jitter
        jittered_datasets = apply_jitter_to_datasets(datasets, jitter_strength)

        # Get entity markers
        entity_marker_map = self._create_entity_marker_map(jittered_datasets)

        # Prepare color scale
        scalar_map = self._prepare_color_scale(
            jittered_datasets, cmap, log_scale, apply_iqr
        )

        # Plot each subplot
        default_color = plt.cm.get_cmap(cmap)(0.7)

        for i, data in enumerate(jittered_datasets):
            self._plot_world_subplot(
                axes[i], data, entity_marker_map, scalar_map,
                default_color, default_point_size, continent
            )

        # Add colorbar
        if scalar_map:
            self._add_world_colorbar(fig, axes, scalar_map, colorbar_title, font_size)

        plt.subplots_adjust(
            wspace=0.02, hspace=0.02,
            right=0.88 if scalar_map else 0.98
        )

        return fig

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
        apply_iqr: bool
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
        continent: str
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

        # Set extent
        bounds = CONTINENT_BOUNDS.get(continent, CONTINENT_BOUNDS['World'])
        ax.set_extent(bounds, crs=ccrs.PlateCarree())

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
            fraction=0.01, pad=0.01
        )
        cbar.ax.set_ylabel(colorbar_title or "Value", fontsize=font_size)

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
