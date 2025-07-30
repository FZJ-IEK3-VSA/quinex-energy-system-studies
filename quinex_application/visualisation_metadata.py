import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

class VisualisationMetadata():
    def __init__(self, df_path):
        pd.set_option('display.max_colwidth', None)
        self.df_path = df_path
        sns.set(style="whitegrid")
        self.color = sns.color_palette("dark:steelblue", 6)[2]
        self.color2 = sns.color_palette("dark:cyan", 6)[2]


    def load_df(self, query, date):
        self.df = pd.read_parquet(self.df_path)
        self.df = self.df[self.df[f"{query}_{date}"] == True]


    def plot_bar(self, data, xlabel, ylabel, title, horizontal=True, figsize=(10,3)):
        fig, ax = plt.subplots(figsize=figsize)

        if horizontal:
            sns.barplot(x=data.values, y=data.index, ax=ax, color=self.color)
        else:
            sns.barplot(x=data.index, y=data.values, ax=ax, color=self.color)

        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        fig.tight_layout()
        return fig
    
    def plot_line(self, data, xlabel, ylabel, title, marker='o', figsize=(10,3)):
        fig, ax = plt.subplots(figsize=figsize)
        sns.lineplot(x=data.index, y=data.values, ax=ax, marker=marker, color=self.color)

        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        ax.grid(True)
        fig.tight_layout()
        return fig
    
    def plot_dual_axis(self, data_left, data_right, xlabel, ylabel_left, ylabel_right, title, figsize=(10,3)):
        fig, ax1 = plt.subplots(figsize=figsize)
        
        # Linke Achse
        sns.barplot(x=data_left.index, y=data_left.values, ax=ax1, color=self.color, alpha=0.6)
        ax1.set_xlabel(xlabel)
        ax1.set_ylabel(ylabel_left, color=self.color)
        ax1.tick_params(axis='y', labelcolor=self.color)

        # Rechte Achse
        ax2 = ax1.twinx()
        sns.lineplot(x=data_right.index, y=data_right.values, ax=ax2, color=self.color2, marker='o', linewidth=2)
        ax2.set_ylabel(ylabel_right, color=self.color2)
        ax2.tick_params(axis='y', labelcolor=self.color2)

        ax1.set_xticks(range(len(data_left.index)))
        ax1.set_xticklabels([int(year) for year in data_left.index], rotation=45)
        plt.title(title)
        fig.tight_layout()
        return fig

    def paper_per_year(self, start_year=2000, figsize=(10,3)):
        # Anzahl Paper pro Jahr
        papers_per_year = self.df['Year'].value_counts().sort_index()
        papers_per_year = papers_per_year[papers_per_year.index >= start_year]
        return self.plot_bar(papers_per_year, "Publication year", "Number of published papers", "Number of published papers per year", False, figsize)
    
    def citations_per_year(self, start_year=2000, figsize=(10,3)):
        # Durchschnittliche Zitierungen pro Jahr berechnen
        citations_per_year = self.df.groupby('Year')['Cited by'].mean()
        citations_per_year = citations_per_year[citations_per_year.index >= start_year]
        return self.plot_line(citations_per_year, "Publication year", "Average citations per paper", "Average citations per year", "o", figsize)
    
    def top_journals(self, number=10, by='count', figsize=(10,3)):
        if by == "count":
            # Häufigkeit der Journale zählen
            top_journals = self.df['Source title'].value_counts().head(number)
            xlabel = "Number of published papers"
        elif by == "avg_citations":
            # Erst Journale mit mehr als 100 auswählen
            counts = self.df['Source title'].value_counts()
            valid_journals = counts[counts > 100].index
            top_journals = self.df[self.df['Source title'].isin(valid_journals)].groupby('Source title')['Cited by'].mean().sort_values(ascending=False).head(number)
            xlabel = "Average citations per paper"
        else: 
            raise ValueError("Parameter 'by' muss 'count' oder 'avg_citations' sein.")
        return self.plot_bar(top_journals, xlabel, "Journal", f"Top {number} journals", True, figsize)
                
    def journal_trend(self, journal_name, figsize=(10,3)):
        df_journal = self.df[self.df['Source title'] == journal_name]

        if df_journal.empty:
            print(f"⚠️ Keine Daten gefunden für das Journal: '{journal_name}'")
            return

        publications_per_year = df_journal.groupby('Year').size()
        total_citations_per_year = df_journal.groupby('Year')['Cited by'].sum()

        return self.plot_dual_axis(
            data_left=publications_per_year,
            data_right=total_citations_per_year,
            xlabel="Publication year",
            ylabel_left="Number of published papers",
            ylabel_right="Total citations",
            title=f"Number of papers and total citations per year - Journal: {journal_name}",
            figsize=figsize
        )
    
    def open_access(self, figsize=(10, 3)):
        oa_counts = self.df['Open Access'].value_counts()
        return self.plot_bar(oa_counts, "Number of papers", "Open Access type", "Distribution of Open Access types", True, figsize)
    
    def citations_open_access(self, figsize=(10, 3)):
        # Gruppen mit mindestens z. B. 10 Einträgen
        avg_citations = self.df.groupby('Open Access')['Cited by'].mean().sort_values(ascending=False)
        return self.plot_bar(avg_citations, "Average citations per paper", "Open Access type", "Average citations by Open Access type", True, figsize)
    
    def top_cited_papers(self, number_paper, figsize=(10,3)):
        # Sortiere nach Zitierungen absteigend
        top_papers = self.df.sort_values(by='Cited by', ascending=False).head(number_paper)
        bar_data = pd.Series(top_papers['Cited by'].values, index=top_papers['DOI'])
        return self.plot_bar(bar_data, "Number of citations", "DOI", f"Top {number_paper} meistzitierte Paper", True, figsize)