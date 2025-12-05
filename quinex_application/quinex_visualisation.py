import os
import requests
import ast
import math
import scipy.stats as st
import pandas as pd
import numpy as np
import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.lines as mlines
import matplotlib.ticker as mticker
import seaborn as sns
import cartopy.crs as ccrs
import cartopy.feature as cfeature


class QuinexVisualisation():
    """
    Visualizes the results observed using quinex.
    """
    
    def __init__(self):
        """
        Initializes the visualisation client.
        """

        pd.set_option('display.max_colwidth', None)
        self.color = sns.color_palette("dark:steelblue", 6)[2]
        self.color2 = sns.color_palette("dark:cyan", 6)[2]

        sns.set_theme(style="ticks")
        sns.set_context("paper", font_scale=3)

    # ----------------------------------- Functions for Loading and Saving Data -----------------------------------------------------------

    def load_df(self, path="df_quinex.parquet"):
        """
        Loads the DataFrame from disk.

        Args:
            path (str): File path of the saved DataFrame.
        """

        if not os.path.exists(path):
            raise FileNotFoundError(f"No saved DataFrame found at '{path}'")

        df = pd.read_parquet(path)
        print(f"📂 Loaded DataFrame from '{path}' with {len(df)} rows")
        return df
    

    # ----------------------------------- Postprocessing of the Data ----------------------------------------------------------

    def convert_unit(self, value, input, output, year, parse):
        url = "http://134.94.117.230:8000/api/units/convert_units/"

        payload = {
            "value": value,
            "input_unit": str(input),
            "output_unit": str(output),
            "year": year,
            "parse": parse,
        }

        response = requests.post(url, json=payload)
        return response.json()
    
    def convert_row(self, row, target_unit, year=None):
        # Input-Unit aus der Zeile
        input_unit = row["unit_normalized"]
        output_unit = target_unit
        value = row['value_normalized']
        if not year:
            year = row['publication_year']  # Zieljahr aus der Zeile
        
        # API-Aufruf
        if pd.isna(value):
            return None
        try:
            result = self.convert_unit(value, input_unit, output_unit, year, False)
        except:
            return None
        return result[0]
        

    # ----------------------------------- Functions for Graphics -----------------------------------------------------------
    
    def plot_top_values(self, df, column, top_n=10, ignore_empty=True, figsize=(6,6), title=None):
        """
        Creates a bar plot of the top N most frequent values.

        Args:
            df (pd.DataFrame): The DataFrame containing the data.
            column (str): The original column name (e.g., 'entity').
            top_n (int): Number of top values to display.
            ignore_empty (bool): Whether to exclude empty or null values.
            figsize (tuple): Size of the figure.
            title (str): The title of the plot.
        """

        data = df[column]

        if ignore_empty:
            data = data.dropna()

        cleaned_data = (
            data.astype(str)
            .str.replace(r"\s+", " ", regex=True)
            .str.strip()
        )
        cleaned_data = cleaned_data[cleaned_data != ""]  # Leere rausfiltern

        value_counts = cleaned_data.value_counts().nlargest(top_n)

        fig, ax = plt.subplots(figsize=figsize)
        sns.barplot(x=value_counts.values, y=value_counts.index, ax=ax, color="steelblue")

        ax.set_xlabel("Count")
        ax.set_ylabel(column.capitalize())
        ax.grid(axis='x')
        #ax.set_title(label=title if title else f"Top {top_n} values in '{column}'", fontsize=14, pad=15)


        plt.tight_layout()
        return fig
    

    def plot_multiple_properties_over_time(
        self, 
        data_list: list,
        legend_title: str,
        color_dict: dict = None,
        figsize: tuple =(16, 8),
        legend_position = (1,0.8),
        legend_size_position = (1,0.4),
        central_tendency: str ="mean",
        error_type : str="se",
        error_display: str = None,
        iqr_filter: bool = True,
        font_size: int = 14
    ): 
        """
        Plots properties over time with custom color palette and optional IQR filtering.

        Args:
            data_list (list): List of dicts, each with keys: 'df', 'entity_col', 'value_col', 'ylabel', 'title'
            legend_title (str): Legend title.
            figsize (tuple): Figure size.
            iqr_filter (bool): Whether to remove outliers using IQR.
            plot_type (str): Type of plot to create ("scatter" or "box" or "line").
            central_tendency (str): Type of centraling used for creating the lineplot ("mean" or "median" or "moving average")
            error_type (str): 'se' or 'ci'
            error_display (str): Wether to display an error - 'bars' or 'shade'
        """


        mpl.rcParams.update({
            'axes.titlesize': font_size,
            'axes.labelsize': font_size,
            'xtick.labelsize': font_size,
            'ytick.labelsize': font_size,
            'legend.fontsize': font_size,
            'legend.title_fontsize': font_size
        })

        n_plots = len(data_list)
        ncols = 2 if n_plots > 1 else 1
        nrows = math.ceil(n_plots / ncols)

        fig, axes = plt.subplots(nrows, ncols, figsize=figsize, sharey=False)
        axes = axes.flatten() if n_plots > 1 else [axes]

        # ------------------------------
        # Einheitliche Farbpalette für alle Entities
        # ------------------------------
        all_entities = []
        all_n_vals = []

        # Sammle alle Entities und n-Werte über alle DataFrames
        for data in data_list:
            df = data['df']
            entity_col = data['entity_col']
            value_col = data['value_col']

            if iqr_filter:
                df = self.apply_iqr_filter(df, value_col, entity_col)

            # Temporal Scope
            df['temporal_scope'] = df['temporal_scope'].apply(
                lambda x: x if isinstance(x, dict) else ({'year': ast.literal_eval(x)['year']} if isinstance(x, str) else {'year': x})
            )
            df['jahr'] = df['temporal_scope'].apply(lambda x: x.get('year', pd.NA))
            df['jahr'] = pd.to_numeric(df['jahr'], errors='coerce')
            df['jahr'] = df['jahr'].fillna(df['publication_year']).astype(int)

            # Aggregates
            agg_df = self.calculate_aggregates(df, entity_col, value_col, central_tendency, error_type)
            agg_df = agg_df[agg_df['n'] >= 5]

            all_entities.extend(agg_df[entity_col].unique())
            all_n_vals.extend(agg_df['n'].dropna().astype(int).unique())

        all_entities = sorted(list(set(all_entities)))
        if color_dict is None:
            palette_colors = sns.color_palette("tab10", n_colors=len(all_entities))
            color_dict = dict(zip(all_entities, palette_colors))

        # Einheitliche min/max Werte für Scatter-Größen
        min_n, max_n = min(all_n_vals), max(all_n_vals)
        size_range = (50, 200)

        # Mapping n -> s
        def map_n_to_s(n):
            return np.interp(n, [min_n, max_n], [size_range[0], size_range[1]])


        # ------------------------------
        # Plotten der einzelnen Subplots
        # ------------------------------
        for i, data in enumerate(data_list):
            ax = axes[i]
            df = data['df'].copy()
            entity_col = data['entity_col']
            value_col = data['value_col']
            ylabel = data['ylabel']
            title = data.get('title', '')

            if iqr_filter:
                df = self.apply_iqr_filter(df, value_col, entity_col)

            # Temporal Scope
            df['temporal_scope'] = df['temporal_scope'].apply(
                lambda x: x if isinstance(x, dict) else ({'year': ast.literal_eval(x)['year']} if isinstance(x, str) else {'year': x})
            )
            df['jahr'] = df['temporal_scope'].apply(lambda x: x.get('year', pd.NA))
            df['jahr'] = pd.to_numeric(df['jahr'], errors='coerce')
            df['jahr'] = df['jahr'].fillna(df['publication_year']).astype(int)
            
            # Aggregates
            agg_df = self.calculate_aggregates(df, entity_col, value_col, central_tendency, error_type)
            agg_df = agg_df[agg_df['n'] >= 5]

            # Neue Spalte für gemappte Punktgrößen
            agg_df['size_mapped'] = map_n_to_s(agg_df['n'].fillna(min_n))


            # ------------------------------
            # Lineplot
            # ------------------------------
            sns.lineplot(
                data=agg_df,
                x='jahr',
                y='value_central',
                hue=entity_col,
                palette=color_dict,
                ax=ax,
            )

            # ------------------------------
            # Scatterplot (einheitliche Größen)
            # ------------------------------
            ax.scatter(
                agg_df['jahr'],
                agg_df['value_central'],
                s=agg_df['size_mapped'],
                c=agg_df[entity_col].map(color_dict),
                edgecolor='w',
                linewidth=0.3,
                alpha=0.9,
            )
            # sns.scatterplot(
            #     data=agg_df,
            #     x='jahr',
            #     y='value_central',
            #     hue=entity_col,
            #     size='size_mapped',
            #     sizes=size_range,  # Skaliere je nach Geschmack
            #     palette=color_dict,
            #     legend=False,
            #     ax=ax,
            #     marker='o',
            # )

            # ------------------------------
            # Fehlerbalken oder Shade
            # ------------------------------
            if error_display == "bars":
                for entity in agg_df[entity_col].unique():
                    entity_df = agg_df[agg_df[entity_col] == entity].copy()

                    if error_type == "se" and 'se' in entity_df.columns:
                        yerr = entity_df['se']
                    elif error_type == "ci" and 'ci' in entity_df.columns:
                        yerr = entity_df['ci']
                    else:
                        continue

                    ax.errorbar(
                        x=entity_df['jahr'],
                        y=entity_df['value_central'],
                        yerr=yerr,
                        fmt='none',           # Keine Linie, nur Fehlerbalken
                        ecolor='gray',        # Farbe der Balken
                        elinewidth=1,
                        capsize=3,            # Endkappen an Balken
                        alpha=0.6,
                        label=None
                    )
            
            elif error_display == "shade":
                for entity in agg_df[entity_col].unique():
                    entity_df = agg_df[agg_df[entity_col] == entity].sort_values('jahr')

                    if error_type == "se" and 'se' in entity_df.columns:
                        lower = entity_df['value_central'] - entity_df['se']
                        upper = entity_df['value_central'] + entity_df['se']

                    elif error_type == "ci" and 'ci_lower' in entity_df.columns:
                        lower = entity_df['ci_lower']
                        upper = entity_df['ci_upper']

                    else:
                        continue

                    ax.fill_between(
                        entity_df['jahr'],
                        lower,
                        upper,
                        color=color_dict[entity],
                        alpha=0.2
                    )

            # ------------------------------
            # Achsen, Gitter und Titel
            # ------------------------------
            ax.set_xlabel('Year')
            ax.set_ylabel(ylabel)
            ax.grid(linestyle='--', alpha=0.6)
            ax.xaxis.set_major_locator(mticker.MultipleLocator(5))
            ax.set_title(title, loc='left', fontweight='bold')
        
            # Legende lokal entfernen
            if ax.get_legend() is not None:
                ax.get_legend().remove()

        # ------------------------------
        # Gemeinsame Farb-Legende
        # ------------------------------
        handles = [plt.Line2D([0],[0], color=color_dict[e], lw=2) for e in all_entities]
        fig.legend(
            handles=handles, 
            labels=all_entities, 
            title=legend_title,
            bbox_to_anchor=legend_position, 
            loc='upper left',
        )

        # ------------------------------
        # Gemeinsame Größen-Legende
        # ------------------------------
        size_handles = self.create_size_legend_handles(ax, np.sort(np.unique(all_n_vals)), size_range[0], size_range[1])
        fig.legend(
            handles=size_handles, 
            title='Sample Size', 
            bbox_to_anchor=legend_size_position, 
            loc='upper left',
        )
        
        plt.tight_layout()     
        return fig
        

    def plot_multiple_datasets_on_world(
        self,
        datasets: list,
        colorbar_title: str = None,
        figsize=(14, 7),
        default_point_size=60,
        jitter_strength=0.0,
        cmap="viridis",
    ):    
        """
        Plots multiple datasets on a shared world map, encoding numeric values via color
        and (optionally) categorical entities via marker shape.

        Args:
            datasets (list): List of dicts, each with keys:
                            - 'df': pandas DataFrame with 'latitude' and 'longitude'.
                            - 'value_column': str, numeric column used for the color gradient.
                            - 'entity_column': (optional) str, categorical column for marker shapes.
                            - 'title': Title for the subplot, e.g., 'a) Wind Turbine'.
            colorbar_title (str): Title for the color scale shown to the right of the world map.
            figsize (tuple): Size of the figure in inches.
            default_point_size (float): Size of the markers.
            jitter_strength (float): Random spatial jitter (in degrees) applied to avoid overlapping points.
            cmap (str): Color map used for the values.
        """

        n_plots = len(datasets)
        ncols = 2 if n_plots > 1 else 1
        nrows = math.ceil(n_plots / ncols)
        fig, axes = plt.subplots(nrows, ncols, figsize=figsize, subplot_kw={'projection': ccrs.PlateCarree()})
        axes = axes.flatten() if n_plots > 1 else [axes]

        # -------------------------------------------
        # 1) Filter per dataset (IQR) if value_column exists
        # -------------------------------------------
        all_vals = []
        for data in datasets:
            df = data["df"].copy()
            val_col = data["value_column"]

            if val_col not in df.columns:
                raise ValueError(f"Value column '{val_col}' not found in dataset.")

            ent_col = data.get("entity_column", None)

            if pd.api.types.is_numeric_dtype(df[val_col]):
                if ent_col:
                    df = self.apply_iqr_filter(df, val_col, ent_col)
                else:
                    df = self.apply_iqr_filter(df.assign(dummy="x"), val_col, "dummy").drop(columns="dummy")

            data['df'] = df
            all_vals.append(df[val_col])

        # Combine all values for global color scaling
        all_vals = pd.concat(all_vals)
        vmin, vmax = all_vals.min(), all_vals.max()
        norm = plt.Normalize(vmin=vmin, vmax=vmax)
        scalar_map = plt.cm.ScalarMappable(cmap=cmap, norm=norm)

        # -------------------------------------------
        # 2) Jitter
        # -------------------------------------------
        jittered_datasets = self.apply_jitter_to_datasets(datasets, jitter_strength)

        # -------------------------------------------
        # 3) Marker shapes (if entity_col provided)
        # -------------------------------------------
        marker_cycle = ["o", "s", "^", "D", "P", "X", "v", "<", ">"]
        entity_marker_map = {}

        # Collect all entity categories
        all_entities = []
        for data in jittered_datasets:
            ent_col = data.get("entity_column", None)
            if ent_col:
                all_entities.extend(data["df"][ent_col].dropna().unique())

        all_entities = sorted(list(set(all_entities)))

        for i, ent in enumerate(all_entities):
            entity_marker_map[ent] = marker_cycle[i % len(marker_cycle)]

        # -------------------------------------------
        # 4) Plotting
        # -------------------------------------------
        for i, data in enumerate(datasets):
            ax = axes[i]
            df = data['df']
            value_col = data['value_column']
            entity_col = data.get('entity_column', None)
            title = data.get('title', '')

            # Weltkarte
            ax.set_global()
            ax.coastlines()
            ax.add_feature(cfeature.BORDERS, edgecolor='black')
            ax.add_feature(cfeature.LAND, facecolor='lightgray')
            ax.gridlines(linewidth=0.5, color='gray', linestyle='--')

            # Scatter
            for _, row in df.iterrows():
                color = scalar_map.to_rgba(row[value_col])
                marker = entity_marker_map[row[entity_col]] if entity_col else 'o'
                ax.scatter(
                    row['longitude'],
                    row['latitude'],
                    color=color,
                    s=default_point_size,
                    marker=marker,
                    transform=ccrs.PlateCarree(),
                    edgecolor='black',
                    linewidth=0.5
                )

            # Untertitel / Buchstabenlabel
            ax.set_title(title, loc='left', fontweight='bold')

        # -------------------------------------------
        # 5) Add colorbar on the right
        # -------------------------------------------
        cbar = plt.colorbar(
            scalar_map,
            ax=ax,
            orientation="vertical",
            fraction=0.015,     # << smaller
            pad=0.02            # << tighter
        )
        cbar.ax.set_ylabel(colorbar_title if colorbar_title else "Value", fontsize=14)

        # -------------------------------------------
        # 6) Add legend for entity markers (if needed)
        # -------------------------------------------
        if all_entities:
            handles = [
                plt.Line2D(
                    [0], [0],
                    marker=entity_marker_map[e],
                    linestyle="",
                    markersize=10,
                    color="black",
                    label=str(e)
                )
                for e in entity_marker_map
            ]

            ax.legend(
                handles=handles,
                title="Entity",
                loc="lower left",
                frameon=True
            )

        return fig

    # ----------------------------------- Helper Functions -----------------------------------------------------------

    def apply_iqr_filter(self, df: pd.DataFrame, value_column: str, entity_col: str) -> pd.DataFrame:
        """
        Removes outliers from a column using the IQR method.

        Args:
            df (pd.DataFrame): Input DataFrame.
            value_column (str): Column on which to apply the IQR filter.

        Returns:
            pd.DataFrame: Filtered DataFrame without outliers.
        """

        def filter_group(df):
            Q1 = df[value_column].quantile(0.20)
            Q3 = df[value_column].quantile(0.80)
            IQR = Q3 - Q1
            lower = Q1 - 1.5 * IQR
            upper = Q3 + 1.5 * IQR
            return df[(df[value_column] >= lower) & (df[value_column] <= upper)]
    
        return df.groupby(entity_col, group_keys=False).apply(filter_group)

    

    def calculate_aggregates(self, df: pd.DataFrame, entity_col: str, value_col: str, central_tendency: str, error_type: str):
        """
        Aggregate DataFrame by 'jahr' and entity_col based on central tendency method.

        Args:
            df (pd.DataFrame): Input DataFrame with 'jahr' column.
            central_tendency (str): 'mean', 'median' or 'moving average'.
            error_type (str): 'se' or 'ci'
        """

        if central_tendency == "median":
            agg_df = df.groupby(['jahr', entity_col])[value_col].agg(['median', 'count']).reset_index()
            agg_df = agg_df.rename(columns={'median': 'value_central', 'count': 'n'})
            agg_df['std_dev'] = df.groupby(['jahr', entity_col])[value_col].std().values
            agg_df['se'] = agg_df['std_dev'] / np.sqrt(agg_df['n'])
            
        elif central_tendency == "mean":
            agg_df = df.groupby(['jahr', entity_col])[value_col].agg(['mean', 'std', 'count']).reset_index()
            agg_df = agg_df.rename(columns={'mean': 'value_central', 'std': 'std_dev', 'count': 'n'})
            agg_df['se'] = agg_df['std_dev'] / np.sqrt(agg_df['n'])
            agg_df['se'] = agg_df['se'].astype(float)

            if error_type == "ci":
                # t-Wert: df = n-1
                agg_df['t_val'] = agg_df['n'].apply(lambda n: st.t.ppf(0.975, n-1) if n > 1 else np.nan)
                agg_df['ci'] = agg_df['t_val'] * agg_df['se']
                agg_df['ci_lower'] = agg_df['value_central'] - agg_df['ci']
                agg_df['ci_upper'] = agg_df['value_central'] + agg_df['ci']

        elif central_tendency == "moving average":
            all_years = pd.DataFrame({'jahr': range(df['jahr'].min(), df['jahr'].max() + 1)})
            entities = df[entity_col].unique()
            full_index = pd.MultiIndex.from_product([all_years['jahr'], entities], names=['jahr', entity_col]).to_frame(index=False)

            mean_values = df.groupby(['jahr', entity_col])[value_col].mean().reset_index()
            agg_df = full_index.merge(mean_values, on=['jahr', entity_col], how='left').sort_values([entity_col, 'jahr'])
            agg_df['value_central'] = agg_df.groupby(entity_col)[value_col].transform(
                lambda x: x.rolling(window=3, center=True, min_periods=1).mean()
            )
            count_df = df.groupby(['jahr', entity_col]).size().reset_index(name='n')
            agg_df = agg_df.merge(count_df, on=['jahr', entity_col], how='left')

            agg_df = agg_df[~agg_df[value_col].isna()]

            agg_df['std_dev'] = agg_df.groupby(entity_col)[value_col].transform(
                lambda x: x.rolling(window=3, center=True, min_periods=1).std()
            )
            agg_df['n_window'] = agg_df.groupby(entity_col)[value_col].transform(
                lambda x: x.rolling(window=3, center=True, min_periods=1).count()
            )
            agg_df['se'] = agg_df['std_dev'] / np.sqrt(agg_df['n_window'])

            
            if error_type == "ci":
                agg_df['t_val'] = agg_df['n_window'].apply(lambda n: st.t.ppf(0.975, n-1) if n > 1 else np.nan)
                agg_df['ci'] = agg_df['t_val'] * agg_df['se']
                agg_df['ci_lower'] = agg_df['value_central'] - agg_df['ci']
                agg_df['ci_upper'] = agg_df['value_central'] + agg_df['ci']

        else:
            raise ValueError(f"Unknown central_tendency: {central_tendency}")

        unique_years = sorted(agg_df['jahr'])
        if len(unique_years) >= 2 and (unique_years[1] - unique_years[0]) >= 10:
            agg_df = agg_df[agg_df['jahr'] != unique_years[0]]

        agg_df['n'] = agg_df['n'].astype(float)
        return agg_df.sort_values(by='n', ascending=False)
    

    def create_size_legend_handles(self, ax, n_vals, min_size=20, max_size=100):
        """
        Create legend handles for sample sizes.

        Args:
            ax (matplotlib.axes.Axes): Axes object.
            n_vals (array-like): Unique sample size values.
            min_size (int): Minimum marker size.
            max_size (int): Maximum marker size.
        """
        def scale_size(n):
            if max(n_vals) == min(n_vals):
                return (min_size + max_size) / 2
            return min_size + (n - min(n_vals)) * (max_size - min_size) / (max(n_vals) - min(n_vals))

        legend_n_vals = []
        if len(n_vals) >= 3:
            legend_n_vals = [n_vals[0], int(np.median(n_vals)), n_vals[-1]]
        elif len(n_vals) == 2:
            legend_n_vals = list(n_vals)
        elif len(n_vals) == 1:
            legend_n_vals = [n_vals[0]]

        handles = [
            ax.scatter([], [], s=scale_size(n), color='gray', alpha=0.6, label=f'n = {n}')
            for n in legend_n_vals
        ]
        return handles
    

    def style_legend_frame(self, legend):
        """
        Defies the style of the Legend.

        Args:
            legend (_type_): The legend for which to define the style.
        """
        frame = legend.get_frame()
        frame.set_edgecolor('black')
        frame.set_linewidth(0.4)
        frame.set_alpha(1)


    def create_color_legend(self, ax, fig, color_map, categories, color_legend_title, color_legend_position = (0,0)):
        """
        Adds a shared color legend to the plot for all category types.

        Args:
            ax (matplotlib.axes._subplots.AxesSubplot): The axis to add the legend to.
            fig (matplotlib.figures._subplots.FiguresSubplot): The figure to plot on.
            color_map (dict): Mapping from category to color.
            categories (list): List of category names to include in the legend.
            color_legedn_title (str): Title for the color legend.
        """
        
        handles_color = [
            mlines.Line2D(
                [], [], marker='X', linestyle='None',
                markersize=10, markerfacecolor=color_map[cat],
                markeredgecolor='black', label=cat
            )
            for cat in categories
        ]
        color_legend = fig.legend(
            handles=handles_color,
            title=color_legend_title,
            loc='lower left',
            bbox_to_anchor=color_legend_position,
            frameon=True
        )
        ax.add_artist(color_legend)
        self.style_legend_frame(color_legend)

    
    def plot_dataset_on_ax(self, ax, fig, dataset, color_map, default_point_size, i):
        """
        Plots one dataset on a given axis, with optional value-based sizing and color-based grouping.
        Adds an individual size legend if applicable.

        Args:
            ax (matplotlib.axes._subplots.AxesSubplot): The axis to plot on.
            fig (matplotlib.figures._subplots.FiguresSubplot): The figure to plot on.
            dataset (dict): Dictionary with keys needed from data.
            color_map (dict): Mapping from category to color.
            default_point_size (float): Size to use if no value_column is provided.
            i (int): Index of the dataset, used for default legend positioning.
        """

        df = dataset['df']
        marker = dataset.get('marker', 'o')
        value_column = dataset.get('value_column', None)
        color_column = dataset.get('color_column', None)
        size_legend_title = dataset.get('size_legend_title', None)
        size_legend_position = dataset.get('size_legend_position', None)

        if value_column:
            values = df[value_column]
            min_size, max_size = default_point_size, default_point_size*20
            sizes = self.calculate_marker_sizes(values, min_size, max_size)
        else:
            sizes = np.full(len(df), default_point_size)

        if color_column:
            for cat in df[color_column].unique():
                subset = df[df[color_column] == cat]
                subset_sizes = sizes[subset.index] if value_column else default_point_size
                ax.scatter(
                    subset['longitude'],
                    subset['latitude'],
                    s=subset_sizes,
                    color=color_map[cat],
                    alpha=1,
                    transform=ccrs.PlateCarree(),
                    edgecolor='black',
                    linewidth=0.5,
                    marker=marker
                )
        else:
            ax.scatter(
                df['longitude'],
                df['latitude'],
                s=sizes,
                color='steelblue',
                alpha=0.6,
                transform=ccrs.PlateCarree(),
                edgecolor='black',
                linewidth=0.5,
                marker=marker
            )

        # Size-Legende zurückgeben
        if value_column:
            legend_values = np.quantile(values, [0.1, 0.5, 0.9])
            legend_values = np.round(legend_values, 1)
            min_size, max_size = default_point_size, default_point_size*20
            legend_sizes = self.calculate_marker_sizes(np.array(legend_values), min_size, max_size)
            handles = [
                plt.scatter([], [], s=s, color='steelblue', alpha=0.6, edgecolor='black', marker=marker, label=f"{v:.2f}")
                for s, v in zip(legend_sizes, legend_values)
            ]
            size_legend = fig.legend(
                handles=handles,
                title=size_legend_title,
                loc='lower left',
                bbox_to_anchor=size_legend_position,
                frameon=True
            )
            ax.add_artist(size_legend)
            self.style_legend_frame(size_legend)

    
    def calculate_marker_sizes(self, values, min_size=30, max_size=600):
        """
        Scales a numeric Series to marker sizes between min_size and max_size.

        Args:
            values (pd.Series or np.array): Numeric values to scale.
            min_size (float): Minimum marker size.
            max_size (float): Maximum marker size.
        """

        if values.max() == values.min():
            return np.full(len(values), (min_size + max_size) / 2)
        return min_size + (values - values.min()) / (values.max() - values.min()) * (max_size - min_size)
    

    def get_color_map(self, datasets, color_column, palette=None):
        """
        Creates a color mapping for categorical values across multiple datasets.

        Args:
            datasets (list): List of dicts, each containing a DataFrame under key 'df'.
            color_column (str): Column name in each DataFrame specifying categories to color by.
            palette (dict or None): Optional dictionary mapping category names to color codes. If None, a seaborn color palette is used.
        """

        seen = set()
        all_color_values = []

        for d in datasets:
            color_counts = d['df'][color_column].value_counts()
            color_order = color_counts.index.tolist()
            for cat in color_order:
                if cat not in seen:
                    seen.add(cat)
                    all_color_values.append(cat)

        if palette:
            color_map = {cat: palette.get(cat, "#CCCCCC") for cat in all_color_values}
        else:
            color_list = sns.color_palette("tab10", n_colors=len(all_color_values))
            color_map = dict(zip(all_color_values, color_list))
        return color_map, all_color_values
    
    def apply_jitter_to_datasets(self, datasets, jitter_strength=0.2):
        """
        Applies a random shift on the latitude and longitude scale on all DataFrames in the Datasets-list to reduce point overlays.

        Args:
            datasets (list): List of Dictionaries with 'df' as key for DataFrames
            jitter_strength (float): Maximum Shift in Degree. Defaults to 0.2.
        """

        jittered = []
        for d in datasets:
            d_copy = d.copy()
            df = d_copy['df'].copy()
            df['latitude'] += np.random.uniform(-jitter_strength, jitter_strength, size=len(df))
            df['longitude'] += np.random.uniform(-jitter_strength, jitter_strength, size=len(df))
            d_copy['df'] = df
            jittered.append(d_copy)
        return jittered
    

    def convert_spatial(self, df):
        df = df[df['spatial_scope'].notna()]
        df['spatial_scope'] = df['spatial_scope'].apply(
            lambda x: x if isinstance(x, dict)
            else ast.literal_eval(x) if isinstance(x, str)
            else {'country': None, 'latitude': None, 'longitude': None}
        )

        df['latitude'] = df['spatial_scope'].apply(
            lambda x: float(x['latitude']) if isinstance(x, dict) and 'latitude' in x else None
        )

        df['longitude'] = df['spatial_scope'].apply(
            lambda x: float(x['longitude']) if isinstance(x, dict) and 'longitude' in x else None
        )
        return df
