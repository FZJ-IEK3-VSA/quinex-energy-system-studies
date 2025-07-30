import os
import requests
import pandas as pd

class QuinexDiscussion():
    """
    Prepares the Discusssion Data from the results observed using quinex.
    """
    
    def __init__(self):
        """
        Initializes the discussion client.
        """

        pd.set_option('display.max_colwidth', None)

        self.entity_keywords = {
            "battery": ["Lithium-Ion Battery", "Nickel-Iron Battery", "Magnesium Sulfur Battery", "Lithium Battery", "Lithium Iron Phosphate Battery", "Lead Acid Battery", "Battery"],
            "hydrogen": ["Hydrogen", "Green Hydrogen", "Blue Hydrogen", "Grey Hydrogen", "Brown Hydrogen", "Black Hydrogen", "Turquoise Hydrogen", "Pink Hydrogen", "Yellow Hydrogen", "White Hydrogen", "Liquid Hydrogen", "Compressed Hydrogen",  "Gaseous Hydrogen", "Solid Hydrogen"],
            "pv": ["Photovoltaic (PV) System", "Rooftop PV System", "Utility-scale PV System", "Ground-mounted PV System", "Floating PV System (FPV)", "Building-Integrated PV System (BIPV)", "Photovoltaic-Thermal System (PVT)", "Hybrid PV System"],
            "wind turbine": ["Wind Turbine", "Onshore Wind Turbine", "Offshore Wind Turbine", "Nearshore Wind Turbine", "Floating Offshore Wind Turbine", "Small Wind Turbine", "Large Wind Turbine", "Vertical Axis Wind Turbine (VAWT)", "Horizontal Axis Wind Turbine (HAWT)", "Airborne Wind Turbine", "Direct Drive Wind Turbine"],
            "natural gas": ["Natural Gas", "Liquefied Natural Gas (LNG)", "Compressed Natural Gas (CNG)", "Natural Gas with CCS"],
            "electrolyzer": ["Electrolyzer", "PEM Electrolyzer", "Alkaline Electrolyzer", "AEM Electrolyzer", "AEC Electrolyzer", "CO2 Electrolyzer", "Solid Oxide Electrolyzer", "Methane Electrolyzer", "Ethylene Electrolyzer"],
            "bess": ["Lithium-ion BESS", "Sodium-ion BESS", "Redox Flow BESS", "Second-life BESS", "Residential BESS", "Commercial BESS", "Utility-scale BESS"],
        }

        self.property_keywords = {
            "cost": ["Capital Cost", "Operating Cost", "Levelized Cost", "LCOH", "LCOE", "COE", "LCOS", "Electricity Cost", "Production Cost", "Total Cost", "Cost"],
            "lifetime": ["Lifetime"],
            "capacity": ["Installed Capacity"],
            "efficiency": ["Efficiency"]
        }

    # ----------------------------------- Functions for Loading and Saving Data -----------------------------------------------------------

    def load_df(self, path="df_quinex.parquet"):
        """
        Loads the DataFrame from disk.

        Args:
            path (str): File path of the saved DataFrame.
        """
        if not os.path.exists(path):
            raise FileNotFoundError(f"No saved DataFrame found at '{path}'")

        df = pd.read_parquet(path)
        print(f"📂 Loaded DataFrame from '{path}' with {len(df)} rows")
        return df
    

    def save_df(self, df: pd.DataFrame, path="df_quinex.parquet"):
        """
        Saves the DataFrame to disk.

        Args:
            df (pd.DataFrame): The DataFrame to save.
            path (str): File path to save the DataFrame.
        """
        df.to_parquet(path)
        print(f"💾 Saved DataFrame to '{path}' with {len(df)} rows")
    
    
    # ----------------------------------- Functions for Metadata -----------------------------------------------------------

    def get_metadata(self, df, entity_keywords=None, property_keywords=None, top_n=None, exact_match=False):
        """
        Provides an overview of the most common entity and property values based on search terms.

        Args:
            df (pd.DataFrame): DataFrame with at least the columns 'entity' and 'property'.
            entity_keywords (list of str): List of keywords for filtering the entity column.
            property_keywords (list of str): List of keywords for filtering the property column.
            top_n (int): Number of top values to be output. If None, return all.
            exact_match (bool): If True, match keywords exactly; otherwise use substring match (contains).
        """
        
        filtered_df = df.copy()

        if entity_keywords:
            if exact_match:
                filtered_df = filtered_df[filtered_df['entity'].isin(entity_keywords)]
            else:
                pattern = '|'.join(entity_keywords)
                filtered_df = filtered_df[filtered_df['entity'].str.contains(pattern, case=False, na=False)]

        if property_keywords:
            if exact_match:
                filtered_df = filtered_df[filtered_df['property'].isin(property_keywords)]
            else:
                pattern = '|'.join(property_keywords)
                filtered_df = filtered_df[filtered_df['property'].str.contains(pattern, case=False, na=False)]

        total_statements = len(filtered_df)
        entity_counts = filtered_df['entity'].value_counts()
        property_counts = filtered_df['property'].value_counts()

        top_entities = entity_counts if top_n is None else entity_counts.head(top_n)
        top_properties = property_counts if top_n is None else property_counts.head(top_n)

        return {
            'total_statements': total_statements,
            'top_entities': top_entities,
            'top_properties': top_properties,
            'filtered_df': filtered_df  # Optional, falls man die Zeilen weiter untersuchen will
        }
    

    def print_metadata(self, metadata: dict):
        """
        Function for printing the metadata.

        Args:
            metadata (dict): The metadata to print
        """

        e = metadata['top_entities']
        p = metadata['top_properties']

        print(f"{'Entity':<30} {'Count':>5}    |    {'Property':<30} {'Count':>5}")
        print("-" * 80)
        for ent, prop in zip(e.items(), p.items()):
            print(f"{ent[0]:<30} {ent[1]:>5}    |    {prop[0]:<30} {prop[1]:>5}")


    # ----------------------------------- Functions for Mapping the data -----------------------------------------------------------

    def map_mentions(self, mention_list: list, mapping_list: list, threshold: float = 0.8):
        """
        Compute the highest similarity between each mention and a list of canonical entities.

        Args:
            mention_list (list): List of mentions to compare (e.g., ["battery storage", "lithium-ion battery"]).
            mapping_list (list): Canonical mapping strings (e.g., ["Li-ion battery", "Lead-acid battery"]).
            threshold (float): Threshold of the similarity to be considered a match.
        """

        url = "http://127.0.0.1:8080/biencoder/match_definition_mention"
        json_dict = {
            "mapping_list": mapping_list,
            "mention_list": mention_list
        }
        response = requests.post(url, json=json_dict)
    
        return {r["mention"]: r["best_mapping"] for r in response.json() if r["score"] >= threshold}