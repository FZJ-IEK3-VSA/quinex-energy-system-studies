import pandas as pd
pd.set_option('display.max_colwidth', None)

def combine_csvs(csv_paths, output_path, sort_by_year=True):
    # Alle CSV-Dateien einlesen
    dfs = [pd.read_csv(path) for path in csv_paths]
    
    # Kombinieren und Duplikate entfernen
    df = pd.concat(dfs, ignore_index=True)
    df = df.drop_duplicates()

    # Optional nach Jahr sortieren
    if sort_by_year and "Year" in df.columns:
        df["Year"] = pd.to_numeric(df["Year"], errors="coerce")
        df = df.sort_values(by="Year", ascending=True).reset_index(drop=True)

    # In Zielpfad speichern
    df.to_csv(output_path, index=False)
    return df

def load_csv(combined=True, year=""):
    if combined:
        path = "data/external/scopus_2025_04_30.csv"
    else:
        path = "data/external/scopus/scopus_2025_04_30_" + f"{year}.csv"
    df = pd.read_csv(path)
    return df

def remove_duplicates_doi(df, path):
    # Sortieren nach Anzahl der Zitationen (absteigend)
    df_sorted = df.sort_values(by="Cited by", ascending=False)

    # Duplikate basierend auf DOI entfernen – ersten behalten
    df_unique_by_citations = df_sorted.drop_duplicates(subset="DOI", keep="first")
    df_unique_by_citations = df_unique_by_citations.sort_index().reset_index(drop=True)
    df_unique_by_citations.to_csv(path, index=False)

    return df_unique_by_citations