import pandas as pd
from rdflib import Graph, RDFS, URIRef

def process_oeo_data():
    df = pd.read_excel("data/raw/etd.xlsx")

    # TODO: Was ist mit den htt... los?
    df = df[~df["ID"].str.startswith("htt")].copy()

    prefix_map = {
        "OEO:": "http://openenergy-platform.org/ontology/oeo/OEO_",
        "UO:": "http://openenergy-platform.org/ontology/oeo/UO_",
        "BFO:": "http://openenergy-platform.org/ontology/oeo/BFO_",
        "IAO:": "http://openenergy-platform.org/ontology/oeo/IAO_",
        "STATO:": "http://openenergy-platform.org/ontology/oeo/STATO_",
        "OBI:": "http://openenergy-platform.org/ontology/oeo/OBI_",
        "RO:": "http://openenergy-platform.org/ontology/oeo/RO_",
    }

    df["URI"] = df["ID"]
    for key, value in prefix_map.items():
        df["URI"] = df["URI"].str.replace(key, value, regex=False)

    g = Graph()
    g.parse("data/raw/oeo-full.owl", format="xml")

    def get_superclass_label(uri):
        s = URIRef(uri)

        # Hole erstes subClassOf-Ziel
        for _, _, parent in g.triples((s, RDFS.subClassOf, None)):
            # Versuche Label zu finden
            for _, _, label in g.triples((parent, RDFS.label, None)):
                return str(label)
            # Falls kein Label, URI zurückgeben
            return str(parent)
        
        return None  # Wenn keine Superklasse gefunden

    df["Super class"] = df["URI"].apply(get_superclass_label)

    df.to_excel("data/processed/oeo.xlsx", index=False)
