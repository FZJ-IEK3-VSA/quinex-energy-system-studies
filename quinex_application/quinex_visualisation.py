import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.lines as mlines
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
        ax.set_title(label=title if title else f"Top {top_n} values in '{column}'", fontsize=14, pad=15)


        plt.tight_layout()
        return fig
    

    def plot_properties_over_time(self, df: pd.DataFrame, ylabel: str, title: str, legend_title: str, figsize: tuple =(12, 6), iqr_filter: bool =True, palette: dict =None, plot_type: str = "scatter", central_tendency: str ="mean"):
        """
        Plots properties over time with custom color palette and optional IQR filtering.

        Args:
            df (pd.DataFrame): Input DataFrame.
            ylabel (str): Y-axis label.
            title (str): Plot title.
            legend_title (str): Legend title.
            figsize (tuple): Figure size.
            iqr_filter (bool): Whether to remove outliers using IQR.
            palette (dict or str): Seaborn-compatible color palette.
            plot_type (str): Type of plot to create ("scatter" or "box" or "line").
            central_tendency (str): Type of centraling used for creating the lineplot ("mean" or "median" or "moving average")
        """

        df = df.copy()

        if iqr_filter:
            df = self.apply_iqr_filter(df, column='value_normalized')
        
        if not palette:
            palette ='dark'

        sns.set_context("paper", font_scale=1.2)
        fig, ax = plt.subplots(figsize=figsize)

        df['jahr'] = df['temporal_scope'].apply(
            lambda x: x['year'] if isinstance(x, dict) and 'year' in x else pd.NA
        )
        if plot_type == "scatter":
            df['jahr'] = pd.to_numeric(df['jahr'], errors='coerce')
            df['jahr'] = df['jahr'].fillna(df['publication_year']).astype(int)

            sns.scatterplot(
                data=df,
                x='jahr',
                y='value_normalized',
                hue='entity_mapping',
                palette=palette,
                alpha=0.7,
                ax=ax,
            )
            
        elif plot_type == "box":
            df['jahr'] = pd.to_numeric(df['jahr'], errors='coerce')
            df['jahr'] = df['jahr'].fillna(df['publication_year']).astype(int).astype(str)

            jahre = sorted(df['jahr'].unique(), key=lambda x: int(x) if x.isdigit() else x)
            df['jahr'] = pd.Categorical(df['jahr'], categories=jahre, ordered=True)

            sns.boxplot(
                data=df,
                x='jahr',
                y='value_normalized',
                hue='entity_mapping',
                palette=palette,
                ax=ax,
                width=0.4,
                showfliers=False,
            )

        elif plot_type == "line":
            df['jahr'] = pd.to_numeric(df['jahr'], errors='coerce')
            df['jahr'] = df['jahr'].fillna(df['publication_year']).astype(int)
                        
            agg_df = self.calculate_aggregates(df, central_tendency)

            sns.lineplot(
                data=agg_df,
                x='jahr',
                y='value_central',
                hue='entity_mapping',
                palette=palette,
                ax=ax,
            )

            sns.scatterplot(
                data=agg_df,
                x='jahr',
                y='value_central',
                hue='entity_mapping',
                size='n',
                sizes=(20, 200),  # Skaliere je nach Geschmack
                palette=palette,
                legend=False,
                ax=ax,
                marker='o',
            )

            for entity in agg_df['entity_mapping'].unique():
                entity_df = agg_df[agg_df['entity_mapping'] == entity].copy()

                if 'se' in entity_df.columns:
                    entity_df = entity_df[entity_df['se'].notna()]
                    ax.errorbar(
                        x=entity_df['jahr'],
                        y=entity_df['value_central'],
                        yerr=entity_df['se'],
                        fmt='none',           # Keine Linie, nur Fehlerbalken
                        ecolor='gray',        # Farbe der Balken
                        elinewidth=1,
                        capsize=3,            # Endkappen an Balken
                        alpha=0.6,
                        label=None
                    )


            n_vals = agg_df['n'].dropna().unique()
            n_vals = np.sort(n_vals.astype(int))

            handles_sample_size = self.create_size_legend_handles(ax, n_vals)

            handles, labels = ax.get_legend_handles_labels()
            color_handles_labels = [(h, l) for h, l in zip(handles, labels) if not l.startswith('n = ')]
            if color_handles_labels:
                color_handles, color_labels = zip(*color_handles_labels)
                color_legend = ax.legend(color_handles, color_labels, title=legend_title, bbox_to_anchor=(0, 1), loc='upper left')
                ax.add_artist(color_legend)

            # Sample Size Legende separat hinzufügen
            size_legend = ax.legend(handles=handles_sample_size, title='Sample Size', bbox_to_anchor=(0.257, 1), loc='upper left')
            ax.add_artist(size_legend)

        else:
            raise ValueError("plot_type must be either 'scatter' or 'box' or 'line'")
        
        ax.set_xlabel('Year')
        ax.set_ylabel(ylabel)
        ax.set_title(title, fontsize=14, pad=15)

        if plot_type != "line":
            ax.legend(title=legend_title, bbox_to_anchor=(1, 1), loc='upper right')

        ax.grid(linestyle='--', alpha=0.3)
        plt.tight_layout()
        return fig
        

    def plot_multiple_datasets_on_world(self, datasets: list, title: str, color_legend_title: str=None, figsize=(14, 7), default_point_size=100, palette=None, jitter_strength=0):
        """
        Plots multiple datasets with optional size and color encoding on a shared world map.
        Each dataset can use a distinct marker shape and include its own size legend.

        Args:
            datasets (list): List of dicts, each with keys:
                            - 'df': pandas DataFrame with 'latitude' and 'longitude'.
                            - 'value_column': (optional) Column to control marker sizes.
                            - 'color_column': (optional) Column to control marker colors.
                            - 'marker': (optional) Marker shape, e.g., 'o', 's', '^'.
                            - 'size_legend_title': (optional) Title for the size legend.
                            - 'legend_position': (optional) X-coordinate for legend placement.
            title (str): Title of the plot.
            color_legend_title (str): Title for the color legend.
            figsize (tuple): Size of the figure in inches.
            default_point_size (float): Marker size used if no value_column is specified.
            palette (dict or None): Optional custom color mapping. If None, seaborn palette is used.
            jitter_strength (float): Verschiebung der Punkte zur Vermeidung von Überlappung (in Grad).
        """
        
        sns.set_context("paper", font_scale=1.2)

        jittered_datasets = self.apply_jitter_to_datasets(datasets, jitter_strength)


        color_column = jittered_datasets[0].get('color_column', 'entity_mapping')  # Annahme: alle nutzen denselben key

        color_map, categories = self.get_color_map(jittered_datasets, color_column, palette)

        fig = plt.figure(figsize=figsize)
        ax = plt.axes(projection=ccrs.PlateCarree())
        ax.set_global()
        ax.coastlines()
        ax.add_feature(cfeature.BORDERS, edgecolor='black')
        ax.add_feature(cfeature.LAND, facecolor='lightgray')
        ax.gridlines(linewidth=0.5, color='gray', linestyle='--')

        for i, dataset in enumerate(jittered_datasets):
            self.plot_dataset_on_ax(ax, dataset, color_map, default_point_size, i)

        self.create_color_legend(ax, color_map, categories, color_legend_title)

        ax.set_title(title, fontsize=14, pad=15)
        return fig
    

    # ----------------------------------- Helper Functions -----------------------------------------------------------

    def apply_iqr_filter(self, df: pd.DataFrame, column: str = 'value_normalized') -> pd.DataFrame:
        """
        Removes outliers from a column using the IQR method.

        Args:
            df (pd.DataFrame): Input DataFrame.
            column (str): Column on which to apply the IQR filter.

        Returns:
            pd.DataFrame: Filtered DataFrame without outliers.
        """
        Q1 = df[column].quantile(0.25)
        Q3 = df[column].quantile(0.75)
        IQR = Q3 - Q1
        lower = Q1 - 1.5 * IQR
        upper = Q3 + 1.5 * IQR
        return df[(df[column] >= lower) & (df[column] <= upper)]
    

    def calculate_aggregates(self, df: pd.DataFrame, central_tendency: str):
        """
        Aggregate DataFrame by 'jahr' and 'entity_mapping' based on central tendency method.

        Args:
            df (pd.DataFrame): Input DataFrame with 'jahr' column.
            central_tendency (str): 'mean', 'median' or 'moving average'.
        """

        if central_tendency == "median":
            agg_df = df.groupby(['jahr', 'entity_mapping'])['value_normalized'].agg(['median', 'count']).reset_index()
            agg_df = agg_df.rename(columns={'median': 'value_central', 'count': 'n'})
            
        elif central_tendency == "mean":
            agg_df = df.groupby(['jahr', 'entity_mapping'])['value_normalized'].agg(['mean', 'std', 'count']).reset_index()
            agg_df = agg_df.rename(columns={'mean': 'value_central', 'std': 'std_dev', 'count': 'n'})
            agg_df['se'] = agg_df['std_dev'] / np.sqrt(agg_df['n'])
            agg_df['se'] = agg_df['se'].astype(float)

        elif central_tendency == "moving average":
            all_years = pd.DataFrame({'jahr': range(df['jahr'].min(), df['jahr'].max() + 1)})
            entities = df['entity_mapping'].unique()
            full_index = pd.MultiIndex.from_product([all_years['jahr'], entities], names=['jahr', 'entity_mapping']).to_frame(index=False)

            mean_values = df.groupby(['jahr', 'entity_mapping'])['value_normalized'].mean().reset_index()
            agg_df = full_index.merge(mean_values, on=['jahr', 'entity_mapping'], how='left').sort_values(['entity_mapping', 'jahr'])
            agg_df['value_central'] = agg_df.groupby('entity_mapping')['value_normalized'].transform(
                lambda x: x.rolling(window=3, center=True, min_periods=1).mean()
            )
            count_df = df.groupby(['jahr', 'entity_mapping']).size().reset_index(name='n')
            agg_df = agg_df.merge(count_df, on=['jahr', 'entity_mapping'], how='left')

            agg_df = agg_df[~agg_df['value_normalized'].isna()]

            agg_df['std_dev'] = agg_df.groupby('entity_mapping')['value_normalized'].transform(
                lambda x: x.rolling(window=3, center=True, min_periods=1).std()
            )
            agg_df['n_window'] = agg_df.groupby('entity_mapping')['value_normalized'].transform(
                lambda x: x.rolling(window=3, center=True, min_periods=1).count()
            )
            agg_df['se'] = agg_df['std_dev'] / np.sqrt(agg_df['n_window'])


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


    def create_color_legend(self, ax, color_map, categories, color_legend_title):
        """
        Adds a shared color legend to the plot for all category types.

        Args:
            ax (matplotlib.axes._subplots.AxesSubplot): The axis to add the legend to.
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
        color_legend = ax.legend(
            handles=handles_color,
            title=color_legend_title,
            loc='lower left',
            bbox_to_anchor=(-0.007, -0.013),
            frameon=True
        )
        ax.add_artist(color_legend)
        self.style_legend_frame(color_legend)

    
    def plot_dataset_on_ax(self, ax, dataset, color_map, default_point_size, i):
        """
        Plots one dataset on a given axis, with optional value-based sizing and color-based grouping.
        Adds an individual size legend if applicable.

        Args:
            ax (matplotlib.axes._subplots.AxesSubplot): The axis to plot on.
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
        legend_x = dataset.get('legend_position', 0.5 * i)

        if value_column:
            values = df[value_column]
            sizes = self.calculate_marker_sizes(values)
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
            legend_values = [values.min(), values.median(), values.max()]
            legend_sizes = self.calculate_marker_sizes(np.array(legend_values))
            handles = [
                plt.scatter([], [], s=s, color='steelblue', alpha=0.6, edgecolor='black', marker=marker, label=f"{v:.2f}")
                for s, v in zip(legend_sizes, legend_values)
            ]
            size_legend = ax.legend(
                handles=handles,
                title=size_legend_title,
                loc='lower left',
                bbox_to_anchor=(legend_x, -0.013),
                frameon=True
            )
            ax.add_artist(size_legend)
            self.style_legend_frame(size_legend)

    
    def calculate_marker_sizes(self, values, min_size=30, max_size=150):
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
