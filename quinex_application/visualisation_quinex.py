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
    
    def save_df(self, df, path):
        """
        Saves the DataFrame to disk using pickle format.

        Args:
            df (pd.DataFrame): The DataFrame to save.
            path (str): File path for saving.
        """
        df.to_pickle(path)
        print(f"✅ DataFrame saved to '{path}'")

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

        df = pd.read_pickle(path)
        print(f"📂 Loaded DataFrame from '{path}' with {len(df)} rows")
        return df



    # ----------------------------------- Functions for Graphics-----------------------------------------------------------
    
    def plot_top_values(self, df, column, top_n=10, ignore_empty=True, figsize=(6,6)):
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

        fig, ax = plt.subplots(figsize=figsize)
        sns.barplot(x=value_counts.values, y=value_counts.index, ax=ax, palette="dark:steelblue", hue=value_counts.index, legend=False)

        ax.set_xlabel("Count")
        ax.set_ylabel(column.capitalize())
        ax.set_title(f"Top {top_n} most frequent '{column}' values")

        plt.tight_layout()
        return fig
    
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

        if ignore_empty:
            df_entity = df_entity.dropna(subset=["property"])
            df_entity = df_entity[df_entity["property"].str.strip() != ""]  

        # Count top properties
        value_counts = df_entity["property"].value_counts().nlargest(top_n)

        # Plot
        fig, ax = plt.subplots(figsize=figsize)
        sns.barplot(x=value_counts.values, y=value_counts.index, ax=ax, palette="dark:steelblue", hue=value_counts.index, legend=False)

        ax.set_xlabel("Count")
        ax.set_ylabel("Property")
        ax.set_title(f"Top {top_n} properties for entity: '{entity_name}'")
        plt.tight_layout()

        return fig    

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

        if ignore_empty:
            df_filtered = df_filtered.dropna(subset=["quantity"])
            df_filtered = df_filtered[df_filtered["quantity"].astype(str).str.strip() != ""]

        value_counts = df_filtered["quantity"].value_counts().nlargest(top_n)

        fig, ax = plt.subplots(figsize=figsize)
        sns.barplot(x=value_counts.values, y=value_counts.index, ax=ax, palette="dark:steelblue", hue=value_counts.index, legend=False)

        ax.set_xlabel("Count")
        ax.set_ylabel("Quantity")
        ax.set_title(f"Top {top_n} quantities for '{property_name}' (entity: '{entity_name}')")
        plt.tight_layout()

        return fig, df_filtered
