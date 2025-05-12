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

            statements = result.get("annotations", {}).get("quantitative_statements", [])

            for stm in statements:
                records.extend(self.parse_statement(stm))

        return pd.DataFrame(records)

    def parse_statement(self, stm):
        """
        Parses a single quantitative statement into one or more structured records.

        Args:
            stm (dict): A single statement containing claim and qualifiers.
        """

        records = []
        claim = stm.get("claim", {})
        qualifiers = stm.get("qualifiers", {})

        entity = claim.get("entity", {}).get("text", "")
        prop = claim.get("property", {}).get("text", "")
        temporal = qualifiers.get("temporal_scope", {}).get("text", "")
        spatial = qualifiers.get("spatial_scope", {}).get("text", "")

        quantity_modifier = [q["value"]["normalized"]["modifiers"] for q in claim.get("quantity", {}).get("normalized", {}).get("individual_quantities", {}).get("normalized", [])]
        quantity = claim.get("quantity", {}).get("text", "")
        combined_quantity = f"{", ".join(set(quantity_modifier))} {quantity}".strip()

        records.append({
            "paper_id": self.doi,
            "entity": entity,
            "property": prop,
            "quantity": combined_quantity,
            "temporal_scope_text": temporal,
            "spatial_scope_text": spatial,
        })

        return records
    
    def plot_top_values(self, df, column, top_n=10, ignore_empty=True):
        """
        Creates a bar plot of the top N most frequent quantitative properties.

        Args:
            df (pd.DataFrame): The DataFrame containing the extracted data.
            column (str): The column name to analyze.
            top_n (int): Number of top properties to display.
            ignore_empty (bool): Whether to exclude empty or null values.
        """

        data = df[column]

        if ignore_empty:
            data = data[data.notna() & (data != "")]

        value_counts = data.value_counts().nlargest(top_n)

        fig, ax = plt.subplots(figsize=(10, 6))
        sns.barplot(x=value_counts.values, y=value_counts.index, ax=ax, palette="dark:steelblue", hue=value_counts.index, legend=False)

        ax.set_xlabel("Count")
        ax.set_ylabel(column.capitalize())
        ax.set_title(f"Top {top_n} most frequent '{column}' values")

        plt.tight_layout()
        return fig
