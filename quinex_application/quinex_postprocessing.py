import os
import json
import pandas as pd

class QuinexPostprocessing():
    """
    Postprocesses the results observed using quinex.
    """
    
    def __init__(self):
        """
        Initializes the postprocessing client.
        """

        pd.set_option('display.max_colwidth', None)

    # ----------------------------------- Functions for Saving Analysis-----------------------------------------------------------

    def create_information_df(self, analysis, meta_df):
        """
        Transforms a Quinex analysis result into a structured pandas DataFrame.

        Args:
            analysis (list): List of analysis results (typically JSON-like dicts) per paper.
            meta_df (pd.DataFrame): DataFrame with at least columns ["DOI", "Year"].

        Returns:
            pd.DataFrame: A DataFrame with extracted quantitative statements and qualifiers.
        """

        records = []

        year_lookup = dict(zip(meta_df["DOI"], meta_df["Year"]))
        for paper in analysis:
            self.doi = paper.get("_id")
            result = paper.get("analysis_result")

            if not result:
                print(f"⚠️  No analysis result for DOI: {self.doi}")
                continue

            self.text = result["text"]
            
            self.year = year_lookup.get(self.doi)
       
            statements = result.get("annotations", {}).get("quantitative_statements", [])

            for self.stm in statements:
                record = self.parse_statement()
                if record is not False:
                    records.extend(record)
        df = pd.DataFrame(records)
        return df.convert_dtypes()

    def parse_statement(self):
        """
        Parses a single quantitative statement into one or more structured records.
        """

        records = []
        claim = self.stm.get("claim", {})
        qualifiers = self.stm.get("qualifiers", {})
        statement_classification = self.stm.get("statement_classification", {})


        entity = claim.get("entity", {}).get("text", "")
        prop = claim.get("property", {}).get("text", "")

        temporal_scope = qualifiers.get("temporal_scope", {}).get("normalized", {'year': None})
        temporal = {"year": temporal_scope.get("year", pd.NA)} if temporal_scope.get("year", pd.NA) else pd.NA

        spatial_scope = qualifiers.get("spatial_scope", {}).get("normalized", {'country': None, 'country_code': None, 'latitude': None, 'longitude': None, 'osm_place_id': None})
        spatial = {"country": spatial_scope.get("country", pd.NA), "latitude": spatial_scope.get("latitude", pd.NA), "longitude": spatial_scope.get("longitude", pd.NA)} if spatial_scope.get("latitude", pd.NA) and spatial_scope.get("longitude", pd.NA)  else pd.NA
        
        classification = {
            "type": statement_classification.get("type", {}).get("class", pd.NA),
            "rational": statement_classification.get("rational", {}).get("class", pd.NA),
            "system": statement_classification.get("system", {}).get("class", pd.NA),
        }

        quantity_modifier = [q["value"]["normalized"]["modifiers"] for q in claim.get("quantity", {}).get("normalized", {}).get("individual_quantities", {}).get("normalized", [])]
        quantity = claim.get("quantity", {}).get("text", "")
        combined_quantity = f"{", ".join(set(quantity_modifier))} {quantity}".strip()
        quantity_type = claim.get("quantity", {}).get("normalized", {}).get("type", {}).get("class", "")

        quantity_normalized = claim.get("quantity", {}).get("normalized", {}).get("individual_quantities", {}).get("normalized", [])

        if any(
            u.get("value", {}).get("normalized", {}).get("numeric_value", pd.NA) is pd.NA
            for u in quantity_normalized
        ):
            combined_quantity_list = []
        else:
            combined_quantity_list = [
                {
                    "value": u.get("value", {}).get("normalized", {}).get("numeric_value", pd.NA),
                    "unit": [
                        {"text": n.get("text"), "exponent": n.get("exponent"), "unit_uri": n.get("uri"), "year": n.get("year")}
                        for n in u.get("unit", {}).get("normalized", [])
                    ] or [{"text": pd.NA, "exponent": pd.NA,  "unit_uri": "http://qudt.org/vocab/unit/UNITLESS", "year": pd.NA}],
                    "modifier": u.get("value", {}).get("normalized", {}).get("modifiers", pd.NA)
                }
                for u in quantity_normalized
            ]

        max_safe_int = 2**53 - 1
        if any(isinstance(e["value"], int) and abs(e["value"]) > max_safe_int for e in combined_quantity_list):
            print(f"⚠️  Maxed integer number achieved for DOI: {self.doi}")
            return False

        quantity_normalized = {"type": quantity_type, "quantities": combined_quantity_list} if combined_quantity_list != [] else {"type": "literal", "quantities": []}

        numeric_values = [e["value"] for e in combined_quantity_list if isinstance(e["value"], (int, float))]
        value = pd.NA if not numeric_values else numeric_values[0] if len(numeric_values) == 1 else sum(numeric_values) / len(numeric_values)
        
        unit = (combined_quantity_list[0].get("unit") if combined_quantity_list else []) or [{"text": pd.NA, "exponent": pd.NA,  "unit_uri": "http://qudt.org/vocab/unit/UNITLESS", "year": pd.NA}]
        # unit = " / ".join(filter(None, [
        #     " * ".join(
        #         f"{u['unit_uri']}" if u.get("exponent") == 1 else f"{u['unit_uri']}^{u['exponent']}"
        #         for u in units if isinstance(u.get("exponent"), int) and u["exponent"] > 0
        #     ),
        #     " * ".join(
        #         f"{u['unit_uri']}" if abs(u.get("exponent", 0)) == 1 else f"{u['unit_uri']}^{abs(u['exponent'])}"
        #         for u in units if isinstance(u.get("exponent"), int) and u["exponent"] < 0
        #     )
        # ])) or units[0]["unit_uri"]

        text_quote = self.get_quote()

        records.append({
            "publication_year": self.year,
            "DOI": self.doi,
            "classification": classification,
            "entity": entity,
            "property": prop,
            "quantity_text": combined_quantity,
            "value_normalized": value,
            "unit_normalized": unit,
            "quantity_normalized": quantity_normalized,
            "quote": text_quote,
            "temporal_scope": temporal,
            "spatial_scope": spatial,
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
    
    def create_metadata_df(self, analysis, meta_df):
        """
        Transforms a Quinex analysis result into a structured pandas DataFrame.

        Args:
            analysis (list): List of analysis results (typically JSON-like dicts) per paper.
            meta_df (pd.DataFrame): DataFrame with at least columns ["DOI", "Year"].

        Returns:
            pd.DataFrame: A DataFrame with metadata, including journal and country.
        """
        records = []

        year_lookup = dict(zip(meta_df["DOI"], meta_df["Year"]))
        for paper in analysis:
            self.doi = paper.get("_id")
            self.year = year_lookup.get(self.doi)

            result = paper.get("analysis_result")
            if not result:
                print(f"⚠️  No analysis result for DOI: {self.doi}")
                continue

            metadata = result.get("metadata", {}).get("bibliographic", {})

            authorship = metadata.get("authorships", [])
            countries = []
            if authorship:
                for a in authorship:
                    for c in a['countries']:
                        if c not in countries:
                            countries.append(c)

            topics = metadata.get("topics", [])
            topic = []
            if topics:
                for t in topics:
                    topic_name = t.get("display_name", "")
                    topic.append(topic_name)

            concepts = metadata.get("concepts", [])
            concept = []
            if concepts:
                for c in concepts:
                    concept_name = c.get("display_name", "")
                    concept.append(concept_name)

            source = metadata.get("primary_location", {}).get("source", {}).get("display_name", "")
            host_organization = metadata.get("primary_location", {}).get("source", {}).get("host_organization_name", "")

            records.append({
                "publication_year": self.year,
                "DOI": self.doi,
                "countries": countries,
                "topics": topic,
                "concepts": concept,
                "source": source,
                "host organization": host_organization
            })

        df = pd.DataFrame(records)
        return df.convert_dtypes()

    
    def save_df(self, df, path):
        """
        Saves the DataFrame to disk using parquet format.
        If the file exists, appends the new data to the existing one.

        Args:
            df (pd.DataFrame): The DataFrame to save.
            path (str): File path for saving.
        """

        if 'quantity_normalized' in df.columns:
            mask = df['quantity_normalized'].apply(self.has_string_value)
            num_bad = mask.sum()
            if num_bad > 0:
                print(f"⚠️ Entferne {num_bad} problematische Zeilen mit String-Werten in 'quantity_normalized'.")
            df = df[~mask]

        if os.path.exists(path):
            try:
                existing_df = pd.read_parquet(path)
                existing_dois = set(existing_df['DOI'].dropna().unique())
                new_rows = df[df['DOI'].notna() & ~df['DOI'].isin(existing_dois)]

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
    

    def has_string_value(self, q):
        """
        Prüft, ob in quantity_normalized mindestens ein value ein String ist.
        """
        if not isinstance(q, dict):
            return False
        if "quantities" not in q:
            return False
        for item in q["quantities"]:
            v = item.get("value")
            if isinstance(v, str):
                return True
        return False