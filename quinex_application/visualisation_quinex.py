import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

class VisualisationQuinex():
    """
    Visualises the results observed using quinex.
    """
    
    def __init__(self):
        """
        Initializes the visualisation client.
        """

        pd.set_option('display.max_colwidth', None)

    # ----------------------------------- Functions for Saving Analysis-----------------------------------------------------------

    def create_df(self, analysis):
        """
        Transforms a Quinex analysis result into a structured pandas DataFrame.

        Args:
            analysis (list): List of analysis results (typically JSON-like dicts) per paper.

        Returns:
            pd.DataFrame: A DataFrame with extracted quantitative statements and qualifiers.
        """
        records = []

        for paper in analysis:
            self.doi = paper.get("_id")
            result = paper.get("analysis_result")

            if not result:
                print(f"⚠️  No analysis result for DOI: {self.doi}")
                continue

            self.text = result["text"]
            statements = result.get("annotations", {}).get("quantitative_statements", [])

            for self.stm in statements:
                records.extend(self.parse_statement())
     
        return pd.DataFrame(records)

    def parse_statement(self):
        """
        Parses a single quantitative statement into one or more structured records.
        """

        records = []
        claim = self.stm.get("claim", {})
        qualifiers = self.stm.get("qualifiers", {})

        entity = claim.get("entity", {}).get("text", "")
        prop = claim.get("property", {}).get("text", "")
        temporal = qualifiers.get("temporal_scope", {}).get("text", "")
        spatial = qualifiers.get("spatial_scope", {}).get("text", "")

        quantity_modifier = [q["value"]["normalized"]["modifiers"] for q in claim.get("quantity", {}).get("normalized", {}).get("individual_quantities", {}).get("normalized", [])]
        quantity = claim.get("quantity", {}).get("text", "")
        combined_quantity = f"{", ".join(set(quantity_modifier))} {quantity}".strip()

        unit = claim.get("quantity", {}).get("normalized", {}).get("individual_quantities", {}).get("normalized", [])

        units = [n for u in unit for n in u.get("unit", {}).get("normalized", [])]
        combined_unit = [{"uri": u.get("uri"), "exponent": u.get("exponent"), "year": u.get("year")} for u in units]
        text_quote = self.get_quote()

        records.append({
            "paper_id": self.doi,
            "entity": entity,
            "property": prop,
            "quantity": combined_quantity,
            "unit": combined_unit,
            "quote": text_quote,
            "temporal_scope_text": temporal,
            "spatial_scope_text": spatial,
        })
        return records
    
    def get_quote(self):
        entity = self.stm.get("claim", {}).get("entity", {})
        prop = self.stm.get("claim", {}).get("property", {})
        quantity = self.stm.get("claim", {}).get("quantity", {})

        entity_char_offsets = [] if entity["is_implicit"] else [entity["start"], entity["end"]]
        property_char_offsets = [] if prop["is_implicit"] else [prop["start"], prop["end"]]
        quantity_char_offsets = [quantity["start"], quantity["end"]]

        offsets = entity_char_offsets + property_char_offsets + quantity_char_offsets

        min_sorted_offsets = min(offsets)
        max_sorted_offsets = max(offsets)
        first_sent_start_before_ann = self.text.rfind(".", 0, min_sorted_offsets)
        first_sent_end_after_ann = self.text.find(".", max_sorted_offsets, len(self.text))
        
        if first_sent_start_before_ann == -1:
            if min_sorted_offsets > 150:
                # Start directly before first annotation.
                first_sent_start_before_ann = min_sorted_offsets
            else:
                # Start at start of text.
                first_sent_start_before_ann = 0

        if first_sent_end_after_ann == -1:
            first_sent_end_after_ann = max_sorted_offsets
        else:
            first_sent_end_after_ann += 1

        text_quote = (
            self.text[first_sent_start_before_ann:first_sent_end_after_ann].removeprefix(".").strip()
        )
        return text_quote

    
    def save_df(self, df, path):
        """
        Saves the DataFrame to disk using parquet format.
        If the file exists, appends the new data to the existing one.

        Args:
            df (pd.DataFrame): The DataFrame to save.
            path (str): File path for saving.
        """
        if os.path.exists(path):
            try:
                existing_df = pd.read_parquet(path)
                existing_dois = set(existing_df['paper_id'].dropna().unique())
                new_rows = df[df['paper_id'].notna() & ~df['paper_id'].isin(existing_dois)]
                

                if new_rows.empty:
                    print("ℹ️ No new DOIs to add. File remains unchanged.")
                    return
                
                combined_df = pd.concat([existing_df, new_rows], ignore_index=True)
                combined_df.to_parquet(path, index=False)
                print(f"✅ Existing file found. Appended and saved updated DataFrame to '{path}'")
            except Exception as e:
                print(f"❌ Error reading existing file: {e}")
        else:
            df.to_parquet(path, index=False)
            print(f"✅ New DataFrame saved to '{path}'")

    def load_df(self, path="df_quinex.pkl"):
        """
        Loads the DataFrame from disk.

        Args:
            path (str): File path of the saved DataFrame.

        Returns:
            pd.DataFrame: The loaded DataFrame.
        """
        if not os.path.exists(path):
            raise FileNotFoundError(f"No saved DataFrame found at '{path}'")

        df = pd.read_parquet(path)
        print(f"📂 Loaded DataFrame from '{path}' with {len(df)} rows")
        return df



    # ----------------------------------- Functions for Graphics-----------------------------------------------------------
    
    def plot_top_values(self, df, column, top_n=10, ignore_empty=True, match_column=None, score_column=None, score_limit=0.8, figsize=(6,6)):
        """
        Creates a bar plot of the top N most frequent values.
        If match_column and score_column are provided, values from match_column
        are used only when score_column >= score_limit, otherwise fallback to `column`.

        Args:
            df (pd.DataFrame): The DataFrame containing the data.
            column (str): The original column name (e.g., 'entity').
            top_n (int): Number of top values to display.
            ignore_empty (bool): Whether to exclude empty or null values.
            match_column (str): Column with matched values (e.g., 'best_oeo_match').
            score_column (str): Column with match scores (e.g., 'match_score').
            score_limit (float): Threshold above which the match_column is used.
            figsize (tuple): Size of the figure.
        """

        if match_column and score_column:
            # Kombinieren: matched value falls score >= limit, sonst original
            data = df.apply(
                lambda row: row[match_column] if pd.notna(row[score_column]) and row[score_column] >= score_limit else row[column],
                axis=1
            )
            column = "entity_levenshtein"
        else:
            data = df[column]

        if ignore_empty:
            data = data.dropna()

        return self.plot_top_values_cleaned(data, column, top_n=top_n, figsize=figsize)

    
    def plot_top_properties_of_entity(self, df, entity_name, top_n=20, ignore_empty=True, figsize=(6,6)):
        """
        Plots the most frequent properties for a specific entity.

        Args:
            df (pd.DataFrame): The DataFrame containing the extracted data
            entity_name (str): The entity for which to show property frequency.
            top_n (int): Number of top properties to display.
            ignore_empty (bool): Whether to exclude empty or null values.
        """

        df_entity = df[df["entity"] == entity_name]
        data = df_entity["property"]
        if ignore_empty:
            data = data.dropna()

        return self.plot_top_values_cleaned(data, "property", top_n=top_n, figsize=figsize, title=f"Top {top_n} properties for entity: '{entity_name}'") 

    def plot_top_quantity_of_property(self, df, entity_name, property_name, top_n=20, ignore_empty=True, figsize=(6, 6)):
        """
        Plots the most frequent quantities for a specific (entity, property) combination.

        Args:
            df (pd.DataFrame): The DataFrame containing the extracted data.
            entity_name (str): The entity to filter by.
            property_name (str): The property to filter by.
            top_n (int): Number of top quantities to display.
            ignore_empty (bool): Whether to exclude empty or null values.
            figsize (tuple): Size of the plot figure.

        """
        df_filtered = df[(df["entity"] == entity_name) & (df["property"] == property_name)]
        data = df_filtered["quantity"]
        if ignore_empty:
            data = data.dropna()
        return self.plot_top_values_cleaned(data, "quantity", top_n=top_n, figsize=figsize, title=f"Top {top_n} quantities for '{property_name}' (entity: '{entity_name}')")
    
    def plot_top_values_cleaned(self, data, column_name, top_n=10, figsize=(6, 6), title=None):
        """
        Creates an adjusted bar plot for the most frequent values in a column.

        Args:
            data (pd.Series): The column to be analyzed.
            column_name (str): Name of the column.
            top_n (int): Number of top values.
            figsize (tuple): Size of the plot figure.
            title (str): Optional plot title.
        """

        # Alle Werte zu String machen und bereinigen
        cleaned_data = (
            data.astype(str)
            .str.replace(r"\s+", " ", regex=True)
            .str.strip()
        )
        cleaned_data = cleaned_data[cleaned_data != ""]  # Leere rausfiltern

        # Top-N-Werte zählen
        value_counts = cleaned_data.value_counts().nlargest(top_n)

        # Plot erstellen
        fig, ax = plt.subplots(figsize=figsize)
        sns.barplot(x=value_counts.values, y=value_counts.index, ax=ax, palette="dark:steelblue", hue=value_counts.index, legend=False)

        ax.set_xlabel("Count")
        ax.set_ylabel(column_name.capitalize())
        ax.set_title(title if title else f"Top {top_n} values in '{column_name}'")
        plt.tight_layout()
        return fig
    
    def plot_levenshtein_score_limits(self, file_path, score_limits, match_score_column='match_score', figsize=(6, 6)):
        """
        Plots the number of DOIs with match_score >= given score_limits.

        Args:
            file_path (str): Path to the single .parquet file containing all results.
            score_limits (list[float]): List of score limits to evaluate.
            match_score_column (str): Column name that contains the match score.
            figsize (tuple): Size of the output figure.
        """

        df = pd.read_parquet(file_path)

        results = []
        for score_limit in score_limits:
            count = len(df[df[match_score_column] >= score_limit])
            results.append({
                'score_limit': score_limit,
                'doi_count': count
            })

        df_results = pd.DataFrame(results).sort_values(by='score_limit')

        # Plot
        plt.figure(figsize=figsize)
        plt.plot(df_results['score_limit'], df_results['doi_count'], marker='o')
        plt.xlabel('Score-Limit')
        plt.ylabel('Number of DOIs with match_score ≥ Score-Limit')
        plt.title('Levenshtein-Matches over the Score-Limits')
        plt.grid(True)
        plt.tight_layout()
        plt.show()

    def plot_unique_entities_over_score_limits(self, file_path, score_limits, column='entity', match_column='best_oeo_match', score_column='match_score', figsize=(6, 6)):
        """
        Plots the number of unique entities before and after Levenshtein matching,
        over different score limits.

        Args:
            file_path (str): Path to the single .parquet file containing all results.
            column (str): Original entity column.
            match_column (str): Column with Levenshtein matches.
            score_column (str): Column with match scores.
            score_limits (list): List of score thresholds.
            figsize (tuple): Figure size for the plot.
        """
        df = pd.read_parquet(file_path)
        original_count = df[column].dropna().nunique()

        results = []
        for limit in score_limits:
            # Kombiniertes Feld: matched value falls score ≥ limit, sonst original
            merged_series = df.apply(
                lambda row: row[match_column] if pd.notna(row[score_column]) and row[score_column] >= limit else row[column],
                axis=1
            )
            unique_count = merged_series.dropna().nunique()

            results.append({
                'score_limit': limit,
                'unique_entities_after_matching': unique_count
            })

        # Plot
        limits = [r['score_limit'] for r in results]
        matched_counts = [r['unique_entities_after_matching'] for r in results]

        plt.figure(figsize=figsize)
        plt.plot(limits, matched_counts, marker='o', label='After Matching')
        plt.axhline(original_count, color='steelblue', linestyle='--', label='Original (without Matching)')
        
        plt.title("Comparison: Number of unique Entities before & after Levenshtein-Matching")
        plt.xlabel("Score-Limit")
        plt.ylabel("Number of unique Entities")
        plt.legend()
        plt.grid(True)
        plt.tight_layout()
        plt.show()

