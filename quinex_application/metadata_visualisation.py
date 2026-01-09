import glob
import os
import re
import math
import pandas as pd
import plotly.graph_objects as go
import matplotlib.pyplot as plt
import seaborn as sns
import matplotlib as mpl
from matplotlib.cm import ScalarMappable
from matplotlib.ticker import PercentFormatter

class VisualisationMetadata():
    def __init__(self, df_path):
        """
        Initialize the visualization settings.
        """
        self.df_path = df_path

        pd.set_option('display.max_colwidth', None)
        sns.set_theme(style="ticks")
        sns.set_context("paper", font_scale=2)
    
    def load_df(self, query, date):
        self.df = pd.read_parquet(self.df_path)
        self.df = self.df[self.df[f"{query}_{date}"] == True]


    def countries_share_and_sjr(
        self,
        metadata_df: pd.DataFrame,
        top_n_line: int = 10,   # Anzahl Länder für Linienplot und farbig im Scatter
        top_n_scatter: int = 20, # Anzahl Länder für Scatter-Plot insgesamt
        figsize: tuple = (16, 6),
        font_size: int = 12,
        color_map: dict = None,
        legend_loc: str = 'upper right',
        legend_bbox: tuple = None
    ):
        # --- Font size ---
        mpl.rcParams.update({
            'axes.titlesize': font_size,
            'axes.labelsize': font_size,
            'xtick.labelsize': font_size,
            'ytick.labelsize': font_size,
            'legend.fontsize': font_size,
            'legend.title_fontsize': font_size
        })

        # --- Missing info ---
        missing_papers = metadata_df[metadata_df['countries'].str.len() == 0]['DOI'].nunique()
        total_papers = metadata_df['DOI'].nunique()
        print(f"Missing country info: {missing_papers} papers ({missing_papers/total_papers*100:.2f} %)")
        missing_sjr = metadata_df['SJR'].isna().sum()
        print(f"Missing SJR info: {missing_sjr} papers ({missing_sjr/total_papers*100:.2f} %)")

        # --- Clean Data ---
        df_clean = metadata_df[metadata_df['countries'].str.len() > 0].explode('countries')
        df_clean['SJR'] = pd.to_numeric(df_clean['SJR'].str.replace(',', '.'), errors='coerce')

        # --- Top Länder für Linienplot ---
        counts_total_line = df_clean.groupby('countries')['DOI'].nunique().reset_index(name='count')
        counts_total_line['share'] = counts_total_line['count'] / total_papers
        top_countries_line = counts_total_line.nlargest(top_n_line, 'share')['countries']

        # --- Top Länder für Scatter-Plot insgesamt ---
        counts_total_scatter = df_clean.groupby('countries')['DOI'].nunique().reset_index(name='count')
        counts_total_scatter['share'] = counts_total_scatter['count'] / total_papers
        top_countries_scatter = counts_total_scatter.nlargest(top_n_scatter, 'share')['countries']

        # --- Linienplot (über Jahre) ---
        total_per_year = df_clean.groupby('publication_year')['DOI'].nunique()
        counts_year = df_clean.groupby(['publication_year', 'countries'])['DOI'].nunique().reset_index(name='count')
        counts_year['share'] = counts_year.apply(lambda row: row['count']/total_per_year[row['publication_year']], axis=1)
        counts_top_year = counts_year[counts_year['countries'].isin(top_countries_line)]
        pivot_share_year = counts_top_year.pivot(index='publication_year', columns='countries', values='share').fillna(0)

        # --- Scatter-Plot Daten ---
        df_top_scatter = df_clean[df_clean['countries'].isin(top_countries_scatter)].copy()
        total_papers_with_country = df_clean['DOI'].nunique()
        scatter_data = df_top_scatter.groupby('countries').agg(
            share_of_paper=('DOI', lambda x: x.nunique() / total_papers_with_country),
            average_sjr=('SJR', 'mean')
        ).reset_index()


        # --- Plot ---
        fig, axes = plt.subplots(1, 2, figsize=figsize)

        # Linker Plot: Linienplot
        for country in pivot_share_year.columns:
            color = color_map.get(country) if color_map else None
            axes[0].plot(pivot_share_year.index, pivot_share_year[country]*100,
                        linestyle='-', marker='o', markersize=0, linewidth=2, label=country, color=color)
        axes[0].set_title("a", loc='left', fontweight='bold')
        axes[0].set_xlabel("Publication Year")
        axes[0].set_ylabel("Share of Papers [%]")
        axes[0].grid(True, linestyle='--', linewidth=0.7, alpha=0.9)

        # Rechter Plot: Scatter-Plot mit Top-Ländern farbig, andere grau
        for _, row in scatter_data.iterrows():
            if row['countries'] in top_countries_line.tolist():
                color = color_map.get(row['countries']) if color_map else None
            else:
                color = 'lightgray'
            axes[1].scatter(row['share_of_paper']*100, row['average_sjr'], s=100, label=row['countries'] if color != 'lightgray' else None, color=color)

        axes[1].set_title("b", loc='left', fontweight='bold')
        axes[1].set_xlabel("Share of Papers [%]")
        axes[1].set_ylabel("Average SJR")
        axes[1].grid(True, linestyle='--', linewidth=0.7, alpha=0.9)

        # Gemeinsame Legende rechts (nur Top-Länder)
        handles, labels = axes[1].get_legend_handles_labels()
        if legend_bbox is not None:
            fig.legend(handles, labels, loc='center', bbox_to_anchor=legend_bbox, frameon=True, title='Countries')
        else:
            fig.legend(handles, labels, loc=legend_loc, frameon=True, title='Countries')

        fig.tight_layout(rect=[0,0,0.85,1])  # Platz für Legend rechts
        return fig, pivot_share_year, scatter_data


    def keywords_distribution(self, quinex_df: pd.DataFrame, keywords: dict, column: str = "entity", figsize=(10,6)):
        """
        Plot the keywords of papers across topics as a horizontal bar chart.

        Args:
            quinex_df (pd.DataFrame): DataFrame with columns 'DOI' and the chosen column.
            keywords (dict): Dict containing the keywords for plotting. Example: entity_keywords = {"battery": ['battery', 'batteries', 'accu']}
            column (str, optional): Column to use for keyword matching ('entity' or 'property').
            figsize (tuple, optional): Figure size (width, height).
        """

        df = quinex_df
        all_keywords = [kw for kws in keywords.values() for kw in kws]

        mask = df[column].str.lower().apply(lambda x: any(kw.lower() in x for kw in all_keywords))
        df_filtered = df[mask].copy()

        def map_to_group(entity):
            for group, kws in keywords.items():
                for kw in kws:
                    if kw.lower() in entity.lower():
                        return group
            return None

        df_filtered['keyword_group'] = df_filtered[column].apply(map_to_group)

        unique_per_paper = df_filtered.drop_duplicates(subset=['DOI','keyword_group'])
        counts = unique_per_paper['keyword_group'].value_counts()

        total_papers = df['DOI'].nunique()
        percentages = (counts / total_papers) * 100

        percentages = percentages.sort_values(ascending=True)

        colors = ["steelblue"] * len(percentages)

        # --- Plot ---
        fig, ax = plt.subplots(figsize=figsize)
        ax.barh(percentages.index, percentages.values, color=colors)

        ax.set_xlabel('Percentage of Papers (%)')
        ylabel = 'Technology' if column == 'entity' else 'Property'
        ax.set_ylabel(ylabel)

        ax.grid(True, linestyle='--', alpha=0.7)
        fig.tight_layout()
        return fig, percentages


    def mention_trend_heatmap_multi_entities(
        self,
        dfs,
        entity_col: str = "entity_base_mapping",
        year_col: str = "publication_year",
        titles=None,
        top_n: int = 6,
        figsize: tuple = (16, 6),
        cmap: str = "viridis",
        font_size: int = 12
    ):
        # --- Normalize input ---
        if not isinstance(dfs, list):
            dfs = [dfs]

        n_plots = len(dfs)

        if titles is None:
            titles = [f"({chr(97+i)})" for i in range(n_plots)]

        if len(titles) != n_plots:
            raise ValueError("titles must have same length as dfs")

        # --- Font size ---
        mpl.rcParams.update({
            'axes.titlesize': font_size,
            'axes.labelsize': font_size,
            'xtick.labelsize': font_size,
            'ytick.labelsize': font_size
        })

        pivots = []
        vmax_global = 0

        # --- Prepare pivots ---
        for df in dfs:
            df = df.copy()
            df = df[df[year_col].notnull()]
            df[year_col] = df[year_col].astype(int)

            total_per_year = df.groupby(year_col)['DOI'].nunique()

            counts = (
                df.groupby([year_col, entity_col])['DOI']
                .nunique()
                .reset_index(name='count')
            )

            counts['share'] = counts.apply(
                lambda r: r['count'] / total_per_year[r[year_col]],
                axis=1
            )

            top_entities = (
                counts.groupby(entity_col)['share']
                .sum()
                .nlargest(top_n)
                .index
            )

            pivot = (
                counts[counts[entity_col].isin(top_entities)]
                .pivot(index=entity_col, columns=year_col, values='share')
                .fillna(0)
            )

            pivot = pivot.loc[pivot.mean(axis=1).sort_values(ascending=False).index]

            pivots.append(pivot)
            vmax_global = max(vmax_global, pivot.values.max())

        # --- Grid-Layout: max 2 Spalten ---
        n_cols = 2 if n_plots > 1 else 1
        n_rows = math.ceil(n_plots / n_cols)

        fig, axes = plt.subplots(
            n_rows, n_cols,
            figsize=(figsize[0], figsize[1]*n_rows),
            gridspec_kw={'wspace': 0.4, 'hspace': 0.35}
        )

        # axes als flache Liste behandeln
        if n_plots == 1:
            axes = [axes]
        else:
            axes = axes.flatten()

        for ax, pivot, title in zip(axes, pivots, titles):
            sns.heatmap(
                pivot,
                ax=ax,
                cmap=cmap,
                vmin=0,
                vmax=vmax_global,
                cbar=False,
                linewidths=0.5
            )

            ax.set_title(title, loc='left', fontweight='bold')
            ax.set_xlabel("Publication Year")
            ax.set_ylabel("Entity")

            # X-Ticks: jede zweite
            xticks = ax.get_xticks()
            labels = [l.get_text() for l in ax.get_xticklabels()]
            ax.set_xticks(xticks[::4])
            ax.set_xticklabels(labels[::4], rotation=0)

        # --- Leere Achsen ausblenden, falls n_plots ungerade ---
        for ax in axes[n_plots:]:
            ax.axis('off')

        # --- Shared Colorbar ---
        sm = ScalarMappable(
            cmap=cmap,
            norm=plt.Normalize(vmin=0, vmax=vmax_global)
        )
        sm.set_array([])

        cbar = fig.colorbar(
            sm,
            ax=axes[:n_plots],
            fraction=0.05,
            pad=0.02,
            shrink=0.5
        )
        cbar.set_label("Share of Papers [%]")
        cbar.ax.yaxis.set_major_formatter(PercentFormatter(xmax=1))

        fig.tight_layout()
        return fig, pivots

    
    def mention_trend_heatmap(
        self,
        quinex_df: pd.DataFrame,
        entity_col: str = "entity_base_mapping",
        property_col: str = "property_base_mapping",
        year_col: str = "publication_year",
        top_n: int = 6,
        figsize: tuple = (16, 6),
        cmap: str = "viridis",
        font_size: int = 12
    ):
        """
        Plot temporal share of mentions as heatmaps for entities and properties with:
        - shared color scale
        - Y-axis sorted by mean share
        - X-axis ticks every 2 years
        - one shared colorbar

        Args:
            quinex_df (pd.DataFrame): DataFrame with entity/property mentions and publication years.
            entity_col (str): Column name for entities.
            property_col (str): Column name for properties.
            year_col (str): Column name for publication year.
            top_n (int): Number of top entities/properties to include.
            figsize (tuple): Figure size.
            cmap (str): Colormap for heatmaps.
            font_size (int): Font size for all plot elements.
        """

        # --- Font size ---
        mpl.rcParams.update({
            'axes.titlesize': font_size,
            'axes.labelsize': font_size,
            'xtick.labelsize': font_size,
            'ytick.labelsize': font_size
        })

        df = quinex_df.copy()
        df = df[df[year_col].notnull()]
        df[year_col] = df[year_col].astype(int)

        total_per_year = df.groupby(year_col)['DOI'].nunique()

        # --- Entities ---
        counts_entity = df.groupby([year_col, entity_col])['DOI'].nunique().reset_index(name='count')
        counts_entity['share'] = counts_entity.apply(
            lambda row: row['count'] / total_per_year[row[year_col]], axis=1)
        top_entities = counts_entity.groupby(entity_col)['share'].sum().nlargest(top_n).index
        counts_entity = counts_entity[counts_entity[entity_col].isin(top_entities)]
        pivot_entity = counts_entity.pivot(index=entity_col, columns=year_col, values='share').fillna(0)
        pivot_entity = pivot_entity.loc[pivot_entity.mean(axis=1).sort_values(ascending=False).index]

        # --- Properties ---
        counts_property = df.groupby([year_col, property_col])['DOI'].nunique().reset_index(name='count')
        counts_property['share'] = counts_property.apply(
            lambda row: row['count'] / total_per_year[row[year_col]], axis=1)
        top_properties = counts_property.groupby(property_col)['share'].sum().nlargest(top_n).index
        counts_property = counts_property[counts_property[property_col].isin(top_properties)]
        pivot_property = counts_property.pivot(index=property_col, columns=year_col, values='share').fillna(0)
        pivot_property = pivot_property.loc[pivot_property.mean(axis=1).sort_values(ascending=False).index]

        # --- Gemeinsame Farbskala ---
        vmax = max(pivot_entity.values.max(), pivot_property.values.max())

        # --- Plot Heatmaps ---
        fig, axes = plt.subplots(1, 2, figsize=figsize, gridspec_kw={'width_ratios':[1,1], 'wspace':0.35})

        # Entities Heatmap
        sns.heatmap(pivot_entity, ax=axes[0], cmap=cmap, vmin=0, vmax=vmax, cbar=False, linewidths=0.5)
        axes[0].set_title("c", loc='left', fontweight='bold')
        axes[0].set_xlabel("Publication Year")
        axes[0].set_ylabel("Entity")

        # Properties Heatmap
        sns.heatmap(pivot_property, ax=axes[1], cmap=cmap, vmin=0, vmax=vmax, cbar=False, linewidths=0.5)
        axes[1].set_title("d", loc='left', fontweight='bold')
        axes[1].set_xlabel("Publication Year")
        axes[1].set_ylabel("Property")

        # --- Gemeinsame Colorbar rechts ---
        sm = ScalarMappable(cmap=cmap, norm=plt.Normalize(vmin=0, vmax=vmax))
        sm.set_array([])
        cbar = fig.colorbar(sm, ax=axes, fraction=0.05, pad=0.02)
        cbar.set_label('Share of Papers [%]')
        cbar.ax.yaxis.set_major_formatter(PercentFormatter(xmax=1))

        # --- X-Ticks: nur jede zweite sichtbar, horizontal ---
        for ax in axes:
            xticks = ax.get_xticks()
            labels = [item.get_text() for item in ax.get_xticklabels()]
            new_ticks = []
            new_labels = []
            for i, label in enumerate(labels):
                if i % 4 == 0:
                    new_ticks.append(xticks[i])
                    new_labels.append(label)
            ax.set_xticks(new_ticks)
            ax.set_xticklabels(new_labels, rotation=0)


        fig.tight_layout()
        return fig, pivot_entity, pivot_property




    def entity_property_sankey(self, df: pd.DataFrame, 
                               entity_keywords: dict, 
                               property_keywords: dict,
                               entity_col: str = "entity",
                               property_col: str = "property",
                               year_col: str = "publication_year",
                               top_n_entities: int = 6,
                               top_n_properties: int = 6,
                               figsize: tuple = (12,6)):
        """
        Create a Sankey diagram showing relationships between Entities and Properties.

        Args:
            df (pd.DataFrame): DataFrame with columns for entities, properties, and publication year.
            entity_keywords (dict): Mapping entity group -> list of keywords.
            property_keywords (dict): Mapping property group -> list of keywords.
            entity_col (str): Column containing entity text.
            property_col (str): Column containing property text.
            year_col (str): Column with publication year (used to filter valid entries).
            top_n_entities (int): Number of top entities to show.
            top_n_properties (int): Number of top properties to show.
            figsize (tuple): Figure size for static plots (Plotly handles interactive sizing separately).
        """

        df = df[df[year_col].notnull()]
        df[year_col] = df[year_col].astype(int)

        # --- Mapping Entities ---
        def map_to_group(text, keywords_dict):
            for group, kws in keywords_dict.items():
                for kw in kws:
                    if kw.lower() in str(text).lower():
                        return group
            return None

        df['entity_group'] = df[entity_col].apply(lambda x: map_to_group(x, entity_keywords))
        df['property_group'] = df[property_col].apply(lambda x: map_to_group(x, property_keywords))

        # Nur Papers behalten, die eine Entity **und** Property haben
        df_filtered = df[df['entity_group'].notnull() & df['property_group'].notnull()]

        # --- Top Entities / Properties ---
        top_entities = df_filtered['entity_group'].value_counts().head(top_n_entities).index
        top_properties = df_filtered['property_group'].value_counts().head(top_n_properties).index

        df_filtered = df_filtered[df_filtered['entity_group'].isin(top_entities) & df_filtered['property_group'].isin(top_properties)]

        # --- Links zählen ---
        link_counts = df_filtered.groupby(['entity_group', 'property_group'])['DOI'].nunique().reset_index(name='count')

        # --- Nodes ---
        all_nodes = list(top_entities) + list(top_properties)
        node_indices = {name: i for i, name in enumerate(all_nodes)}

        # --- Links für Sankey ---
        sources = link_counts['entity_group'].map(node_indices)
        targets = link_counts['property_group'].map(node_indices)
        values = link_counts['count']

        # --- Sankey Plot ---
        fig = go.Figure(data=[go.Sankey(
            node=dict(
                pad=15,
                thickness=20,
                line=dict(color="black", width=0.5),
                label=all_nodes,
                color="steelblue"
            ),
            link=dict(
                source=sources,
                target=targets,
                value=values,
                color="lightblue"
            )
        )])

        fig.update_layout(title_text="Entity-Property Relationships", font_size=12)
        fig.show()

        return fig, link_counts
    
    def add_sjr_to_metadata(
        self,
        metadata_df,
        sjr_folder,
        source_col='Source',
        year_col='publication_year',
        source_rename_dict=None
    ):
        """
        Fügt dem metadata_df die SJR-Werte aus den SCImago CSVs hinzu.
        Auch ein Abgleich bei Unterschieden nur durch ',' oder ':' wird durchgeführt.

        Args:
            metadata_df (pd.DataFrame): DataFrame mit Papers, muss Spalten source_col und year_col enthalten
            sjr_folder (str): Ordner, in dem die SCImago CSVs liegen (2010 bis 2024)
            source_col (str, optional): Spalte in metadata_df mit Journalnamen. Default 'Source'
            year_col (str, optional): Spalte in metadata_df mit Jahr. Default 'publication_year'
            source_rename_dict (dict, optional): Mapping für spezielle Journalnamen

        Returns:
            pd.DataFrame: metadata_df mit neuer Spalte 'SJR'
        """

        # ------------------------------------------------------------------
        # 1. Alle SCImago CSVs einlesen
        # ------------------------------------------------------------------
        all_files = glob.glob(os.path.join(sjr_folder, "*.csv"))
        sjr_list = []

        for f in all_files:
            df = pd.read_csv(f, sep=';', low_memory=False)

            # Jahr aus Dateiname
            year_match = re.search(r'\b(\d{4})\b', os.path.basename(f))
            if not year_match:
                raise ValueError(f"Jahr konnte nicht aus Dateiname {f} extrahiert werden")

            year = int(year_match.group(1))
            df['Year'] = year

            # Journalnamen normalisieren
            df['Title'] = df['Title'].str.upper().str.strip()

            sjr_list.append(df[['Title', 'Year', 'SJR']])

        sjr_all = pd.concat(sjr_list, ignore_index=True)

        # ------------------------------------------------------------------
        # 2. metadata_df vorbereiten
        # ------------------------------------------------------------------
        metadata_df_clean = metadata_df.copy()

        metadata_df_clean[source_col] = (
            metadata_df_clean[source_col]
            .astype(str)
            .str.upper()
            .str.replace("&", "AND", regex=False)
            .str.strip()
        )

        # 🔧 OPTIONAL: Source-Umbenennung
        if source_rename_dict is not None:
            source_rename_dict = {k.upper(): v.upper() for k, v in source_rename_dict.items()}
            metadata_df_clean[source_col] = metadata_df_clean[source_col].replace(source_rename_dict)

        # Falls SJR schon existiert → entfernen
        if 'SJR' in metadata_df_clean.columns:
            metadata_df_clean = metadata_df_clean.drop(columns=['SJR'])

        # ------------------------------------------------------------------
        # 3. Merge (normal)
        # ------------------------------------------------------------------
        merged = metadata_df_clean.merge(
            sjr_all,
            left_on=[source_col, year_col],
            right_on=['Title', 'Year'],
            how='left'
        )

        # ------------------------------------------------------------------
        # 4. Nachträglicher Komma/Doppelpunkt-Abgleich für fehlende SJR
        # ------------------------------------------------------------------
        mask_missing = merged['SJR'].isna()
        for idx in merged[mask_missing].index:
            src = merged.at[idx, source_col]
            year = merged.at[idx, year_col]
            candidates = sjr_all[sjr_all['Year'] == year]['Title'].tolist()
            for c in candidates:
                src_clean = src.replace(',', '').replace(':', '').strip()
                c_clean = c.replace(',', '').replace(':', '').strip()
                if src_clean == c_clean:
                    merged.at[idx, 'SJR'] = sjr_all.loc[
                        (sjr_all['Title'] == c) & (sjr_all['Year'] == year),
                        'SJR'
                    ].values[0]
                    break  # Match gefunden, weiter mit nächstem

        # ------------------------------------------------------------------
        # 5. Aufräumen
        # ------------------------------------------------------------------
        merged = merged.drop(columns=['Title', 'Year'])

        return merged


