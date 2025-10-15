import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import re

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
            metadata_df (pd.DataFrame):  DataFrame containing publication metadata with columns 'paper_id', 'publication_year', and 'countries'.
            top_n (int): Number of top countries to display.
            figsize (tuple, optional): Figure size for the plot (width, height).
        """
        
        # --- Percent of Papers with Missing Country ---
        missing_papers = metadata_df[metadata_df['countries'].str.len() == 0]['paper_id'].nunique()
        total_papers = metadata_df['paper_id'].nunique()
        missing_share = missing_papers / total_papers * 100
        print(f"Missing country info: {missing_papers} papers ({missing_share:.2f} %)")

        # --- Expand Lists in Country column ---
        df_clean = metadata_df[metadata_df['countries'].str.len() > 0].explode('countries')

        # --- Number of Papers per Year ---
        total_per_year = df_clean.groupby('publication_year')['paper_id'].nunique()

        # --- Numbers of Country per Year ---
        counts = df_clean.groupby(['publication_year', 'countries'])['paper_id'].nunique().reset_index(name='count')

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
    

    def journal_distribution(self, metadata_df: pd.DataFrame, group_by: str = "journal",  top_n: int = 10, use_percentage=True, show_other=True, figsize: tuple=(10,6)):
        """
        Plot the distribution of papers across sources (journals) or host organizations (publishers) as a horizontal bar chart.

        Args:
            metadata_df (pd.DataFrame): DataFrame containing publication metadata with 'paper_id', 'source', and 'host_organization'.
            group_by (str, optional): Whether to group by 'journal' (source) or 'publisher' (host_organization). Default is 'journal'.
            top_n (int, optional): Number of top sources/publishers to display individually; the rest are grouped into 'Other'.
            use_percentage(bool, optional): Wether to use the percentage of each journal or the total number of papers.
            show_other(bool, optional): Wether to show the percentage/total number of the other journals.
            figsize (tuple, optional): Figure size (width, height). Default is (10,6).
        """

        if group_by == "publisher":
            col = "host organization"
            ylabel = "Publisher"
        else:
            col = "source"
            ylabel = "Journal"

        # --- Count papers per source ---
        counts = metadata_df.groupby(col)['paper_id'].nunique().sort_values(ascending=False)
        total = counts.sum()


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
        title_group = "Publishers" if group_by == "publisher" else "Journals"
        #ax.set_title(f'Distribution of Papers per {title_group}')
        ax.grid(True, linestyle='--', alpha=0.7)
        fig.tight_layout()
        return fig, top_counts
    

    def topics_distribution(self, metadata_df: pd.DataFrame, group_by: str = "topics", top_n: int = 10, use_percentage=True, show_other=True, figsize=(10,6)):
        """
        Plot the distribution of papers across topics as a horizontal bar chart.

        Args:
            metadata_df (pd.DataFrame): DataFrame with columns 'paper_id' and 'topics' (list of topics).
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
        counts = df_clean.groupby(group_by)['paper_id'].nunique().sort_values(ascending=False)
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
            quinex_df (pd.DataFrame): DataFrame with columns 'paper_id' and the chosen column.
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

        unique_per_paper = df_filtered.drop_duplicates(subset=['paper_id','keyword_group'])
        counts = unique_per_paper['keyword_group'].value_counts()

        total_papers = df['paper_id'].nunique()
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