import os
import pandas as pd
import threading
import logging
from quinex_utils.parsers.quantity_parser import FastSymbolicQuantityParser
from quinex_utils.parsers.unit_parser import FastSymbolicUnitParser

logging.basicConfig(level=logging.WARNING)


# --- Module-level worker loop for queue-based subprocess parsing ---
def _worker_loop(in_q, out_q):
    """Runs in a subprocess: initializes parser once, then processes texts from in_q."""
    try:
        instance = QuinexPostprocessing()
        out_q.put("ready")
    except Exception as e:
        out_q.put(f"error:{e}")
        return

    while True:
        text = in_q.get()
        if text is None:  # sentinel to stop
            break
        try:
            parsed = instance.quantity_parser.parse(text)
            value, unit = instance.extract_value_and_unit(parsed)
            if value is not None:
                value = float(value)
            out_q.put((value, unit, parsed))
        except (OverflowError, ValueError, TypeError):
            out_q.put((None, None, None))
        except Exception:
            out_q.put((None, None, None))



class QuinexPostprocessing():
    """
    Postprocesses the results observed using quinex.
    """
    
    def __init__(self):
        """
        Initializes the postprocessing client.
        """

        pd.set_option('display.max_colwidth', None)
        pd.set_option('display.float_format', lambda x: f'{x:.10g}' if x != 0 else '0.0')
        self.quantity_parser = FastSymbolicQuantityParser()
        self.unit_parser = FastSymbolicUnitParser()

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

            self.text = result.get("text")
            
            self.year = year_lookup.get(self.doi)
            self.source_url = result.get("metadata", {}).get("provenance", {}).get("fulltext_source", {}).get("url", pd.NA)
       
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
        temporal = {
            "year": temporal_scope.get("year", pd.NA)
            } if temporal_scope.get("year", pd.NA) else pd.NA

        spatial_scope = qualifiers.get("spatial_scope", {}).get("normalized", {'country': None, 'country_code': None, 'latitude': None, 'longitude': None, 'osm_place_id': None})
        spatial = {
            "text": qualifiers.get("spatial_scope", {}).get("text", pd.NA),
            "country": spatial_scope.get("country", pd.NA), 
            "latitude": spatial_scope.get("latitude", pd.NA), 
            "longitude": spatial_scope.get("longitude", pd.NA)
            } if spatial_scope.get("latitude", pd.NA) and spatial_scope.get("longitude", pd.NA)  else pd.NA
        
        classification = {
            "type": statement_classification.get("type", {}).get("class", pd.NA),
            "rational": statement_classification.get("rational", {}).get("class", pd.NA),
            "system": statement_classification.get("system", {}).get("class", pd.NA),
        }

        quantity_modifier = [q["value"]["normalized"]["modifiers"] for q in claim.get("quantity", {}).get("normalized", {}).get("individual_quantities", {}).get("normalized", [])]
        quantity = claim.get("quantity", {}).get("text", "")
        combined_quantity = f'{", ".join(set(quantity_modifier))} {quantity}'.strip()
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

        ref_normalized = qualifiers.get("reference", {}).get("normalized", []) or []
        references = [
            {"title": bib.get("title") or "", "venue": bib.get("venue") or ""}
            for ref_entry in ref_normalized
            for bib in (ref_entry.get("bib_entries") or [])
            if bib is not None
        ] or None

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
            "references": references,
            "source_url": self.source_url,
        })
        return records
    
    def get_quote(self):
        if not self.text:
            return pd.NA

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

    def _extract_units_from_source(self, unit_source):
        """Extract normalized unit dicts from a single quantity source."""
        unit_normalized = []
        prefixed_unit = unit_source.get("prefixed_unit")
        if prefixed_unit and prefixed_unit.get("normalized"):
            unit_normalized.extend(
                [{"text": t[0], "exponent": t[1], "unit_uri": t[2], "year": t[3]} for t in prefixed_unit["normalized"]]
            )
        suffixed_unit = unit_source.get("suffixed_unit")
        if suffixed_unit and suffixed_unit.get("normalized"):
            unit_normalized.extend(
                [{"text": t[0], "exponent": t[1], "unit_uri": t[2], "year": t[3]} for t in suffixed_unit["normalized"]]
            )
        return unit_normalized

    def extract_value_and_unit(self, parsed):
        """Extract averaged value and unit from quantity_parser.parse output."""
        
        if not parsed or not parsed.get("normalized_quantities"):
            return None, None

        quantities = parsed["normalized_quantities"]

        if parsed["type"] in ["range", "list"] and len(quantities) >= 2:
            values = [q["value"]["normalized"]["numeric_value"] for q in quantities
                      if q["value"]["normalized"]["numeric_value"] is not None]
            avg_value = sum(values) / len(values) if values else None

            # Collect units from all quantities, ignoring UNITLESS entries
            all_units = []
            for q in quantities:
                units = self._extract_units_from_source(q)
                if units:
                    all_units.append(units)

            if not all_units:
                unit_normalized = [{"text": None, "exponent": None, "unit_uri": 'http://qudt.org/vocab/unit/UNITLESS', "year": None}]
            elif all(u == all_units[0] for u in all_units):
                # All units are identical → take as-is
                unit_normalized = all_units[0]
            else:
                # Units differ → merge all unique unit dicts
                seen = set()
                unit_normalized = []
                for units in all_units:
                    for d in units:
                        key = (d["text"], d["exponent"], d["unit_uri"], d["year"])
                        if key not in seen:
                            seen.add(key)
                            unit_normalized.append(d)
        else:
            avg_value = quantities[0]["value"]["normalized"]["numeric_value"]
            unit_normalized = self._extract_units_from_source(quantities[0])

        # Wenn keine Units gefunden wurden, UNITLESS setzen
        if not unit_normalized:
            unit_normalized = [{"text": None, "exponent": None, "unit_uri": 'http://qudt.org/vocab/unit/UNITLESS', "year": None}]

        return avg_value, unit_normalized


    def apply_quantity_parsing(self, row):
        text = row["quantity_text"]
        if not isinstance(text, str) or not text.strip():
            return pd.Series({"value_normalized_adapted": None, "unit_normalized_adapted": None})
        
        result = {"value": None, "unit": None}
        exception_occurred = False
        
        def parse_with_timeout():
            nonlocal result, exception_occurred
            try:
                parsed = self.quantity_parser.parse(text)
                value, unit = self.extract_value_and_unit(parsed)
                if value is not None:
                    value = float(value)
                result = {"value": value, "unit": unit}
            except (OverflowError, ValueError, TypeError) as e:
                exception_occurred = True
                result = {"value": None, "unit": None}
        
        # Run parse with 5 second timeout
        thread = threading.Thread(target=parse_with_timeout, daemon=True)
        thread.start()
        thread.join(timeout=5.0)
        
        if thread.is_alive():
            logging.warning(f"Parsing timeout for text: {text[:100]}...")
            result = {"value": None, "unit": None}
        
        return pd.Series({"value_normalized_adapted": result["value"], "unit_normalized_adapted": result["unit"]})

    def parse_batch_with_timeout(self, texts, timeout=5, desc="Parsing"):
        """
        Parse a list of quantity texts using a persistent worker subprocess.
        The subprocess initializes once (expensive) and processes texts via queues.
        Only on a real hang (timeout) is the worker killed and restarted.
        """
        import multiprocessing as mp
        import queue as stdlib_queue
        from tqdm.auto import tqdm

        def start_worker():
            in_q = mp.Queue()
            out_q = mp.Queue()
            p = mp.Process(target=_worker_loop, args=(in_q, out_q), daemon=True)
            p.start()
            try:
                signal = out_q.get(timeout=120)  # allow up to 2 min for init
                if isinstance(signal, str) and signal.startswith("error:"):
                    p.terminate()
                    raise RuntimeError(f"Worker init failed: {signal}")
            except stdlib_queue.Empty:
                p.terminate()
                raise RuntimeError("Worker failed to initialize within 120 seconds")
            return p, in_q, out_q

        worker, in_q, out_q = start_worker()
        results = []

        for text in tqdm(texts, desc=desc):
            if not isinstance(text, str) or not text.strip():
                results.append((None, None, None))
                continue

            in_q.put(text)
            try:
                result = out_q.get(timeout=timeout)
                results.append(result)
            except stdlib_queue.Empty:
                logging.warning("Parsing timeout for text: %s...", str(text)[:100])
                worker.terminate()
                worker.join()
                worker, in_q, out_q = start_worker()
                results.append((None, None, None))

        in_q.put(None)  # sentinel to stop worker cleanly
        worker.join(timeout=5)
        if worker.is_alive():
            worker.terminate()

        return results
    
    def apply_unit_dimension_parsing(self, df):
        """
        Adds a 'unit_dimension_adapted' column to df based on 'unit_normalized'.

        Args:
            df (pd.DataFrame): DataFrame with a 'unit_normalized' column containing
                lists of dicts with keys: text, exponent, unit_uri, year.

        Returns:
            pd.DataFrame: df with the additional 'unit_dimension_adapted' column.
        """

        def get_dimension(unit_normalized):
            import json
            if isinstance(unit_normalized, str):
                try:
                    unit_normalized = json.loads(unit_normalized)
                except (json.JSONDecodeError, ValueError):
                    return None
            if not isinstance(unit_normalized, (list, tuple)) or len(unit_normalized) == 0:
                return None
            try:
                parsed = [(d["text"], d["exponent"], d["unit_uri"], d["year"]) for d in unit_normalized]

                if len(parsed) > 1:
                    info = self.unit_parser.get_compound_unit_conversion_info(parsed)
                    return str(info[1])  # dimension_vector

                if len(parsed) == 1:
                    baseunit = parsed[0][2]
                    info = self.unit_parser.unit_dimensions_and_kinds.get(baseunit)
                    if info:
                        return str(info["dimension_vector"])
            except Exception:
                return None
            return None

        from tqdm.auto import tqdm
        tqdm.pandas(desc="Parsing unit dimensions")

        df = df.copy()
        df["unit_dimension_adapted"] = df["unit_normalized_adapted"].progress_apply(get_dimension)
        return df