from datetime import datetime, timezone
from typing import List, Any
from pymongo import MongoClient
import pandas as pd
import sys

class MongoStore:
    """
    Handles storage and retrieval of paper data and analysis results
    using MongoDB and an external Quinex API.
    """

    def __init__(self, quinex, database_name: str, collection_name: str):
        """
        Initializes the MongoStore with Quinex software and MongoDB collections.

        Args:
            quinex: The Quenix client used for performing analysis
            database_name (str): Name of the MongoDB database.
            collection_name (str): Name of the main collection to store papers.
        """

        self.quinex = quinex
        client = MongoClient("mongodb://localhost:27017/")
        self.db = client[database_name]
        self.collection = self.db[collection_name]
        self.failed_collection = self.db["failed_papers"]


    def insert_paper(self, name: str, df_doi: pd.DataFrame, take_abstract: bool = False, force_redownload: bool = False, only_open_access: bool = True) -> None:
        """
        Inserts DOIs into the main collection via Quinex and logs failures.

        Args:
            name (str): Project name for Quinex context.
            df_doi (DataFrame):Pandas DataFrame containing a 'DOI' column.
            take_abstract (bool): Wether to take the abstract if the download has failed. Default is False.
            force_redownload (bool): Wether to redownload a doi if already existing.
            only_open_access (bool): Wether to only download open access paper.
        """

        attempted = len(df_doi["DOI"])
        added = already_existing = failed = 0

        for i, doi in enumerate(df_doi["DOI"], 1):
            try:
                response = self.quinex.add_doi(name, doi, take_abstract, force_redownload, only_open_access)
            except Exception as e:
                print(f"❌ Error when adding {doi}: {e}")
            
            if response.status_code == 200:
                paper_id = response.json().get('paper_id')
            
                self.failed_collection.delete_one({"_id": doi})
                result = self.collection.update_one(
                    {"_id": doi},
                    {
                        "$setOnInsert": {
                            "openalex_id": paper_id,
                            "analysis_result": None,
                            "created_at": datetime.now(timezone.utc).isoformat()
                        }
                    },
                    upsert=True
                )

                if result.upserted_id:
                    added +=1
                else: 
                    already_existing += 1

            else: 
                result = self.failed_collection.update_one(
                    {"_id": doi},
                    {
                        "$setOnInsert": {
                            "created_at": datetime.now(timezone.utc).isoformat()
                        }
                    },
                    upsert=True
                )
                
                failed += 1

            sys.stdout.write(f"\rVerarbeitet: {i}/{attempted} | ✅ Neu: {added} | 🔁 Vorhanden: {already_existing} | ❌ Fehlgeschlagen: {failed}")
            sys.stdout.flush()
        
        print()
        total = self.collection.count_documents({})
        print(f"📚 Total DOIs currently stored: {total}")


    def insert_scopus_csv(self, name: str, df: pd.DataFrame, force_overwrite: bool = False):
        """
        Adds a Scopus export directly from a pandas DataFrame to an existing bulk analysis session
        and stores successfully added papers in MongoDB.

        Args:
            name (str): Name of the analysis session.
            df (pd.DataFrame): DataFrame containing the Scopus export.
                            Must include columns: 'DOI', 'Title', 'Source title', 'Year', 'Abstract'.
            force_overwrite (bool): Wether to overwrite existing DOIs in Quinex.
        """

        required_cols = {"DOI", "Title", "Source title", "Year", "Abstract"}
        missing = required_cols - set(df.columns)
        if missing:
            raise ValueError(f"Missing required columns: {', '.join(missing)}")
        
        df = df.drop_duplicates(subset="DOI", keep="first").reset_index(drop=True)

        try:
            result = self.quinex.add_scopus_abstract(name, df, force_overwrite)
            print(f"✅ Inserting papers finished: {result}")
        except Exception as e:
            print(f"❌ Error when adding paper: {e}")

        for doi, paper_id in zip(result.get("successfully_added_papers", []), result.get("paper_ids", [])):
            # Entferne aus failed_collection, falls vorhanden
            self.failed_collection.delete_one({"_id": doi})

            self.collection.update_one(
                {"_id": doi},
                {
                    "$setOnInsert": {
                        "openalex_id": paper_id,
                        "analysis_result": None,
                        "created_at": datetime.now(timezone.utc).isoformat()
                    }
                },
                upsert=True
            )
        
        print(f"📚 Added {len(result.get('successfully_added_papers', []))}/{len(df)} papers to Mongo.")


    def process_paper(self, name: str, dois: list[str], number_of_gpus: int = 5) -> None:
        """
        Performs analysis on papers with missing analysis results.

        Args:
            name (str): Project name for Quinex context.
            dois (list[str]): List of DOIs to analyze.
            number_of_gpus (int): Number of GPUs to use for processing.
        """

        papers_to_analyze = list(self.collection.find(
            {"_id": {"$in": dois},"analysis_result": None},
            {"_id": 1, "openalex_id": 1}
        ))

        if not papers_to_analyze:
            print("No new entries for analysis.")
            return
        
        paper_ids = [p["openalex_id"] for p in papers_to_analyze]
        
        try:
            result = self.quinex.perform_analyis(name, paper_ids, number_of_gpus)
            print(f"✅ Analysis finished: {result}")
        except Exception as e:
            print(f"❌ Error when performing quinex: {e}")


    def rerun_normalizations(self, name: str, dois: list[str]) -> None:
        """
        Reruns normalizations on papers with failed normalization

        Args:
            name (str): Project name for Quinex context.
            dois (list[str]): List of DOIs to analyze.
        """

        papers_to_rerun = list(self.collection.find(
            {"_id": {"$in": dois},"analysis_result": None},
            {"_id": 1, "openalex_id": 1}
        ))
        paper_ids = [p["openalex_id"] for p in papers_to_rerun]

        try:
            result = self.quinex.rerun_normalizations(name, paper_ids)
            print(f"✅ Rerun finished: {result}")
        except Exception as e:
            print(f"❌ Error when rerunning normalizations: {e}")


    def add_analysis(self, name: str, dois: list[str]) -> None:
        """
        Fetches analysis results from Quinex and stores them in the database.

        Args:
            name (str): Project name for Quinex context.
            dois (list[str]): List of DOIs to update.
        """

        papers_to_add = list(self.collection.find(
            {"_id": {"$in": dois},"analysis_result": None},
            {"_id": 1, "openalex_id": 1}
        ))
            
        total = len(papers_to_add)
        saved = 0

        for paper in papers_to_add:
            doi = paper["_id"]
            openalex_id = paper["openalex_id"]

            try:
                response = self.quinex.get_analysis(name, openalex_id)
                if response:
                    response = self.convert_large_ints(response)
                    self.collection.update_one(
                        {"_id": doi},
                        {"$set": {"analysis_result": response}}
                    )
                    saved += 1
                else:
                    print(f"No analysis for DOI {doi}")
            except Exception as e:
                print(f"Error in Analysis for DOI {doi}: {e}")

        print(f"\n📊 Successfully processed: {saved} of {total} DOIs")


    def update_paper_parquet(self, collection_name, parquet_path, quinex_version, oeo_version, abstract = False):
        """
        Updates the paper parquet file by setting Quinex flags and versions for papers 
        whose DOIs exist in the specified collection.

        Args:
            collection_name (str): Name of the MongoDB collection containing paper info.
            parquet_path (str): File path to the parquet file to update.
            quinex_version (str): Version string to set in 'Quinex_Version' column.
            oeo_version (str): Version string to set in 'OEO_Version' column.
            abstract (str): Wether only the abstract is downloaded and processed.
        """
        df = pd.read_parquet(parquet_path)
        collection = self.get_collection(collection_name)
        failed_collection = self.get_collection("failed_papers")

        doi_to_quinex_id = {}
        doi_to_has_qs = {}
        for doc in collection:
            if not doc:
                continue
            doi = doc["_id"]
            doi_to_quinex_id[doi] = doc.get("openalex_id")

            analysis = doc.get("analysis_result")
            if analysis is None:
                doi_to_has_qs[doi] = False
            else:
                annotations = analysis.get("annotations") or {}
                qs = annotations.get("quantitative_statements")
                doi_to_has_qs[doi] = bool(qs)

        all_collection_dois = set(doi_to_quinex_id.keys())
       
        # Filter rows to update
        mask = df['DOI'].isin(all_collection_dois)

        # Update DataFrame in one vectorized step
        df.loc[mask, 'Quinex'] = df.loc[mask, 'DOI'].map(lambda doi: bool(doi_to_has_qs.get(doi)))
        df.loc[mask, 'Quinex_ID'] = df.loc[mask, 'DOI'].map(doi_to_quinex_id)
        df.loc[mask, 'Quinex_Version'] = quinex_version
        df.loc[mask, 'OEO_Version'] = oeo_version

        if abstract:
            df.loc[mask, 'Download_Status'] = "Abstract Succeeded"
        else:
            df.loc[mask, 'Download_Status'] = "Succeeded"

        failed_dois = {doc["_id"] for doc in failed_collection} - all_collection_dois
        failed_mask = df['DOI'].isin(failed_dois)
        df.loc[failed_mask, 'Download_Status'] = "Failed"
        df.loc[failed_mask, 'Quinex'] = False

        df.to_parquet(parquet_path, index=False)

        quinex_counts = df.loc[mask, 'Quinex'].value_counts()
        num_true = quinex_counts.get(True, 0)
        num_false = quinex_counts.get(False, 0)

        print(f"In Collection {collection_name} -> Quinex True: {num_true}, Quinex False: {num_false}")
        return df


    def reset_quinex_result(self, dois: list[str]) -> None:
        """
        Resets the 'analysis_result' field for the given DOIs to None.

        Args:
            dois (list[str]): List of DOIs to reset.
        """

        result = self.collection.update_many(
            {"_id": {"$in": dois}},
            {"$set": {"analysis_result": None}}
        )
        print(f"🔄 Reset: {result.modified_count} of {len(dois)} requested DOIs.")
    

    def get_papers_from_collection(self, df, collection_name: str, only_without_analysis: bool = False) -> None:
        """
        Filters a DataFrame to include only DOIs already in the given collection.

        Args:
            df (DataFrame): DataFrame with a 'DOI' column.
            collection_name (str): Name of the MongoDB collection.
            only_without_analysis (bool): If True, only include DOIs with no 'analysis_result' field.
        """

        dois_df = df['DOI'].dropna().unique().tolist()

        # MongoDB-Query aufbauen
        query = {"_id": {"$in": dois_df}}
        if only_without_analysis:
            query["analysis_result.annotations.quantitative_statements"] = {"$exists": False}

        existing_docs = self.db[collection_name].find(query, {"_id": 1})
        existing_dois = {doc["_id"] for doc in existing_docs}
        return df[df['DOI'].isin(existing_dois)]

    
    def get_collection(self, collection_name: str) -> List[dict[str, Any]]:
        """
        Retrieves all documents from a specified collection.

        Args:
            collection_name (str): Name of the MongoDB collection.
        """

        doc = []
        for entry in self.db[collection_name].find():
            doc.append(entry)
        return doc


    def delete_collection(self, collection_name: str) -> None:
        """
        Deletes the specified collection from the MongoDB database.

        Args:
            collection_name (str): Name of the MongoDB collection.
        """

        self.db[collection_name].drop()


    def convert_large_ints(self, obj, path=""):
        """
        Recursively convert integers larger than 64-bit to strings in a nested dict/list.

        Args:
            obj: dict, list, int, or other value
            path: str, used for printing the key path

        Returns:
            obj with large ints converted to strings
        """
        if isinstance(obj, dict):
            new_dict = {}
            for k, v in obj.items():
                new_path = f"{path}.{k}" if path else k
                new_dict[k] = self.convert_large_ints(v, new_path)
            return new_dict
        elif isinstance(obj, list):
            return [self.convert_large_ints(x, f"{path}[{i}]") for i, x in enumerate(obj)]
        elif isinstance(obj, int):
            if abs(obj) > 2**63 - 1:
                print(f"Converting large int at '{path}': {obj} -> str")
                return str(obj)
            return obj
        else:
            return obj
