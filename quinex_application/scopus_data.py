import pandas as pd
import glob


class ProcessScopusData():
    def __init__(self, csvs_paths, output_path, cleaned_output_path):
        pd.set_option('display.max_colwidth', None)
        self.csvs_paths = csvs_paths
        self.output_path = output_path
        self.cleaned_output_path = cleaned_output_path

    def combine_csvs(self, sort_by_year=True):
        # Alle CSV-Dateien einlesen
        dfs = [pd.read_csv(path) for path in self.csvs_paths]

        # Kombinieren und Duplikate entfernen
        self.df = pd.concat(dfs, ignore_index=True)
        self.df = self.df.drop_duplicates()

        # Optional nach Jahr sortieren
        if sort_by_year and "Year" in self.df.columns:
            self.df["Year"] = pd.to_numeric(self.df["Year"], errors="coerce")
            self.df = self.df.sort_values(by="Year", ascending=True).reset_index(drop=True)

        # In Zielpfad speichern
        self.df.to_csv(self.output_path, index=False)
        return self.df

    def clean_openaccess(self):
        self.df['Open Access'] = self.df['Open Access'].str.replace(r'^All Open Access;\s*', '', regex=True)
        return self.df


    def remove_duplicates_doi(self):
        # Sortieren nach Anzahl der Zitationen (absteigend)
        self.df = self.df.sort_values(by="Cited by", ascending=False)

        # Duplikate basierend auf DOI entfernen – ersten behalten
        self.df = self.df.drop_duplicates(subset="DOI", keep="first")
        self.df = self.df.sort_index().reset_index(drop=True)

        return self.df

    def save_df(self):
        self.df.to_csv(self.cleaned_output_path, index=False)

    def load_csv(self, combined=True, cleaned=True, year=""):
        if combined:
            if cleaned:
                path = self.cleaned_output_path
            else:
                path = self.output_path
        else:
            for p in self.csvs_paths:
                if year in p:
                    path = p
                    break
            else:
                raise ValueError(f"No CSV-path for the year {year}")

        df = pd.read_csv(path)
        return df   