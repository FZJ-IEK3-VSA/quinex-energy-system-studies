import pandas as pd
import os
from pathlib import Path

class ProcessScopusData():
    """
    A class to process and merge Scopus CSV data, manage boolean flags for sources and queries,
    and maintain an up-to-date parquet dataset.
    """

    def __init__(self, csvs_paths: str, output_path: str, query_name: str, query_date: str, quelle_name: str):
        """
        Initializes the ScopusProcessor with file_paths and column names.
        Args:
            csvs_paths (list[str]): List of CSV file paths to load and combine.
            output_path (Path): Path to save/load the parquet dataset.
            query_name (str): Name of the query for marking columns.
            query_date (str): Date string used in query column names.
            quelle_name (str): Name of the source/quelle to mark in the dataset.
        """
        pd.set_option('display.max_colwidth', None)

        self.csvs_paths = csvs_paths
        self.output_path = Path(output_path)

        self.query_name = query_name
        self.quelle_name = quelle_name
        self.query_date = query_date
        self.df = None
        self.additional_cols = ["Quinex", "Quinex_ID", "Quinex_Version", "Lizenz", "OEO_Version", "Download_Status"]

        self.parquet_df = self.load_parquet_if_exists()

    def combine_csvs(self, sort_by_year=True):
        """
        Reads and concatenates all CSV and Excel files, removes duplicates,
        adds boolean columns marking the source and query date,
        and ensures additional columns are present.

        Args:
            sort_by_year (bool, optional): _description_. Defaults to True.
        """
        ext = os.path.splitext(self.csvs_paths[0])[-1].lower()
        if ext == '.csv':
            dfs = [pd.read_csv(path) for path in self.csvs_paths]
        elif ext in ['.xls', '.xlsx']:
            dfs = [pd.read_excel(path) for path in self.csvs_paths]
        else:
            raise ValueError(f"Unsupported file type: {self.csvs_paths}. Only .csv, .xls, and .xlsx are supported.")


        # Concatenate CSVs and remove duplicate rows
        self.df = pd.concat(dfs, ignore_index=True).drop_duplicates()

        if self.quelle_name == "Source: WOS":
            rename_map = {
                'Publication Year': 'Year',
                'Source Title': 'Source title',
                'Times Cited, All Databases': 'Cited by',
                'DOI': 'DOI',
                'DOI Link': 'Link',
                'Open Access Designations': 'Open Access'
            }
            columns_to_keep = [col for col in rename_map if col in self.df.columns]
            self.df = self.df[columns_to_keep].rename(columns={k: rename_map[k] for k in columns_to_keep})
            # No Link in WOS
            self.df["Link"] = pd.NA


        # Optionally sort by 'Year' column ascending
        if sort_by_year and "Year" in self.df.columns:
            self.df["Year"] = pd.to_numeric(self.df["Year"], errors="coerce")
            self.df = self.df.sort_values(by="Year", ascending=True).reset_index(drop=True)

         # Add boolean columns marking source and query date presence
        query_col = f"{self.query_name}_{self.query_date}"
        self.df[self.quelle_name] = True
        self.df[query_col] = True
        self.df[[self.quelle_name, query_col]] = self.df[[self.quelle_name, query_col]].fillna(False)

        self.clean_openaccess()

        # Ensure additional columns exist; 'Quinex' as False, others as pd.NA
        for col in self.additional_cols:
            if col not in self.df.columns:
                if col == "Quinex":
                    self.df[col] = False
                else:
                    self.df[col] = pd.NA

        return self.df

    def clean_openaccess(self):
        """Remove the prefix 'All Open Access;' from the 'Open Access' column values."""
        self.df['Open Access'] = self.df['Open Access'].str.replace(r'^All Open Access;\s*', '', regex=True)
        return self.df


    def remove_duplicates_doi(self):
        """
        Sorts the dataframe by 'Cited by' descending and removes duplicate DOIs,
        keeping the first (most cited) entry.
        """

        # Sort by number of citations (descending)
        self.df = self.df.sort_values(by="Cited by", ascending=False)

        # Remove duplicates based on DOI - keep the first one
        self.df = self.df.drop_duplicates(subset="DOI", keep="first")
        self.df = self.df.sort_index().reset_index(drop=True)

        return self.df
    
    def load_parquet_if_exists(self):
        """Load existing parquet file if it exists, otherwise return an empty DataFrame."""
        if self.output_path.exists():
            return pd.read_parquet(self.output_path)
        else:
            return pd.DataFrame() 

    def update_parquet_with_new_data(self):
        """
        Main method to update the internal parquet DataFrame with new data from self.df,
        managing query/source flags and persisting the result.
        """

        if "DOI" not in self.df:
            raise ValueError("New Data must contain a 'DOI'-column.")
        
        if self.parquet_df.empty:
            self.parquet_df = self.df.copy()
        else:
            df_updated = self.get_new_dois_and_rows()
            df_updated = self.update_query_columns(df_updated)
            df_updated = self._update_source_columns(df_updated)
            self.parquet_df = df_updated
        
        self.parquet_df = self._sort_and_reorder_columns(self.parquet_df)
        self.parquet_df = self.parquet_df.fillna(pd.NA)
        return self.parquet_df
    
    def get_new_dois_and_rows(self):
        """
        Appends new rows with DOIs not yet in the parquet.
        """
        new_dois = set(self.df['DOI']) - set(self.parquet_df['DOI'])
        new_rows = self.df[self.df["DOI"].isin(new_dois)]
        return pd.concat([self.parquet_df, new_rows], ignore_index=True)
    
    def update_query_columns(self, df_updated):
        """
        Updates all 'Query:' columns with True/False depending on presence in df/parquet.
        """
        query_cols = [col for col in df_updated.columns if 'Query:' in col]

        for col in query_cols:
            if col in self.df.columns:
                dois_in_df = set(self.df[self.df[col] == True]["DOI"])
                df_updated[col] = df_updated["DOI"].apply(lambda doi: doi in dois_in_df)
            elif col in self.parquet_df.columns:
                dois_in_parquet = set(self.parquet_df[self.parquet_df[col] == True]["DOI"])
                df_updated[col] = df_updated["DOI"].apply(lambda doi: doi in dois_in_parquet)
            else:
                df_updated[col] = False

        return df_updated


    def _update_source_columns(self, df_updated):
        """
        Updates all 'Source:' columns by checking if any dataset marks the DOI as True in that column.
        """
        source_cols = [col for col in df_updated.columns if 'Source:' in col]

        for col in source_cols:
            dois_true_df = set(self.df[self.df[col] == True]["DOI"]) if col in self.df.columns else set()
            dois_true_parquet = set(self.parquet_df[self.parquet_df[col] == True]["DOI"]) if col in self.parquet_df.columns else set()
            valid_dois = dois_true_df.union(dois_true_parquet)

            df_updated[col] = df_updated["DOI"].apply(lambda doi: doi in valid_dois)

        return df_updated
    
    def _sort_and_reorder_columns(self, df):
        """
        Sorts the DataFrame by year and reorders columns: Open Access → Source → Query → rest.
        """
        df = df.sort_values(by="Year", ascending=True).reset_index(drop=True)

        cols = list(df.columns)
        index_oa = cols.index("Open Access")
        group1 = cols[:index_oa+1]

        rest = cols[index_oa+1:]
        group2 = [c for c in rest if "Source" in c]
        rest = [c for c in rest if "Source" not in c]
        group3 = [c for c in rest if "Query" in c]
        rest = [c for c in rest if "Query" not in c]

        ordered_cols = group1 + group2 + group3 + rest
        df = df[ordered_cols]

        return df

    def save_df(self):
        """Save the current combined dataframe (self.parquet_df) to Parquet."""
        self.parquet_df.to_parquet(self.output_path, index=False)

    def load_csv(self, combined=True, cleaned=True, year=""):
        """
        Load a CSV file based on parameters.

        Args:
            combined (bool): Whether to load the combined/cleaned file.
            cleaned (bool): If combined=True, whether to load the cleaned version.
            year (str): Year string to identify a single CSV file if combined=False.
        """

        if combined:
            if cleaned:
                path = self.output_path
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