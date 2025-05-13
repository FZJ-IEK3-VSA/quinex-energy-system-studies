import os
import pandas as pd
from rdflib import Graph, RDFS, URIRef

class OEOData:
    """
    A class to process OEO (Open Energy Ontology) data from an Excel file and RDF ontology.
    """

    def __init__(self, etd_path: str, ontology_path: str, output_path: str):
        """
        Initializes the OEOProcessor with file paths.

        Args:
            etd_path (str): Path to the raw Excel input file.
            ontology_path (str): Path to the OWL ontology file.
            output_path (str): Path where the processed Excel output will be saved.
        """

        self.etd_path = etd_path
        self.ontology_path = ontology_path
        self.output_path = output_path

        self.prefix_map = {
            "OEO:": "http://openenergy-platform.org/ontology/oeo/OEO_",
            "UO:": "http://openenergy-platform.org/ontology/oeo/UO_",
            "BFO:": "http://openenergy-platform.org/ontology/oeo/BFO_",
            "IAO:": "http://openenergy-platform.org/ontology/oeo/IAO_",
            "STATO:": "http://openenergy-platform.org/ontology/oeo/STATO_",
            "OBI:": "http://openenergy-platform.org/ontology/oeo/OBI_",
            "RO:": "http://openenergy-platform.org/ontology/oeo/RO_",
        }


    def process_oeo_data(self):
        """
        Executes the processing of OEO data.
        """

        df = pd.read_excel(self.etd_path)
        # TODO: Was ist mit den htt... los?
        df = df[~df["ID"].str.startswith("htt")].copy()

        df["URI"] = df["ID"]
        for key, value in self.prefix_map.items():
            df["URI"] = df["URI"].str.replace(key, value, regex=False)

        self.g = Graph()
        self.g.parse(self.ontology_path, format="xml")

        df["Super class"] = df["URI"].apply(lambda uri: self.get_superclass_label(uri))

        os.makedirs(os.path.dirname(self.output_path), exist_ok=True)
        df.to_excel(self.output_path, index=False)
        return df

    def get_superclass_label(self, uri):
        """
        Retrieves the label of the superclass for a given URI from the RDF graph.

        Args:
            uri (str): Full URI of the class.
        """
        s = URIRef(uri)

        # Hole erstes subClassOf-Ziel
        for _, _, parent in self.g.triples((s, RDFS.subClassOf, None)):
            # Versuche Label zu finden
            for _, _, label in self.g.triples((parent, RDFS.label, None)):
                return str(label)
            # Falls kein Label, URI zurückgeben
            return str(parent)
        
        return None  # Wenn keine Superklasse gefunden
