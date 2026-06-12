"""Spatial visualization methods for Quinex."""

import math
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.colors import LogNorm
from matplotlib.gridspec import GridSpec
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import cartopy.io.shapereader as shpreader

from quinex_application.postprocessing.country_codes import CONTINENT_BOUNDS, normalize_country_code
from quinex_application.visualisation.plot_utils import (
    set_font_sizes,
    setup_plotting_environment,
    create_size_legend,
    calculate_marker_sizes,
    get_color_map,
    style_legend_frame,
    flatten_axes,
)
from quinex_application.visualisation.entity_colors import DEFAULT_ENTITY_COLORS
from quinex_application.postprocessing.data_processing import (
    apply_iqr_filter,
    parse_spatial_scope,
    apply_jitter_to_datasets,
    calculate_aggregates,
)


class SpatialVisualisation:
    """Spatial and map visualization functionality."""

    def __init__(self):
        """Initialize spatial visualization defaults and entity colors."""
        pd.set_option('display.max_colwidth', None)

        self.color = sns.color_palette("dark:steelblue", 6)[2]
        self.color2 = sns.color_palette("dark:cyan", 6)[2]
        self.entity_colors = DEFAULT_ENTITY_COLORS.copy()

        setup_plotting_environment()

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
        iqr_lower_quantile: float = 0.25,
        iqr_upper_quantile: float = 0.75,
        iqr_multiplier: float = 1.5,
        continent: str = None,
        country_column: str = "country",
        aggregation: str = "mean",
        spatial_extent: list = None,
        color_scale_range: tuple = None,
        colorbar_ticks: list = None,
        doi_col: str = "DOI",
        print_summary: bool = True,
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
            - 'show_rivers' (bool): Whether to draw rivers on the map (default: False).
            - 'show_roads' (bool or str): Whether to draw roads on the map (default: False).
              Uses Natural Earth 10m roads data. Accepted values:
              ``True`` / ``'all'`` â€“ all roads; ``'highway'`` â€“ Major Highways only;
              ``'secondary'`` â€“ Major + Secondary Highways.
            - 'show_cities' (bool or int): Whether to draw the largest cities on the map
              (default: False). If ``True``, the 10 largest cities are shown. Pass an
              ``int`` to control how many cities to display (e.g. ``5`` for top 5).
        
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
            iqr_lower_quantile: Lower quantile for IQR filter (default 0.25 = Q1).
            iqr_upper_quantile: Upper quantile for IQR filter (default 0.75 = Q3).
            iqr_multiplier: Multiplier for IQR fence (default 1.5, Tukey method).
            continent: Default continent to display (can be overridden per dataset).
            spatial_extent: Default custom extent [lon_min, lon_max, lat_min, lat_max]
                (can be overridden per dataset). If set, takes precedence over continent.
            country_column: Column name containing ISO-3 country codes.
            aggregation: Aggregation method for choropleth ('mean', 'median', 'sum', 'min', 'max').
            color_scale_range: Optional tuple (vmin, vmax) for the color scale.
                If None, the range is inferred from data (default behavior).
            colorbar_ticks: Optional list of values to mark on the colorbar.
                If None, matplotlib uses automatic ticks (default behavior).
            doi_col: Default DOI column used to count contributing studies.
                Can be overridden per dataset via dataset['doi_col'].
            print_summary: Whether to print filter and DOI summary stats.
            
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

        for data in jittered_datasets:
            data['_iqr_applied'] = False
            data['_rows_before_iqr'] = len(data.get('df', []))
            data['_rows_after_iqr'] = len(data.get('df', []))
            data['_iqr_removed_rows'] = 0
            data['_contributing_dois'] = set()
            data['_doi_col_used'] = None

        # Get entity markers
        entity_marker_map = self._create_entity_marker_map(jittered_datasets)

        # Prepare color scale (exclude size-mode datasets)
        map_jittered = [d for d in jittered_datasets if d.get('plot_mode', 'points') != 'size']
        scalar_map = self._prepare_color_scale(
            map_jittered, cmap, log_scale, apply_iqr,
            iqr_lower_quantile=iqr_lower_quantile,
            iqr_upper_quantile=iqr_upper_quantile,
            iqr_multiplier=iqr_multiplier,
            country_column=country_column, aggregation=aggregation,
            color_scale_range=color_scale_range,
        )

        # Plot each subplot
        default_color = plt.cm.get_cmap(cmap)(0.7)
        data_tables = {}

        for i, data in enumerate(jittered_datasets):
            plot_mode = data.get('plot_mode', 'points')
            dataset_extent = data.get('spatial_extent', spatial_extent)
            dataset_continent = data.get('continent', continent)
            entry_doi_col = self._resolve_existing_column(
                data.get('df'), [data.get('doi_col', doi_col), 'DOI', 'doi']
            )
            data['_doi_col_used'] = entry_doi_col

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

                        data['_contributing_dois'] = self._collect_world_size_contributing_dois(
                            data=data,
                            ghi_data=ghi_data,
                            country_column=country_column,
                            value_column=data.get('value_column'),
                            min_datapoints=data.get('min_datapoints', 1),
                            doi_col=entry_doi_col,
                        )
            elif plot_mode == 'choropleth':
                self._plot_world_choropleth_subplot(
                    axes[i], data, scalar_map, dataset_continent,
                    country_column=country_column,
                    aggregation=aggregation,
                    spatial_extent=dataset_extent,
                    min_datapoints=data.get('min_datapoints', 1),
                    show_rivers=data.get('show_rivers', False),
                    show_roads=data.get('show_roads', False),
                    show_cities=data.get('show_cities', False),
                )
                data['_contributing_dois'] = self._collect_world_choropleth_contributing_dois(
                    data=data,
                    country_column=country_column,
                    value_column=data.get('value_column'),
                    doi_col=entry_doi_col,
                )
            else:  # points mode
                self._plot_world_subplot(
                    axes[i], data, entity_marker_map, scalar_map,
                    default_color, default_point_size, dataset_continent,
                    spatial_extent=dataset_extent,
                    show_rivers=data.get('show_rivers', False),
                    show_roads=data.get('show_roads', False),
                    show_cities=data.get('show_cities', False),
                )
                data['_contributing_dois'] = self._collect_world_points_contributing_dois(
                    data=data,
                    doi_col=entry_doi_col,
                )

        # Add colorbar (only for map subplots)
        map_axes = [a for a in axes if a is not None]
        if scalar_map and map_axes:
            if has_any_size:
                cbar_ax = fig.add_axes([0.92, 0.55, 0.015, 0.35])
                cbar = plt.colorbar(scalar_map, cax=cbar_ax)
                if colorbar_ticks is not None:
                    cbar.set_ticks(colorbar_ticks)
                cbar.ax.set_ylabel(colorbar_title or "Value", fontsize=font_size)
            else:
                self._add_world_colorbar(
                    fig, map_axes, scalar_map, colorbar_title, font_size,
                    colorbar_ticks=colorbar_ticks,
                )

        if not has_any_size:
            plt.subplots_adjust(
                wspace=0.02, hspace=0.02,
                right=0.88 if scalar_map else 0.98
            )

        if print_summary:
            self._print_world_generation_summary(jittered_datasets, apply_iqr)

        return fig, data_tables

    def _collect_world_points_contributing_dois(self, data: dict, doi_col: str | None) -> set:
        """Collect unique DOIs contributing to a points-mode world plot."""
        df = data.get('df')
        if doi_col is None or df is None or doi_col not in df.columns:
            return set()

        dois = set(df[doi_col].dropna().astype(str).str.strip())
        dois.discard('')
        return dois

    def _collect_world_choropleth_contributing_dois(
        self,
        data: dict,
        country_column: str,
        value_column: str | None,
        doi_col: str | None,
    ) -> set:
        """Collect unique DOIs contributing to a choropleth world plot."""
        df = data.get('df')
        if doi_col is None or df is None or doi_col not in df.columns:
            return set()
        if value_column is None or country_column not in df.columns or value_column not in df.columns:
            return set()

        df_clean = df.copy()
        df_clean['country_norm'] = df_clean[country_column].apply(normalize_country_code)
        df_clean = df_clean.dropna(subset=['country_norm', value_column])

        dois = set(df_clean[doi_col].dropna().astype(str).str.strip())
        dois.discard('')
        return dois

    def _collect_world_size_contributing_dois(
        self,
        data: dict,
        ghi_data: dict,
        country_column: str,
        value_column: str | None,
        min_datapoints: int,
        doi_col: str | None,
    ) -> set:
        """Collect unique DOIs contributing to a size-mode world plot."""
        df = data.get('df')
        if doi_col is None or df is None or doi_col not in df.columns:
            return set()
        if value_column is None or country_column not in df.columns or value_column not in df.columns:
            return set()

        df_clean = df.copy()
        df_clean['country_norm'] = df_clean[country_column].apply(normalize_country_code)
        df_clean = df_clean.dropna(subset=['country_norm', value_column])
        if df_clean.empty:
            return set()

        country_count = df_clean.groupby('country_norm')[value_column].count()
        valid_countries = set(country_count.index)
        if min_datapoints > 1:
            valid_countries = set(country_count[country_count >= min_datapoints].index)

        if not valid_countries:
            return set()

        ghi_countries = set(pd.Series(list(ghi_data.keys())).dropna().astype(str))
        valid_countries = {c for c in valid_countries if c in ghi_countries}
        if not valid_countries:
            return set()

        contributing_df = df_clean[df_clean['country_norm'].isin(valid_countries)]
        dois = set(contributing_df[doi_col].dropna().astype(str).str.strip())
        dois.discard('')
        return dois

    def _print_world_generation_summary(self, datasets: list, apply_iqr: bool):
        """Print per-dataset filter stats and overall unique DOI contribution."""
        print("\n=== World Plot Generation Summary ===")

        total_unique_dois = set()
        doi_available_any = False

        for idx, data in enumerate(datasets, start=1):
            title = data.get('title') or f"Dataset {idx}"
            plot_mode = data.get('plot_mode', 'points')

            if data.get('_iqr_applied', False):
                removed = int(data.get('_iqr_removed_rows', 0))
                before = int(data.get('_rows_before_iqr', 0))
                after = int(data.get('_rows_after_iqr', 0))
                print(
                    f"[{idx}] {title} ({plot_mode}) | IQR removed: {removed} values "
                    f"(before={before}, after={after})"
                )
            else:
                if apply_iqr and plot_mode == 'size':
                    print(f"[{idx}] {title} ({plot_mode}) | IQR filter not applied in size mode")
                elif apply_iqr:
                    print(f"[{idx}] {title} ({plot_mode}) | IQR filter not applied")
                else:
                    print(f"[{idx}] {title} ({plot_mode}) | IQR filter disabled")

            doi_col = data.get('_doi_col_used')
            dataset_dois = data.get('_contributing_dois', set())
            if doi_col is None:
                print("    Contributing studies: DOI column not found")
                continue

            doi_available_any = True
            total_unique_dois.update(dataset_dois)
            print(
                f"    Contributing studies ({doi_col}): "
                f"{len(dataset_dois)} unique DOI(s)"
            )

        if doi_available_any:
            print(
                "Total contributing studies in this generated figure: "
                f"{len(total_unique_dois)} unique DOI(s)"
            )
        else:
            print("Total contributing studies in this generated figure: DOI column unavailable")

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
        iqr_lower_quantile: float = 0.25,
        iqr_upper_quantile: float = 0.75,
        iqr_multiplier: float = 1.5,
        country_column: str = "country",
        aggregation: str = "mean",
        color_scale_range: tuple = None,
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
            rows_before_iqr = len(df)

            if apply_iqr and pd.api.types.is_numeric_dtype(df[val_col]):
                if ent_col:
                    df = apply_iqr_filter(df, val_col, ent_col,
                                          lower_quantile=iqr_lower_quantile,
                                          upper_quantile=iqr_upper_quantile,
                                          iqr_multiplier=iqr_multiplier)
                else:
                    df = apply_iqr_filter(
                        df.assign(dummy="x"), val_col, "dummy",
                        lower_quantile=iqr_lower_quantile,
                        upper_quantile=iqr_upper_quantile,
                        iqr_multiplier=iqr_multiplier,
                    ).drop(columns="dummy")
                data['_iqr_applied'] = True

            rows_after_iqr = len(df)
            data['_rows_before_iqr'] = rows_before_iqr
            data['_rows_after_iqr'] = rows_after_iqr
            data['_iqr_removed_rows'] = rows_before_iqr - rows_after_iqr

            df = df.dropna(subset=[val_col])
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

        if color_scale_range is not None:
            if len(color_scale_range) != 2:
                raise ValueError("color_scale_range must be a tuple of (vmin, vmax).")
            vmin, vmax = color_scale_range
            if vmin is None or vmax is None:
                raise ValueError("color_scale_range values cannot be None.")
            vmin = float(vmin)
            vmax = float(vmax)
            if vmin > vmax:
                vmin, vmax = vmax, vmin
        else:
            vmin = float(all_vals.min())
            vmax = float(all_vals.max())

        if log_scale:
            if vmin <= 0:
                raise ValueError("For log_scale=True, color_scale_range vmin must be > 0.")
            if color_scale_range is None:
                min_pos = all_vals[all_vals > 0].min()
                vmin = max(float(min_pos), 1e-12)
            else:
                vmin = max(vmin, 1e-12)
            norm = LogNorm(vmin=vmin, vmax=vmax)
        else:
            norm = plt.Normalize(vmin=vmin, vmax=vmax)

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
        show_rivers: bool = False,
        show_roads: bool = False,
        show_cities=False,
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
        if show_rivers:
            ax.add_feature(cfeature.RIVERS, edgecolor='steelblue', linewidth=0.5)
        if show_roads:
            self._add_roads_to_ax(ax, show_roads)

        # Set extent (spatial_extent takes precedence over continent)
        # For global/world views, set_global() is sufficient â€” calling set_extent
        # with [-180,180] in PlateCarree would clip the Robinson oval to a rectangle.
        if spatial_extent:
            ax.set_extent(spatial_extent, crs=ccrs.PlateCarree())
        elif continent and continent != 'World':
            ax.set_extent(CONTINENT_BOUNDS[continent], crs=ccrs.PlateCarree())

        if show_cities:
            self._add_cities_to_ax(ax, show_cities)

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
        show_rivers: bool = False,
        show_roads: bool = False,
        show_cities=False,
    ):
        """Plot a single world map subplot as a choropleth (countries filled by value).
        
        Args:
            min_datapoints: Minimum number of data points a country must have
                to be colored. Countries below this threshold are shown in grey.
            show_rivers: Whether to draw rivers on the map.
            show_roads: Whether to draw major roads on the map.
            show_cities: Whether to draw the largest cities on the map.
        """
        df = data['df']
        value_col = data.get('value_column')
        title = data.get('title', '')

        # Set up map
        ax.set_global()
        ax.coastlines()
        ax.add_feature(cfeature.BORDERS, edgecolor='black', linewidth=0.5)
        ax.add_feature(cfeature.OCEAN, facecolor='white')
        if show_rivers:
            ax.add_feature(cfeature.RIVERS, edgecolor='steelblue', linewidth=0.5)
        if show_roads:
            self._add_roads_to_ax(ax, show_roads)

        # Set extent (spatial_extent takes precedence over continent)
        # For global/world views, set_global() is sufficient â€” calling set_extent
        # with [-180,180] in PlateCarree would clip the Robinson oval to a rectangle.
        if spatial_extent:
            ax.set_extent(spatial_extent, crs=ccrs.PlateCarree())
        elif continent and continent != 'World':
            ax.set_extent(CONTINENT_BOUNDS[continent], crs=ccrs.PlateCarree())

        if show_cities:
            self._add_cities_to_ax(ax, show_cities)

        # Aggregate values per country (normalized)
        low_count_set: set = set()
        if value_col and country_column in df.columns:
            # Normalize country codes first
            df_normalized = df.copy()
            df_normalized['country_norm'] = df_normalized[country_column].apply(normalize_country_code)
            
            df_clean = df_normalized.dropna(subset=['country_norm', value_col])
            
            country_counts = df_clean.groupby('country_norm')[value_col].count()

            # Track countries with data but below the threshold for hatching
            if min_datapoints > 1:
                low_count_set = set(
                    country_counts[(country_counts > 0) & (country_counts < min_datapoints)].index
                )

            # Include all countries with at least one data point so low-count
            # countries still receive their computed colour (shown with hatching).
            all_with_data = country_counts[country_counts > 0].index
            country_agg = (
                df_clean[df_clean['country_norm'].isin(all_with_data)]
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

            # Overlay hatching for countries below the min_datapoints threshold
            if low_count_set:
                is_low_count = (
                    country_iso3 in low_count_set
                    or country_iso2 in low_count_set
                    or country_name in low_count_set
                    or (country_name and normalize_country_code(country_name) in low_count_set)
                )
                if is_low_count:
                    ax.add_geometries(
                        [geometry], ccrs.PlateCarree(),
                        facecolor='none',
                        edgecolor='white',
                        linewidth=0.5,
                        hatch='////',
                    )

        ax.set_title(title, loc='left', fontweight='bold', pad=10)

    def _add_roads_to_ax(self, ax, road_type):
        """Add road geometries to a cartopy axes, filtered by road type.

        Args:
            ax: Cartopy GeoAxes to draw on.
            road_type: One of:
                - True / 'all'          â€” all roads in the dataset
                - 'highway'             â€” Major Highways only
                - 'secondary'           â€” Major + Secondary Highways
        """
        ROAD_TYPE_FILTER = {
            True:        None,          # no filter â†’ all roads
            'all':       None,
            'highway':   {'Major Highway'},
            'secondary': {'Major Highway', 'Secondary Highway'},
        }
        allowed = ROAD_TYPE_FILTER.get(road_type)

        shpfilename = shpreader.natural_earth(
            resolution='10m', category='cultural', name='roads'
        )
        reader = shpreader.Reader(shpfilename)
        geometries = [
            record.geometry
            for record in reader.records()
            if allowed is None or record.attributes.get('type') in allowed
        ]
        if geometries:
            ax.add_geometries(
                geometries, ccrs.PlateCarree(),
                facecolor='none', edgecolor='#c0392b', linewidth=0.5,
            )

    def _add_cities_to_ax(self, ax, city_option):
        """Add the largest cities to a cartopy axes.

        Args:
            ax: Cartopy GeoAxes to draw on.
            city_option: One of:
                - True   â€” show the 10 largest cities
                - int    â€” show the N largest cities
        """
        n_cities = city_option if isinstance(city_option, int) else 10

        shpfilename = shpreader.natural_earth(
            resolution='10m', category='cultural', name='populated_places'
        )
        reader = shpreader.Reader(shpfilename)

        cities = []
        for record in reader.records():
            pop = record.attributes.get('POP_MAX', 0) or 0
            name = record.attributes.get('NAME', '')
            lon = record.attributes.get('LONGITUDE', record.geometry.x)
            lat = record.attributes.get('LATITUDE', record.geometry.y)
            cities.append((name, pop, lon, lat))

        cities.sort(key=lambda c: c[1], reverse=True)
        top_cities = cities[:n_cities]

        for name, _pop, lon, lat in top_cities:
            ax.plot(
                lon, lat,
                marker='o', color='black', markersize=3,
                transform=ccrs.PlateCarree(),
                zorder=5,
            )
            ax.text(
                lon + 0.5, lat + 0.5, name,
                fontsize=6, fontweight='bold',
                transform=ccrs.PlateCarree(),
                zorder=5,
            )

    def _add_world_colorbar(
        self,
        fig,
        axes,
        scalar_map,
        colorbar_title: str,
        font_size: int,
        colorbar_ticks: list = None,
    ):
        """Add colorbar to world map figure."""
        cbar = plt.colorbar(
            scalar_map, ax=axes,
            orientation="vertical",
            fraction=0.005, pad=0.01, shrink=0.5
        )
        if colorbar_ticks is not None:
            cbar.set_ticks(colorbar_ticks)
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

        # Build name â†’ ISO3 mapping from Natural Earth shapefile
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
        ax.set_xlabel('Solar Radiation GHI [kWh/mÂ²/day]', fontsize=font_size - 1)
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

