import os
import pandas as pd
import threading
import logging
from numbers import Integral
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
        self._unavailable_full_text_markers = [
            "due to copyright restrictions, the full text of this paper is not available"
        ]

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

            openalex_about_source = result.get("metadata", {}).get("provenance", {}).get("fulltext_source", {}).get("openalex_about_source", {})
            self.oa = openalex_about_source.get("is_oa", False) if openalex_about_source else False

            self.licence_information = result.get("metadata", {}).get("provenance", {}).get("fulltext_source", {}).get("license_from_source", pd.NA)
            
            metadata = result.get("metadata") or {}
            bibliographic = metadata.get("bibliographic") or {}
            authorships = bibliographic.get("authorships") or []

            first_author = next(
                (a for a in authorships if a.get("author_position") == "first"),
                authorships[0] if authorships else None,
            )
            self.author = (
                first_author.get("author", {}).get("display_name", pd.NA)
                if first_author else pd.NA
            )

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
        full_text_length = len(self.text) if self._has_available_text(self.text) else 0


        entity = claim.get("entity", {})
        prop = claim.get("property", {})

        temporal_scope_raw = qualifiers.get("temporal_scope", {}) or {}
        temporal_scope = temporal_scope_raw.get("normalized", {'year': None})
        temporal = {
            "year": temporal_scope.get("year", pd.NA)
            } if temporal_scope.get("year", pd.NA) else pd.NA
        _, temporal_position = self._extract_text_and_position(temporal_scope_raw)

        spatial_scope_raw = qualifiers.get("spatial_scope", {}) or {}
        spatial_scope = spatial_scope_raw.get("normalized", {'country': None, 'country_code': None, 'latitude': None, 'longitude': None, 'osm_place_id': None})
        spatial = {
            "text": spatial_scope_raw.get("text", pd.NA),
            "country": spatial_scope.get("country", pd.NA), 
            "latitude": spatial_scope.get("latitude", pd.NA), 
            "longitude": spatial_scope.get("longitude", pd.NA)
            } if spatial_scope.get("latitude", pd.NA) and spatial_scope.get("longitude", pd.NA)  else pd.NA
        _, spatial_position = self._extract_text_and_position(spatial_scope_raw)

        method_raw = qualifiers.get("method", {}) or {}
        method_text, method_position = self._extract_text_and_position(method_raw)

        qualifier_raw = qualifiers.get("qualifier", {}) or {}
        qualifier_text, qualifier_position = self._extract_text_and_position(qualifier_raw)

        reference_raw = qualifiers.get("reference", {}) or {}
        reference_text, reference_position = self._extract_text_and_position(reference_raw)
        
        classification = {
            "type": statement_classification.get("type", {}).get("class", pd.NA),
            "rational": statement_classification.get("rational", {}).get("class", pd.NA),
            "system": statement_classification.get("system", {}).get("class", pd.NA),
        }

        quantity_modifier = [q["value"]["normalized"]["modifiers"] for q in claim.get("quantity", {}).get("normalized", {}).get("individual_quantities", {}).get("normalized", [])]
        quantity = claim.get("quantity", {})
        combined_quantity = f'{", ".join(set(quantity_modifier))} {quantity.get("text", "")}'.strip()
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

        quote_info = self.get_quote_info(full_text_length)
        text_quote = quote_info["quote"]

        records.append({
            "publication_year": self.year,
            "DOI": self.doi,
            "author": self.author,
            "source_url": self.source_url,
            "open_access": self.oa,
            "license_information": self.licence_information,
            "full_text_length": full_text_length,
            "classification": classification,
            "entity": entity.get("text", ""),
            "entity_position": (entity.get("start"), entity.get("end")) if not entity.get("is_implicit", True) else None,
            "property": prop.get("text", ""),
            "property_position": (prop.get("start"), prop.get("end")) if not prop.get("is_implicit", True) else None,
            "quantity_text": combined_quantity,
            "quantity_position": (quantity.get("start"), quantity.get("end")) if not quantity.get("is_implicit", True) else None,
            "value_normalized": value,
            "unit_normalized": unit,
            "quantity_normalized": quantity_normalized,
            "quote": text_quote,
            "quote_position": quote_info["quote_position"],
            "temporal_scope": temporal,
            "temporal_scope_position": temporal_position,
            "spatial_scope": spatial,
            "spatial_scope_position": spatial_position,
            "method": method_text,
            "method_position": method_position,
            "qualifier": qualifier_text,
            "qualifier_position": qualifier_position,
            "reference": reference_text,
            "reference_position": reference_position,
        })
        return records
    
    def get_quote(self):
        return self.get_quote_info().get("quote", pd.NA)

    def _has_available_text(self, text):
        """Return True if a usable full text is present (not empty and not copyright placeholder)."""
        if not isinstance(text, str):
            return False

        text_norm = text.strip()
        if not text_norm:
            return False

        lowered = text_norm.lower()
        return not any(marker in lowered for marker in self._unavailable_full_text_markers)

    def get_quote_info(self, full_text_length=None):
        if not self._has_available_text(self.text):
            return {
                "quote": pd.NA,
                "quote_position": None,
            }

        if full_text_length is None:
            full_text_length = len(self.text)

        entity = self.stm.get("claim", {}).get("entity", {})
        prop = self.stm.get("claim", {}).get("property", {})
        quantity = self.stm.get("claim", {}).get("quantity", {})

        entity_char_offsets = [] if entity.get("is_implicit", True) else [entity.get("start"), entity.get("end")]
        property_char_offsets = [] if prop.get("is_implicit", True) else [prop.get("start"), prop.get("end")]
        quantity_char_offsets = [] if quantity.get("is_implicit", False) else [quantity.get("start"), quantity.get("end")]

        offsets = [o for o in (entity_char_offsets + property_char_offsets + quantity_char_offsets) if isinstance(o, Integral)]
        if not offsets:
            return {
                "quote": pd.NA,
                "quote_position": None,
            }
        
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

        quote_position = self._to_position_tuple(first_sent_start_before_ann, first_sent_end_after_ann)

        text_quote = (
            self.text[first_sent_start_before_ann:first_sent_end_after_ann].removeprefix(".").strip()
        )
        return {
            "quote": text_quote,
            "quote_position": quote_position,
        }

    def _to_position_tuple(self, start, end):
        """Build a normalized (start, end) tuple or None if invalid/missing."""
        if isinstance(start, Integral) and isinstance(end, Integral) and start >= 0 and end >= start:
            return (int(start), int(end))
        return None

    def _extract_text_and_position(self, annotation):
        """Extract annotation text and a single position tuple."""
        if not isinstance(annotation, dict):
            return pd.NA, None

        text = annotation.get("text", pd.NA)
        is_implicit = annotation.get("is_implicit", False)
        if is_implicit:
            return text, None

        return text, self._to_position_tuple(annotation.get("start"), annotation.get("end"))

    def _interval_union_length(self, intervals):
        """Compute total covered length for possibly overlapping [start, end) intervals."""
        if not intervals:
            return 0

        sorted_intervals = sorted(intervals, key=lambda x: x[0])
        total = 0
        cur_start, cur_end = sorted_intervals[0]

        for start, end in sorted_intervals[1:]:
            if start <= cur_end:
                cur_end = max(cur_end, end)
            else:
                total += (cur_end - cur_start)
                cur_start, cur_end = start, end

        total += (cur_end - cur_start)
        return total

    def _merge_intervals(self, intervals):
        """Merge overlapping [start, end) intervals (adjacent intervals stay separate)."""
        if not intervals:
            return []

        intervals = sorted(intervals, key=lambda x: x[0])
        merged = [intervals[0]]
        for start, end in intervals[1:]:
            last_start, last_end = merged[-1]
            if start < last_end:
                merged[-1] = (last_start, max(last_end, end))
            else:
                merged.append((start, end))
        return merged

    def _collect_row_positions(self, row):
        """Collect valid positions from one row based on *_position columns."""
        position_columns = [
            "entity_position",
            "property_position",
            "quantity_position",
            "quote_position",
            "spatial_scope_position",
            "temporal_scope_position",
            "method_position",
            "qualifier_position",
            "reference_position",
        ]

        def _normalize_position(value):
            """Normalize many persisted representations to a (start, end) tuple or None."""
            if value is None or value is pd.NA:
                return None

            # Handle pandas/numpy missing values safely.
            try:
                if pd.isna(value):
                    return None
            except Exception:
                pass

            # Strings like "[10, 20]" or "(10, 20)" from parquet/object serialization.
            if isinstance(value, str):
                try:
                    import ast
                    value = ast.literal_eval(value)
                except (ValueError, SyntaxError):
                    return None

            # Numpy arrays are common after parquet roundtrips.
            if hasattr(value, "tolist") and not isinstance(value, (tuple, list)):
                try:
                    value = value.tolist()
                except Exception:
                    return None

            if not isinstance(value, (tuple, list)) or len(value) != 2:
                return None

            start, end = value[0], value[1]
            if isinstance(start, str):
                start = start.strip()
                if start == "":
                    return None
                try:
                    start = int(float(start))
                except ValueError:
                    return None
            if isinstance(end, str):
                end = end.strip()
                if end == "":
                    return None
                try:
                    end = int(float(end))
                except ValueError:
                    return None

            if isinstance(start, Integral) and isinstance(end, Integral) and start >= 0 and end >= start:
                return (int(start), int(end))
            return None

        intervals = []
        for col in position_columns:
            if col not in row.index:
                continue
            position = _normalize_position(row[col])
            if position is not None:
                intervals.append(position)

        return intervals

    def summarize_text_coverage(self, df):
        """
        Summarize DOI-level text coverage using position tuple columns.

        For each DOI, all position ranges from all claims are collected,
        overlapping intervals are merged, and covered characters are counted once.

        Args:
            df (pd.DataFrame): Output from create_information_df.

        Returns:
            pd.DataFrame: per DOI coverage with columns
                [DOI, claim_count, full_text_length, covered_char_count, covered_text_pct].
        """
        if df is None or df.empty:
            return pd.DataFrame(columns=["DOI", "claim_count", "full_text_length", "covered_char_count", "covered_text_pct"])

        per_doi_records = []
        for doi, group in df.groupby("DOI", dropna=False):
            claim_count = int(len(group))
            text_lengths = group["full_text_length"].dropna() if "full_text_length" in group else pd.Series(dtype="float64")
            full_text_length = int(text_lengths.iloc[0]) if not text_lengths.empty else pd.NA

            intervals = []
            for _, row in group.iterrows():
                intervals.extend(self._collect_row_positions(row))

            merged = self._merge_intervals(intervals)
            covered_char_count = self._interval_union_length(merged)
            covered_text_pct = 0
            if isinstance(full_text_length, Integral) and full_text_length > 0:
                covered_char_count = min(covered_char_count, full_text_length)
                covered_text_pct = (covered_char_count / full_text_length) * 100

            per_doi_records.append({
                "DOI": doi,
                "claim_count": claim_count,
                "full_text_length": full_text_length,
                "covered_char_count": covered_char_count,
                "covered_text_pct": covered_text_pct,
            })

        per_doi_df = pd.DataFrame(per_doi_records)
        return per_doi_df.convert_dtypes()
    
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
            df = df.copy()
            df['quantity_normalized'] = df['quantity_normalized'].apply(self.coerce_quantity_values)
            mask = df['quantity_normalized'].apply(self.has_string_value)
            num_bad = mask.sum()
            if num_bad > 0:
                print(f"⚠️ Entferne {num_bad} problematische Zeilen mit nicht-konvertierbaren String-Werten in 'quantity_normalized'.")
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
                print(f"❌ Error reading/writing parquet file: {e}")
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
        Prueft, ob in quantity_normalized mindestens ein value als
        nicht-konvertierbarer String vorliegt.
        """
        if not isinstance(q, dict):
            return False
        if "quantities" not in q:
            return False
        for item in q["quantities"]:
            if not isinstance(item, dict):
                continue
            v = item.get("value")
            if isinstance(v, str):
                _, ok = self._try_parse_numeric_string(v)
                if not ok:
                    return True
        return False

    def _try_parse_numeric_string(self, value):
        """Try to parse numeric strings like '0.282' (and decimal comma forms)."""
        if not isinstance(value, str):
            return value, False

        candidate = value.strip()
        if candidate.count(",") == 1 and "." not in candidate:
            candidate = candidate.replace(",", ".")

        parsed = pd.to_numeric(candidate, errors="coerce")
        if pd.isna(parsed):
            return value, False
        return float(parsed), True

    def coerce_quantity_values(self, q):
        """Coerce string values in quantity_normalized.quantities[*].value to float."""
        if not isinstance(q, dict):
            return q
        if "quantities" not in q or not isinstance(q["quantities"], list):
            return q

        q_new = q.copy()
        quantities_new = []
        for item in q["quantities"]:
            if not isinstance(item, dict):
                quantities_new.append(item)
                continue

            item_new = item.copy()
            v = item_new.get("value")
            if isinstance(v, str):
                parsed, ok = self._try_parse_numeric_string(v)
                if ok:
                    item_new["value"] = parsed
            quantities_new.append(item_new)

        q_new["quantities"] = quantities_new
        return q_new

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