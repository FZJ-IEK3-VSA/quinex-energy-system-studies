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
    
    # ISO3 to ISO2 country code mapping
    ISO3_TO_ISO2 = {
        "ABW": "AW", "AFG": "AF", "AGO": "AO", "ALB": "AL", "AND": "AD", "ARE": "AE",
        "ARG": "AR", "ARM": "AM", "AUS": "AU", "AUT": "AT", "AZE": "AZ", "BDI": "BI",
        "BEL": "BE", "BEN": "BJ", "BFA": "BF", "BGD": "BD", "BGR": "BG", "BHR": "BH",
        "BHS": "BS", "BIH": "BA", "BLR": "BY", "BLZ": "BZ", "BOL": "BO", "BRA": "BR",
        "BRB": "BB", "BRN": "BN", "BTN": "BT", "BWA": "BW", "CAF": "CF", "CAN": "CA",
        "CHE": "CH", "CHL": "CL", "CHN": "CN", "CIV": "CI", "CMR": "CM", "COD": "CD",
        "COG": "CG", "COL": "CO", "COM": "KM", "CPV": "CV", "CRI": "CR", "CUB": "CU",
        "CYP": "CY", "CZE": "CZ", "DEU": "DE", "DJI": "DJ", "DNK": "DK", "DOM": "DO",
        "DZA": "DZ", "ECU": "EC", "EGY": "EG", "ERI": "ER", "ESP": "ES", "EST": "EE",
        "ETH": "ET", "FIN": "FI", "FJI": "FJ", "FRA": "FR", "FRO": "FO", "GAB": "GA",
        "GBR": "GB", "GEO": "GE", "GHA": "GH", "GIN": "GN", "GMB": "GM", "GNB": "GW",
        "GNQ": "GQ", "GRC": "GR", "GRL": "GL", "GTM": "GT", "GUY": "GY", "HKG": "HK",
        "HND": "HN", "HRV": "HR", "HTI": "HT", "HUN": "HU", "IDN": "ID", "IND": "IN",
        "IRL": "IE", "IRN": "IR", "IRQ": "IQ", "ISL": "IS", "ISR": "IL", "ITA": "IT",
        "JAM": "JM", "JOR": "JO", "JPN": "JP", "KAZ": "KZ", "KEN": "KE", "KGZ": "KG",
        "KHM": "KH", "KOR": "KR", "KWT": "KW", "LAO": "LA", "LBN": "LB", "LBR": "LR",
        "LBY": "LY", "LKA": "LK", "LSO": "LS", "LTU": "LT", "LUX": "LU", "LVA": "LV",
        "MAC": "MO", "MAR": "MA", "MDA": "MD", "MDG": "MG", "MDV": "MV", "MEX": "MX",
        "MKD": "MK", "MLI": "ML", "MLT": "MT", "MMR": "MM", "MNE": "ME", "MNG": "MN",
        "MOZ": "MZ", "MRT": "MR", "MUS": "MU", "MWI": "MW", "MYS": "MY", "NAM": "NA",
        "NER": "NE", "NGA": "NG", "NIC": "NI", "NLD": "NL", "NOR": "NO", "NPL": "NP",
        "NZL": "NZ", "OMN": "OM", "PAK": "PK", "PAN": "PA", "PER": "PE", "PHL": "PH",
        "PNG": "PG", "POL": "PL", "PRI": "PR", "PRK": "KP", "PRT": "PT", "PRY": "PY",
        "PSE": "PS", "QAT": "QA", "ROU": "RO", "RUS": "RU", "RWA": "RW", "SAU": "SA",
        "SDN": "SD", "SEN": "SN", "SGP": "SG", "SLB": "SB", "SLE": "SL", "SLV": "SV",
        "SOM": "SO", "SRB": "RS", "SSD": "SS", "SUR": "SR", "SVK": "SK", "SVN": "SI",
        "SWE": "SE", "SWZ": "SZ", "SYR": "SY", "TCD": "TD", "TGO": "TG", "THA": "TH",
        "TJK": "TJ", "TKM": "TM", "TLS": "TL", "TTO": "TT", "TUN": "TN", "TUR": "TR",
        "TWN": "TW", "TZA": "TZ", "UGA": "UG", "UKR": "UA", "URY": "UY", "USA": "US",
        "UZB": "UZ", "VEN": "VE", "VNM": "VN", "YEM": "YE", "ZAF": "ZA", "ZMB": "ZM",
        "ZWE": "ZW", "XKX": "XK"
    }
    
    def __init__(self, df_path):
        """
        Initialize the visualization settings.
        """
        self.df_path = df_path
        self._population_cache = None  # Cache for population data
        self._gdp_cache = None  # Cache for GDP data

        pd.set_option('display.max_colwidth', None)
        sns.set_theme(style="ticks")
        sns.set_context("paper", font_scale=2)

        mpl.rcParams['pdf.fonttype'] = 42
        mpl.rcParams['ps.fonttype'] = 42
    
    def load_df(self, query, date):
        self.df = pd.read_parquet(self.df_path)
        self.df = self.df[self.df[f"{query}_{date}"] == True]

    def _load_population_data(self, population_excel_path: str) -> pd.DataFrame:
        """
        Load UN World Population Prospects data from local Excel file.
        
        Args:
            population_excel_path: Path to the WPP2024 Excel file
            
        Returns:
            DataFrame with columns: ['countries', 'year', 'population', 'world_population', 'population_share']
            
        Data source: UN World Population Prospects 2024 Revision
        """
        if self._population_cache is not None:
            return self._population_cache
        
        print(f"Loading UN World Population Prospects data from {population_excel_path}...")
        
        # Read both sheets (Estimates until 2023, Medium variant from 2024)
        df_estimates = pd.read_excel(
            population_excel_path, 
            sheet_name='Estimates', 
            header=16
        )
        df_medium = pd.read_excel(
            population_excel_path, 
            sheet_name='Medium variant', 
            header=16
        )
        
        # Combine both sheets
        df_pop = pd.concat([df_estimates, df_medium], ignore_index=True)
        
        # Select relevant columns
        df_pop = df_pop[[
            'ISO2 Alpha-code', 
            'Year', 
            'Total Population, as of 1 January (thousands)'
        ]].copy()
        
        # Rename columns
        df_pop.columns = ['countries', 'year', 'population']
        
        # Filter out rows without ISO2 code (regions, aggregates)
        df_pop = df_pop[df_pop['countries'].notna()].copy()
        
        # Population is in thousands, convert to actual population
        df_pop['population'] = df_pop['population'] * 1000
        
        # Calculate world population per year (sum of all countries)
        world_pop = df_pop.groupby('year')['population'].sum().reset_index()
        world_pop.columns = ['year', 'world_population']
        
        # Merge world population
        df_pop = df_pop.merge(world_pop, on='year', how='left')
        
        # Calculate population share
        df_pop['population_share'] = df_pop['population'] / df_pop['world_population']
        
        # Ensure year is integer
        df_pop['year'] = df_pop['year'].astype(int)
        
        self._population_cache = df_pop
        print(f"Loaded population data for {df_pop['countries'].nunique()} countries, years {df_pop['year'].min()}-{df_pop['year'].max()}")
        
        return df_pop

    def _load_gdp_data(self, gdp_excel_path: str) -> pd.DataFrame:
        """
        Load World Bank GDP data from local Excel file.
        
        Args:
            gdp_excel_path: Path to the World Bank GDP Excel file (.xls)
            
        Returns:
            DataFrame with columns: ['countries', 'year', 'gdp', 'world_gdp', 'gdp_share']
            
        Data source: World Bank - World Development Indicators
        """
        if self._gdp_cache is not None:
            return self._gdp_cache
        
        print(f"Loading World Bank GDP data from {gdp_excel_path}...")
        
        # Read Excel file (header at row 3)
        df_gdp = pd.read_excel(gdp_excel_path, header=3)
        
        # Get year columns - they are loaded as strings, so we need to check string representation
        # or try to convert them. Year columns should be numeric values >= 1960
        year_columns = []
        for col in df_gdp.columns:
            # Skip the non-year columns
            if col in ['Country Name', 'Country Code', 'Indicator Name', 'Indicator Code']:
                continue
            try:
                year = int(float(col))
                if year >= 1960:
                    year_columns.append(col)
            except (ValueError, TypeError):
                continue
        
        # Melt to long format
        df_gdp = df_gdp.melt(
            id_vars=['Country Name', 'Country Code'],
            value_vars=year_columns,
            var_name='year',
            value_name='gdp'
        )
        
        # Map ISO3 to ISO2 country codes
        df_gdp['countries'] = df_gdp['Country Code'].map(self.ISO3_TO_ISO2)
        
        # Filter out non-country entries (regions, aggregates without ISO2 mapping)
        df_gdp = df_gdp[df_gdp['countries'].notna()].copy()
        
        # Remove rows with missing GDP
        df_gdp = df_gdp[df_gdp['gdp'].notna()].copy()
        
        # Convert year to int
        df_gdp['year'] = pd.to_numeric(df_gdp['year'], errors='coerce').astype(int)
        
        # Calculate world GDP per year (sum of all countries)
        world_gdp = df_gdp.groupby('year')['gdp'].sum().reset_index()
        world_gdp.columns = ['year', 'world_gdp']
        
        # Merge world GDP
        df_gdp = df_gdp.merge(world_gdp, on='year', how='left')
        
        # Calculate GDP share
        df_gdp['gdp_share'] = df_gdp['gdp'] / df_gdp['world_gdp']
        
        # Select final columns
        df_gdp = df_gdp[['countries', 'year', 'gdp', 'world_gdp', 'gdp_share']]
        
        self._gdp_cache = df_gdp
        print(f"Loaded GDP data for {df_gdp['countries'].nunique()} countries, years {df_gdp['year'].min()}-{df_gdp['year'].max()}")
        
        return df_gdp
    

    def countries_share_and_sjr(
        self,
        metadata_df: pd.DataFrame,
        top_n_line: int = 10,   # Anzahl Länder für Linienplot und farbig im Scatter
        top_n_scatter: int = 20, # Anzahl Länder für Scatter-Plot insgesamt
        figsize: tuple = (16, 6),
        font_size: int = 12,
        color_map: dict = None,
        legend_loc: str = 'upper right',
        legend_bbox: tuple = None,
        normalize_by_population: bool = False,  # Normalisierung nach Bevölkerungsanteil
        population_excel_path: str = None,  # Pfad zur UN WPP Excel-Datei
        normalize_by_gdp: bool = False,  # Normalisierung nach GDP-Anteil
        gdp_excel_path: str = None,  # Pfad zur World Bank GDP Excel-Datei
        max_year: int = None,  # Maximales Jahr für Plotting und Datennutzung
        country_groups: dict = None  # Dict mit Gruppennamen als Keys und Liste von Ländercodes als Values
    ):
        """
        Plot country share of papers and average SJR.
        
        Args:
            metadata_df: DataFrame with paper metadata including 'countries', 'DOI', 'SJR', 'publication_year'
            top_n_line: Number of countries for line plot (or groups + remaining countries)
            top_n_scatter: Number of countries for scatter plot
            figsize: Figure size
            font_size: Font size for labels
            color_map: Optional color mapping for countries
            legend_loc: Legend location
            legend_bbox: Legend bounding box
            normalize_by_population: If True, divide share of papers by share of world population.
                                     This shows research output relative to population size.
            population_excel_path: Path to the UN World Population Prospects Excel file.
                                   Required when normalize_by_population=True.
            normalize_by_gdp: If True, divide share of papers by share of world GDP.
                              This shows research output relative to economic size.
            gdp_excel_path: Path to the World Bank GDP Excel file.
                            Required when normalize_by_gdp=True.
            max_year: Maximum year to include in plot and data analysis.
                      If None, all years are used.
            country_groups: Dict mit Gruppennamen als Keys und Liste von Ländercodes als Values.
                           Gruppen werden aggregiert im Linienplot angezeigt.
                           Beispiel: {"EU": ["DE", "FR", "IT"], "Asia": ["CN", "JP", "IN"]}
        """
        # Validate that only one normalization is used
        if normalize_by_population and normalize_by_gdp:
            raise ValueError("Cannot use both normalize_by_population and normalize_by_gdp at the same time.")
        
        # --- Font size ---
        mpl.rcParams.update({
            'axes.titlesize': font_size,
            'axes.labelsize': font_size,
            'xtick.labelsize': font_size,
            'ytick.labelsize': font_size,
            'legend.fontsize': font_size,
            'legend.title_fontsize': font_size
        })

        # --- Load normalization data if needed ---
        if normalize_by_population:
            if population_excel_path is None:
                raise ValueError("population_excel_path must be provided when normalize_by_population=True")
            norm_df = self._load_population_data(population_excel_path)
            norm_share_col = 'population_share'
        elif normalize_by_gdp:
            if gdp_excel_path is None:
                raise ValueError("gdp_excel_path must be provided when normalize_by_gdp=True")
            norm_df = self._load_gdp_data(gdp_excel_path)
            norm_share_col = 'gdp_share'

        # --- Filter by max_year if specified ---
        if max_year is not None:
            metadata_df = metadata_df[metadata_df['publication_year'] <= max_year].copy()
        
        # --- Missing info ---
        missing_papers = metadata_df[metadata_df['countries'].str.len() == 0]['DOI'].nunique()
        total_papers = metadata_df['DOI'].nunique()
        print(f"Missing country info: {missing_papers} papers ({missing_papers/total_papers*100:.2f} %)")
        missing_sjr = metadata_df['SJR'].isna().sum()
        print(f"Missing SJR info: {missing_sjr} papers ({missing_sjr/total_papers*100:.2f} %)")

        # --- Clean Data ---
        df_clean = metadata_df[metadata_df['countries'].str.len() > 0].explode('countries')
        df_clean['SJR'] = pd.to_numeric(df_clean['SJR'].str.replace(',', '.'), errors='coerce')

        # --- Linienplot (über Jahre) ---
        total_per_year = df_clean.groupby('publication_year')['DOI'].nunique()
        counts_year = df_clean.groupby(['publication_year', 'countries'])['DOI'].nunique().reset_index(name='count')
        counts_year['share'] = counts_year.apply(lambda row: row['count']/total_per_year[row['publication_year']], axis=1)
        
        # Top Länder immer basierend auf absolutem Share auswählen
        counts_total_line = df_clean.groupby('countries')['DOI'].nunique().reset_index(name='count')
        counts_total_line['share'] = counts_total_line['count'] / total_papers
        
        # Bestimme welche Länder zu Gruppen gehören
        countries_in_groups = set()
        if country_groups is not None:
            for country_list in country_groups.values():
                countries_in_groups.update(country_list)
        
        # Für Linienplot: Gruppen + restliche Top-Länder
        if country_groups is not None:
            # Länder außerhalb von Gruppen
            countries_outside_groups = counts_total_line[~counts_total_line['countries'].isin(countries_in_groups)]
            top_countries_line = countries_outside_groups.nlargest(top_n_line - len(country_groups), 'share')['countries'].tolist()
            # Füge Gruppennamen hinzu
            top_countries_line = list(country_groups.keys()) + top_countries_line
        else:
            top_countries_line = counts_total_line.nlargest(top_n_line, 'share')['countries'].tolist()
        
        counts_total_scatter = df_clean.groupby('countries')['DOI'].nunique().reset_index(name='count')
        counts_total_scatter['share'] = counts_total_scatter['count'] / total_papers
        top_countries_scatter = counts_total_scatter.nlargest(top_n_scatter, 'share')['countries'].tolist()
        
        if normalize_by_population or normalize_by_gdp:
            # Merge normalization data
            counts_year = counts_year.merge(
                norm_df[['countries', 'year', norm_share_col]],
                left_on=['countries', 'publication_year'],
                right_on=['countries', 'year'],
                how='left'
            )
            # Calculate normalized ratio: share of papers / share of population or GDP
            # A value > 1 means the country produces more papers than expected
            counts_year['normalized_share'] = counts_year['share'] / counts_year[norm_share_col]
            # Handle missing data
            counts_year['normalized_share'] = counts_year['normalized_share'].fillna(0)
            plot_column = 'normalized_share'
        else:
            plot_column = 'share'

        # Pivot für Linienplot (mit Ländern für Linien)
        counts_top_year = counts_year[counts_year['countries'].isin(top_countries_line)]
        pivot_share_year = counts_top_year.pivot(index='publication_year', columns='countries', values=plot_column).fillna(0)

        # --- Gruppen aggregieren (falls vorhanden) und zum Pivot hinzufügen ---
        if country_groups is not None:
            for group_name, country_list in country_groups.items():
                if group_name not in pivot_share_year.columns:
                    # Aggregiere Daten für diese Gruppe über alle Jahre
                    if normalize_by_population or normalize_by_gdp:
                        # Bei Normalisierung: summiere rohe shares und normalisierungs-shares, dann neu dividieren
                        group_data_by_year = counts_year[counts_year['countries'].isin(country_list)].groupby('publication_year').agg(
                            share_sum=('share', 'sum'),
                            norm_share_sum=(norm_share_col, 'sum')
                        ).reset_index()
                        group_data_by_year[plot_column] = group_data_by_year['share_sum'] / group_data_by_year['norm_share_sum']
                        group_data_by_year[plot_column] = group_data_by_year[plot_column].fillna(0)
                    else:
                        group_data_by_year = counts_year[counts_year['countries'].isin(country_list)].groupby('publication_year').agg(
                            **{plot_column: (plot_column, 'sum')}
                        ).reset_index()
                    
                    # Füge zu Pivot hinzu
                    pivot_share_year[group_name] = group_data_by_year.set_index('publication_year')[plot_column]
                    pivot_share_year[group_name] = pivot_share_year[group_name].fillna(0)

        # --- Scatter-Plot Daten ---
        df_top_scatter = df_clean[df_clean['countries'].isin(top_countries_scatter)].copy()
        total_papers_with_country = df_clean['DOI'].nunique()
        
        if normalize_by_population or normalize_by_gdp:
            # Für Scatter: Durchschnitt des normalisierten Shares
            scatter_data = counts_year[counts_year['countries'].isin(top_countries_scatter)].groupby('countries').agg(
                share_of_paper=('normalized_share', 'mean')
            ).reset_index()
            # Add average SJR
            sjr_data = df_top_scatter.groupby('countries')['SJR'].mean().reset_index()
            sjr_data.columns = ['countries', 'average_sjr']
            scatter_data = scatter_data.merge(sjr_data, on='countries', how='left')
            
            # Füge aggregierte Gruppendaten zum Scatter hinzu
            if country_groups is not None:
                for group_name, country_list in country_groups.items():
                    # Berechne aggregierte Daten für die gesamte Gruppe (nicht nur die in top_countries_scatter)
                    group_share = counts_year[
                        (counts_year['countries'].isin(country_list)) & 
                        (counts_year['publication_year'].notna())
                    ]['normalized_share'].mean()
                    
                    # Durchschnittliche SJR für alle Papers in der Gruppe
                    group_df = df_clean[df_clean['countries'].isin(country_list)]
                    group_sjr = group_df['SJR'].mean()
                    
                    # Füge Gruppen-Eintrag zu scatter_data hinzu
                    scatter_data = pd.concat([scatter_data, pd.DataFrame({
                        'countries': [group_name],
                        'share_of_paper': [group_share],
                        'average_sjr': [group_sjr]
                    })], ignore_index=True)
        else:
            scatter_data = df_top_scatter.groupby('countries').agg(
                share_of_paper=('DOI', lambda x: x.nunique() / total_papers_with_country),
                average_sjr=('SJR', 'mean')
            ).reset_index()
            
            # Füge aggregierte Gruppendaten hinzu
            if country_groups is not None:
                for group_name, country_list in country_groups.items():
                    group_df = df_clean[df_clean['countries'].isin(country_list)]
                    group_share = group_df['DOI'].nunique() / total_papers_with_country
                    group_sjr = group_df['SJR'].mean()
                    
                    scatter_data = pd.concat([scatter_data, pd.DataFrame({
                        'countries': [group_name],
                        'share_of_paper': [group_share],
                        'average_sjr': [group_sjr]
                    })], ignore_index=True)


        # --- Plot ---
        fig, axes = plt.subplots(1, 2, figsize=figsize)

        # Linker Plot: Linienplot
        for country in pivot_share_year.columns:
            color = color_map.get(country) if color_map else None
            
            if normalize_by_population or normalize_by_gdp:
                # Für normalisierte Werte: keine Multiplikation mit 100
                axes[0].plot(pivot_share_year.index, pivot_share_year[country],
                            linestyle='-', marker='o', markersize=0, linewidth=2, label=country, color=color)
            else:
                axes[0].plot(pivot_share_year.index, pivot_share_year[country]*100,
                            linestyle='-', marker='o', markersize=0, linewidth=2, label=country, color=color)
        
        axes[0].set_title("a", loc='left', fontweight='bold')
        axes[0].set_xlabel("Publication Year")
        
        if normalize_by_population:
            axes[0].set_ylabel("Population-relative\npublications")
        elif normalize_by_gdp:
            axes[0].set_ylabel("GDP-relative\npublications")
        else:
            axes[0].set_ylabel("Share of Papers [%]")
        axes[0].grid(True, linestyle='--', linewidth=0.7, alpha=0.9)

        # Rechter Plot: Scatter-Plot mit Top-Ländern + Gruppen eingefärbt, Einzelländer aus Gruppen grau
        # Länder-zu-Gruppe Mapping
        country_to_group = {}
        if country_groups:
            for group_name, country_list in country_groups.items():
                for country_code in country_list:
                    country_to_group[country_code] = group_name
        
        # Bestimme Gruppen-Namen
        group_names_set = set(country_groups.keys()) if country_groups else set()
        
        rest_labeled = False  # Flag to add "Rest" label only once
        for _, row in scatter_data.iterrows():
            country_name = row['countries']
            
            # Färbung: Top-Länder (nicht aus Gruppen) + Gruppen eingefärbt, alles andere grau
            if country_name in top_countries_line:
                # Das ist ein Top-Land oder eine Gruppe -> eingefärbt
                color = color_map.get(country_name) if color_map else None
                label = country_name
            elif country_name in group_names_set:
                # Das ist eine Gruppe -> eingefärbt
                color = color_map.get(country_name) if color_map else None
                label = country_name
            else:
                # Rest (einzelne Länder oder nicht Top-Länder)
                color = 'lightgray'
                label = 'Others' if not rest_labeled else None
                rest_labeled = True
            
            if normalize_by_population or normalize_by_gdp:
                axes[1].scatter(row['share_of_paper'], row['average_sjr'], s=100, label=label, color=color)
            else:
                axes[1].scatter(row['share_of_paper']*100, row['average_sjr'], s=100, label=label, color=color)

        axes[1].set_title("b", loc='left', fontweight='bold')
        if normalize_by_population:
            axes[1].set_xlabel("Population-relative publications")
        elif normalize_by_gdp:
            axes[1].set_xlabel("GDP-relative publications")
        else:
            axes[1].set_xlabel("Share of Papers [%]")
        axes[1].set_ylabel("Average SJR")
        axes[1].grid(True, linestyle='--', linewidth=0.7, alpha=0.9)

        # Gemeinsame Legende rechts (aus Linienplot für konsistente Reihenfolge)
        handles_line, labels_line = axes[0].get_legend_handles_labels()
        if legend_bbox is not None:
            fig.legend(handles_line, labels_line, loc='center', bbox_to_anchor=legend_bbox, frameon=True, title='Countries')
        else:
            fig.legend(handles_line, labels_line, loc=legend_loc, frameon=True, title='Countries')

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
        font_size: int = 12,
        n_cols: int = 2
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

        # --- First pass: compute global entity ranking across all dfs ---
        global_entity_scores = {}
        for df in dfs:
            df_temp = df.copy()
            df_temp = df_temp[df_temp[year_col].notnull()]
            df_temp[year_col] = df_temp[year_col].astype(int)

            total_per_year = df_temp.groupby(year_col)['DOI'].nunique()

            counts = (
                df_temp.groupby([year_col, entity_col])['DOI']
                .nunique()
                .reset_index(name='count')
            )

            counts['share'] = counts.apply(
                lambda r: r['count'] / total_per_year[r[year_col]],
                axis=1
            )

            entity_sums = counts.groupby(entity_col)['share'].sum()
            for entity, score in entity_sums.items():
                global_entity_scores[entity] = global_entity_scores.get(entity, 0) + score

        # Get top_n entities globally, sorted by total score
        global_top_entities = sorted(
            global_entity_scores.keys(),
            key=lambda x: global_entity_scores[x],
            reverse=True
        )[:top_n]

        # --- Second pass: Prepare pivots with consistent entity order ---
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

            pivot = (
                counts[counts[entity_col].isin(global_top_entities)]
                .pivot(index=entity_col, columns=year_col, values='share')
                .fillna(0)
            )

            # Reindex to ensure consistent order across all heatmaps
            pivot = pivot.reindex([e for e in global_top_entities if e in pivot.index])

            pivots.append(pivot)
            vmax_global = max(vmax_global, pivot.values.max())

        # --- Grid-Layout: n_cols Parameter statt hardcodierter 2 Spalten ---
        n_rows = math.ceil(n_plots / n_cols)

        fig, axes = plt.subplots(
            n_rows, n_cols,
            figsize=(figsize[0], figsize[1]*n_rows),
            gridspec_kw={'wspace': 0.1, 'hspace': 0.35}
        )

        # axes als flache Liste behandeln
        if n_plots == 1:
            axes = [axes]
        else:
            axes = axes.flatten()

        for idx, (ax, pivot, title) in enumerate(zip(axes, pivots, titles)):
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

            # Bestimme Position im Grid
            row_idx = idx // n_cols
            col_idx = idx % n_cols
            is_bottom_row = (row_idx == n_rows - 1) or (idx >= n_plots - n_cols)
            is_left_col = (col_idx == 0)

            # Y-Achse: nur bei linken Plots anzeigen
            if is_left_col:
                ax.set_ylabel("Technology")
            else:
                ax.set_ylabel("")
                ax.set_yticks([])

            # X-Ticks: jede vierte, nur bei untersten Plots anzeigen
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

        # --- Leere Achsen ausblenden, falls n_plots ungerade ---
        for ax in axes[n_plots:]:
            ax.axis('off')

        # --- Shared Colorbar unten horizontal ---
        sm = ScalarMappable(
            cmap=cmap,
            norm=plt.Normalize(vmin=0, vmax=vmax_global)
        )
        sm.set_array([])

        cbar = fig.colorbar(
            sm,
            ax=axes[:n_plots],
            orientation='horizontal',
            pad=0.15,
            aspect=40,
            shrink=0.8
        )
        cbar.set_label("Share of Papers [%]")
        cbar.ax.xaxis.set_major_formatter(PercentFormatter(xmax=1))

        fig.tight_layout(rect=[0, 0.12, 1, 1])
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


