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

        self.entity_keywords_mapping = {
            "battery": {
                "types": {
                    "Lithium-Ion Battery": ["Lithium-Ion Battery", "Li-Ion Battery", "LI Battery", "Li-Ion", "LIB"],
                    "Nickel-Iron Battery": ["Nickel-Iron Battery", "Ni-Fe Battery"],
                    "Magnesium Sulfur Battery": ["Magnesium Sulfur Battery", "Mg-S Battery"],
                    "Sodium Sulfur Battery": ["Sodium Sulfur Battery", "Na-S Battery"],
                    "Lithium Battery": ["Lithium Battery", "Li Battery"],
                    "Lithium Iron Phosphate Battery": ["Lithium Iron Phosphate Battery", "LFP Battery", "LiFe Battery"],
                    "Lead Acid Battery": ["Lead Acid Battery", "Pb-Acid Battery", "LA Battery"],
                    "Battery": ["Battery", "Accumulator"]
                }
            },
            "hydrogen": {
                "types": {
                    "Hydrogen": ["Hydrogen", "H2"],
                },
                "colors": {
                    "Green Hydrogen": ["Green Hydrogen", "Green H2"],
                    "Blue Hydrogen": ["Blue Hydrogen", "Blue H2"],
                    "Grey Hydrogen": ["Grey Hydrogen", "Grey H2"],
                    "Brown Hydrogen": ["Brown Hydrogen", "Brown H2"],
                    "Black Hydrogen": ["Black Hydrogen", "Black H2"],
                    "Turquoise Hydrogen": ["Turquoise Hydrogen", "Turquoise H2"],
                    "Pink Hydrogen": ["Pink Hydrogen", "Pink H2"],
                    "Yellow Hydrogen": ["Yellow Hydrogen", "Yellow H2"],
                    "White Hydrogen": ["White Hydrogen", "White H2"],
                },
                "physical_states": {
                    "Liquid Hydrogen": ["Liquid Hydrogen", "LH2"],
                    "Compressed Hydrogen": ["Compressed Hydrogen", "CH2"],
                    "Gaseous Hydrogen": ["Gaseous Hydrogen", "GH2"],
                    "Solid Hydrogen": ["Solid Hydrogen", "SH2"]
                }
            },
            "pv": {
                "types": {
                    "PVSystem": ["PV System", "Photovoltaic System"],
                    "Rooftop PV System": ["Rooftop PV System", "Roof PV"],
                    "Utility-scale PV System": ["Utility-scale PV System", "Utility PV"],
                    "Ground-mounted PV System": ["Ground-mounted PV System", "Ground PV"],
                    "Floating PV System (FPV)": ["Floating PV System", "FPV"],
                    "Building-Integrated PV System (BIPV)": ["Building-Integrated PV System", "BIPV"],
                    "Photovoltaic-Thermal System (PVT)": ["Photovoltaic-Thermal System", "PVT"],
                    "Hybrid PV System": ["Hybrid PV System", "HPV"]
                }
            },
            "wind turbine": {
                "types": {
                    "Wind Turbine": ["Wind Turbine", "WT"],
                    "Onshore Wind Turbine": ["Onshore Wind Turbine", "Onshore WT"],
                    "Offshore Wind Turbine": ["Offshore Wind Turbine", "Offshore WT"],
                    "Nearshore Wind Turbine": ["Nearshore Wind Turbine", "Nearshore WT"],
                    "Floating Offshore Wind Turbine": ["Floating Offshore Wind Turbine", "Floating Offshore WT"],
                    "Small Wind Turbine": ["Small Wind Turbine", "Small WT"],
                    "Large Wind Turbine": ["Large Wind Turbine", "Large WT"],
                    "Vertical Axis Wind Turbine (VAWT)": ["Vertical Axis Wind Turbine", "VAWT"],
                    "Horizontal Axis Wind Turbine (HAWT)": ["Horizontal Axis Wind Turbine", "HAWT"],
                    "Airborne Wind Turbine": ["Airborne Wind Turbine"],
                    "Direct Drive Wind Turbine": ["Direct Drive Wind Turbine"]
                }
            },
            "natural gas": {
                "types": {
                    "Natural Gas": ["Natural Gas", "NG"],
                    "Liquefied Natural Gas (LNG)": ["Liquefied Natural Gas", "LNG"],
                    "Compressed Natural Gas (CNG)": ["Compressed Natural Gas", "CNG"],
                    "Natural Gas with CCS": ["Natural Gas with CCS"]
                }
            },
            "electrolyzer": {
                "types": {
                    "Electrolyzer": ["Electrolyzer"],
                    "PEM Electrolyzer": ["PEM Electrolyzer", "PEM"],
                    "Alkaline Electrolyzer": ["Alkaline Electrolyzer", "Alkaline"],
                    "AEM Electrolyzer": ["AEM Electrolyzer", "AEM"],
                    "AEC Electrolyzer": ["AEC Electrolyzer", "AEC"],
                    "CO2 Electrolyzer": ["CO2 Electrolyzer", "CO2"],
                    "Solid Oxide Electrolyzer": ["Solid Oxide Electrolyzer", "SOE"],
                    "Methane Electrolyzer": ["Methane Electrolyzer"],
                    "Ethylene Electrolyzer": ["Ethylene Electrolyzer"]
                }
            },
        }

        self.entity_keywords_string = {
            "battery": ['battery', 'batteries', 'accumulator'],
            "hydrogen": ['hydrogen', 'H2'],
            "pv": ['PV', 'photovoltaic', 'solar panel', 'solar cell'],
            "wind turbine": ["Wind"],
            "natural gas": ['natural gas', 'fossil gas', 'methane'],
            "electrolyzer": ['electrolyzer', 'electrolyser'],
        }

        self.property_keywords_mapping = {
            "cost": {
                "Capital Cost": ["Capital Cost", "Capex"],
                "Operating Cost": ["Operating Cost", "Opex"],
                "Levelized Cost": ["Levelized Cost", "LCOE", "LCOH", "LCOS", "COE"],
                "Electricity Cost": ["Electricity Cost"],
                "Production Cost": ["Production Cost"],
                "Total Cost": ["Total Cost"],
                "Cost": ["Cost"]
            },
            "lifetime": {
                #"Lifetime": ["Lifetime", "Lifespan", "Service Life", "Durability"]
                "Lifetime": ["Lifetime", "Lifespan", "Durability"]
            },
            "capacity": {
                "Installed Capacity": ["Installed Capacity", "Capacity", "Nominal Capacity", "Rated Capacity"]
            },
            "efficiency": {
                "Efficiency": ["Efficiency", "Conversion Efficiency", "Electrical Efficiency", "Thermal Efficiency"]
            }
        }

        self.property_keywords_string = {
            "cost": ['cost', 'LCOE', 'LCOH', 'COE', 'price', 'Capex', 'Opex'],
            "lifetime": ["lifetime, durability", "duration", "life"],
            "capacity": ["capacity"],
            "efficiency": ["efficiency"]
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


    # ----------------------------------- Functions for Organizing the Technology Synonyms -----------------------------------------------------------
    
    def get_all_synonyms_for_key(self, entity: bool=None, property: bool=None, main_key: str=None):
        """
        Returns all synonyms for a main category (e.g. “hydrogen”) as a flat list.

        Args:
            main_key (str): Technology for which to return the list.
            entity (bool): Wether the synonyms should be taken from the entity keywords.
            property (bool): Wether the synonyms should be taken from the property keywords.
        """

        def recurse_extract(d):
            synonyms = []
            if isinstance(d, dict):
                for v in d.values():
                    synonyms.extend(recurse_extract(v))
            elif isinstance(d, list):
                synonyms.extend(d)
            return synonyms
        
        mapping = {}
        if entity:
            mapping = self.entity_keywords_mapping
        elif property:
            mapping = self.property_keywords_mapping
        else:
            raise ValueError("Either 'entity' or #property' must be set to True")

        
        if main_key is None:
            all_synonyms = []
            for key in mapping:
                all_synonyms.extend(recurse_extract(mapping[key]))
            return all_synonyms
        
        if main_key not in mapping:
            return []
        return recurse_extract(mapping[main_key])
    

    def build_mention_to_canonical_mapping(self, entity: bool = None, property: bool = None, main_key: str=None):
        """
        Builds a dict that maps each synonymous term (lowercase) to the respective canonical term.

        Args:
            main_key (str): The technology for which to return the dict.
            entity (bool): Wether the dict should be returned from the entity keywords.
            property (bool): Wether the dict should be returned from the property keywords.
        """
        mapping_result = {}
        
        def recurse(d):
            if isinstance(d, dict):
                for canonical, syn_list in d.items():
                    if isinstance(syn_list, list):
                        for syn in syn_list:
                            mapping_result[syn.lower()] = canonical
                    elif isinstance(syn_list, dict):
                        recurse(syn_list)
            elif isinstance(d, list):
                # Falls keine weitere Unterteilung, dann das erste Element als Canonical nehmen
                # (Das ist eine einfache Heuristik)
                if len(d) > 0:
                    canonical = d[0]
                    for syn in d:
                        mapping_result[syn.lower()] = canonical

        mapping = {}
        if entity:
            mapping = self.entity_keywords_mapping
        elif property:
            mapping = self.property_keywords_mapping
        else:
            raise ValueError("Either 'entity' or #property' must be set to True")
        
        if main_key is None:
            for key in mapping:
                recurse(mapping[key])
        else:
            if main_key not in mapping:
                return {}
            recurse(mapping[main_key])
        return mapping_result
    

    def build_entity_reverse_mapping(self):
        """
        Function for Building so reverse mapping of self.entity_keywords_mapping.
        """

        reverse_mapping = {}
        for main_cat, subgroups in self.entity_keywords_mapping.items():
            for subgroup in subgroups.values():  # z. B. "types", "colors", "Hydrogen"
                if isinstance(subgroup, dict):  # weitere Untergruppen vorhanden
                    for specific_name in subgroup.keys():
                        reverse_mapping[specific_name] = main_cat
                elif isinstance(subgroup, list):  # z. B. ["Hydrogen", "H2"]
                    # Sonderfall: wenn z. B. "Hydrogen": ["Hydrogen", "H2"] als direktes Mapping
                    reverse_mapping[main_cat] = main_cat
        return reverse_mapping

    
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
    

    def perform_mapping(self, df: pd.DataFrame, mention_list: list, canonical_name: str=None, entity: bool=None, property: bool=None, threshold: float = 0.8):
        """
        Perform the Mapping of the top properties or top entities to their canonical lists.

        Args:
            df (pd.DataFrame): The DataFrame on which to perform the mapping.
            mention_list (list): The list of mentions to map to their canonical lists.
            entity_name (str, optional): The name used for the canonical entity values.
            property_name (str, optional): The name used for the canonical property values.
            threshold (float, optional): Threshold of the similarity to be considered a match.
        """

        if entity:
            canonical_values = self.get_all_synonyms_for_key(entity=True, main_key=canonical_name)
            mention_to_entity = self.map_mentions(mention_list, canonical_values, threshold=threshold)
            if not mention_to_entity:
                print(f"⚠️ No entity-Mappings for '{canonical_name}' found.")
                return df

            df.loc[:, "entity_mapping"] = df["entity"].map(mention_to_entity)
            df = df[df["entity_mapping"].notna()].copy()

            mapping_dict = self.build_mention_to_canonical_mapping(entity=True, main_key=canonical_name)
            df.loc[:, 'entity_text_lower'] = df['entity_mapping'].str.lower()
            df.loc[:, 'entity_mapping'] = df['entity_text_lower'].map(mapping_dict)
            df.drop(columns=['entity_text_lower'], inplace=True)

        if property:
            canonical_values = self.get_all_synonyms_for_key(property=True, main_key=canonical_name)
            mention_to_property = self.map_mentions(mention_list, canonical_values, threshold=threshold)
            if not mention_to_property:
                print(f"⚠️ No property-Mappings for '{canonical_name}' found.")
                return df
            
            df.loc[:, "property_mapping"] = df["property"].map(mention_to_property)
            df = df[df["property_mapping"].notna()].copy()  # copy() hier!

            mapping_dict = self.build_mention_to_canonical_mapping(property=True, main_key=canonical_name)
            df.loc[:, 'property_text_lower'] = df['property_mapping'].str.lower()
            df.loc[:, 'property_mapping'] = df['property_text_lower'].map(mapping_dict)
            df.drop(columns=['property_text_lower'], inplace=True)

        return df
    

    # ----------------------------------- Functions for Helping the Layout -----------------------------------------------------------

    def print_df_sizes(self, df: pd.DataFrame):
        """
        Function to print the size of the Number Of Statements, Entities and Properties.

        Args:
            df (pd.DataFrame): The DataFrame for which to print the sizes.
        """

        print("Total Statements:", len(df))
        print("Number of Entities:", len(df["entity"].value_counts()))
        print("Number of Properties:", len(df["property"].value_counts()))