import pandas as pd
import plotly.graph_objects as go
import matplotlib.pyplot as plt
import seaborn as sns

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


    def countries_share_year(self, metadata_df: pd.DataFrame, top_n: int, figsize: tuple = (12, 6), legend_position: tuple = (0.91, 1)):
        """
        Plot the share of publications per year for the top N countries.

        Args:
            metadata_df (pd.DataFrame):  DataFrame containing publication metadata with columns 'DOI', 'publication_year', and 'countries'.
            top_n (int): Number of top countries to display.
            figsize (tuple, optional): Figure size for the plot (width, height).
        """
        
        # --- Percent of Papers with Missing Country ---
        missing_papers = metadata_df[metadata_df['countries'].str.len() == 0]['DOI'].nunique()
        total_papers = metadata_df['DOI'].nunique()
        missing_share = missing_papers / total_papers * 100
        print(f"Missing country info: {missing_papers} papers ({missing_share:.2f} %)")

        # --- Expand Lists in Country column ---
        df_clean = metadata_df[metadata_df['countries'].str.len() > 0].explode('countries')

        # --- Number of Papers per Year ---
        total_per_year = df_clean.groupby('publication_year')['DOI'].nunique()

        # --- Numbers of Country per Year ---
        counts = df_clean.groupby(['publication_year', 'countries'])['DOI'].nunique().reset_index(name='count')

        # --- Percentage per Year ---
        counts['share'] = counts.apply(lambda row: row['count'] / total_per_year[row['publication_year']], axis=1)

        # --- Top-6 Countries over all Years ---
        top = counts.groupby('countries')['share'].sum().nlargest(top_n).index
        counts_top = counts[counts['countries'].isin(top)]

        # --- Pivot ---
        pivot = counts_top.pivot(index='publication_year', columns='countries', values='share').fillna(0)

        # --- Seaborn Style and Color Palette ---
        colors = sns.color_palette("tab10", n_colors=len(pivot.columns))

        # --- Plot ---
        fig, ax = plt.subplots(figsize=figsize)
        for country, color in zip(pivot.columns, colors):
            ax.plot(pivot.index, pivot[country]*100, marker='o', markersize=0, linewidth=2, label=country, color=color)

        #ax.set_title(f'Share of Publications per Year – Top {top_n} Countries')
        ax.set_xlabel('Publication Year')
        ax.set_ylabel('Share of Papers (%)')
        ax.legend(title='Countries', bbox_to_anchor=legend_position, loc='upper left')
        ax.grid(True, linestyle='--', linewidth=0.7, alpha=1)  # Dashed grid lines
        fig.tight_layout()
        
        return fig, pivot
    

    def journal_distribution(self, metadata_df: pd.DataFrame, col: str = "source", ylabel: str = "Journal",  top_n: int = 10, use_percentage=True, show_other=True, figsize: tuple=(10,6)):
        """
        Plot the distribution of papers across sources (journals) or host organizations (publishers) as a horizontal bar chart.

        Args:
            metadata_df (pd.DataFrame): DataFrame containing publication metadata with 'DOI', 'source', and 'host_organization'.
            col (str, optional): The column which to use for the graphic
            ylabel (str, optional): The label of the y-axes
            top_n (int, optional): Number of top sources/publishers to display individually; the rest are grouped into 'Other'.
            use_percentage(bool, optional): Wether to use the percentage of each journal or the total number of papers.
            show_other(bool, optional): Wether to show the percentage/total number of the other journals.
            figsize (tuple, optional): Figure size (width, height). Default is (10,6).
        """

        print(len(metadata_df))
        # --- Count papers per source ---
        counts = metadata_df.groupby(col)['DOI'].nunique().sort_values(ascending=False)
        total = counts.sum()
        print(total)
        print(len(metadata_df))

        print(len(counts))
        # --- Leere oder fehlende Einträge entfernen (nicht anzeigen) ---
        counts = counts[counts.index.notna()]           # entferne NaN
        print(len(counts))
        counts = counts[counts.index.str.strip() != ""] # entferne leere Strings
        counts = counts.sort_values(ascending=False)

        # --- Top N sources and group rest as 'Other' ---
        top_counts = counts.head(top_n)
        if show_other and len(counts) > top_n:
            top_counts["Other"] = counts[top_n:].sum()
        
        if use_percentage:
            top_counts = top_counts / total * 100
            xlabel = "Percentage of Papers (%)"
        else:
            xlabel = "Number of Papers"

        colors = ["steelblue"] * len(top_counts)
        if "Other" in top_counts.index:
            colors[0] = "lightgrey"

        # --- Plot ---
        fig, ax = plt.subplots(figsize=figsize)
        ax.barh(top_counts.index[::-1], top_counts.values[::-1], color=colors)

        # --- Achsen & Titel ---
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        ax.grid(True, linestyle='--', alpha=0.7)
        fig.tight_layout()
        return fig, top_counts
    

    def topics_distribution(self, metadata_df: pd.DataFrame, group_by: str = "topics", top_n: int = 10, use_percentage=True, show_other=True, figsize=(10,6)):
        """
        Plot the distribution of papers across topics as a horizontal bar chart.

        Args:
            metadata_df (pd.DataFrame): DataFrame with columns 'DOI' and 'topics' (list of topics).
            group_by (str, optional): Whether to group by 'topics' or 'concepts'. Default is 'topics'.
            top_n (int, optional): Number of top topics to display individually; the rest are grouped into 'Other'.
            use_percentage (bool, optional): Show percentages instead of absolute counts.
            show_other (bool, optional): Whether to group remaining topics into 'Other'.
            figsize (tuple, optional): Figure size (width, height).
        """

        if group_by not in ["topics", "concepts"]:
            raise ValueError("group_by must be either 'topics' or 'concepts'")
        
        # --- Expand lists in topics column ---
        df_clean = metadata_df[metadata_df[group_by].str.len() > 0].explode(group_by)

        # --- Count papers per topic ---
        counts = df_clean.groupby(group_by)['DOI'].nunique().sort_values(ascending=False)
        total = counts.sum()

        # --- Top N + optional Other ---
        top_counts = counts.head(top_n)
        if show_other and len(counts) > top_n:
            top_counts["Other"] = counts[top_n:].sum()

        # --- Prozent oder absolute Werte ---
        if use_percentage:
            top_counts = top_counts / total * 100
            xlabel = "Percentage of Papers (%)"
        else:
            xlabel = "Number of Papers"

        # --- Farben: einheitlich Steelblue, Other hellgrau ---
        colors = ["steelblue"] * len(top_counts)
        if "Other" in top_counts.index:
            colors[0] = "lightgrey"

        # --- Plot ---
        fig, ax = plt.subplots(figsize=figsize)
        ax.barh(top_counts.index[::-1], top_counts.values[::-1], color=colors)

        ax.set_xlabel(xlabel)
        ax.set_ylabel(group_by.capitalize())
        #ax.set_title(f"Distribution of Papers per {group_by.capitalize()}")

        ax.grid(True, linestyle='--', alpha=0.7)
        fig.tight_layout()
        return fig
    

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
    

    
    def mention_trend_over_time(self, quinex_df: pd.DataFrame, keywords: dict, mention_col: str = "entity_base_mapping",
                               year_col: str = "publication_year", top_n: int = 6,
                               figsize: tuple = (12, 6), legend_position: tuple = (0.91, 1)):
        """
        Plot the temporal share of mentions per year for selected technologies (based on keywords mapping).

        Args:
            quinex_df (pd.DataFrame): DataFrame containing extracted entities and publication years.
            keywords (dict): Dict containing technology keyword groups, e.g. {"battery": ["battery", "batteries", "accu"]}.
            mention_col (str, optional): Column name containing entity text. Default is 'entity_base_mapping'.
            year_col (str, optional): Column name containing publication year. Default is 'publication_year'.
            top_n (int, optional): Number of top technologies to show. Default is 6.
            figsize (tuple, optional): Figure size (width, height). Default is (12,6).
            legend_position (tuple, optional): Position of legend anchor. Default is (0.91, 1).
        """

        df = quinex_df.copy()
        df = df[df[year_col].notnull()]
        df[year_col] = df[year_col].astype(int)

        # --- Schritt 1: Keywords-Filter ---
        all_keywords = [kw for kws in keywords.values() for kw in kws]
        mask = df[mention_col].astype(str).str.lower().apply(lambda x: any(kw.lower() in x for kw in all_keywords))
        df_filtered = df[mask].copy()

        # --- Schritt 2: Zuordnen zur Gruppe (z. B. battery, hydrogen, pv, ...) ---
        def map_to_group(entity):
            for group, kws in keywords.items():
                for kw in kws:
                    if kw.lower() in entity.lower():
                        return group
            return None

        df_filtered["mention_group"] = df_filtered[mention_col].apply(map_to_group)

        # --- Number of Papers er Year ---
        total_per_year = df.groupby('publication_year')['DOI'].nunique()

        # --- Numbers of Mentions per Year ---
        counts = df_filtered.groupby([year_col, 'mention_group'])['DOI'].nunique().reset_index(name='count')

        # --- Percentage per Year ---
        counts['share'] = counts.apply(lambda row: row['count'] / total_per_year[row['publication_year']], axis=1)

        # --- Top-6 Mentions over all Years ---
        top = counts.groupby('mention_group')['share'].sum().nlargest(top_n).index
        counts_top = counts[counts['mention_group'].isin(top)]


        # --- Pivot für Plot ---
        pivot = counts_top.pivot(index=year_col, columns="mention_group", values="share").fillna(0)

        # --- Farben & Stil ---
        colors = sns.color_palette("tab10", n_colors=len(pivot.columns))
        fig, ax = plt.subplots(figsize=figsize)

        # --- Linien plotten ---
        for entity, color in zip(pivot.columns, colors):
            ax.plot(pivot.index, pivot[entity]*100, marker='o', markersize=0, linewidth=2, label=entity, color=color)

        # --- Achsen & Formatierung ---
        ax.set_xlabel("Publication Year")
        ax.set_ylabel("Share of Papers (%)")
        #ax.set_title(f"Temporal Share of Top {top_n} Technologies")
        legend_title = 'Technology' if mention_col == 'entity' else 'Property'
        ax.legend(title=legend_title, bbox_to_anchor=legend_position, loc="upper left")
        ax.grid(True, linestyle='--', linewidth=0.7, alpha=0.9)
        fig.tight_layout()

        return fig, pivot


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

