from datetime import datetime, UTC
from typing import List, Any
from pymongo import MongoClient
from tqdm import tqdm
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

    def insert_paper(self, name: str, df_doi) -> None:
        """
        Inserts DOIs into the main collection via Quinex and logs failures.

        Args:
            name (str): Project name for Quinex context.
            df_doi (DataFrame):Pandas DataFrame containing a 'DOI' column.
        """

        attempted = len(df_doi["DOI"])
        added = already_existing = failed = 0

        for i, doi in enumerate(df_doi["DOI"], 1):
            result = self.quinex.add_doi(name, doi)
            paper_id = self.quinex.get_paper_id_by_doi(name, doi)

            if paper_id:
                result = self.collection.update_one(
                    {"_id": doi},
                    {
                        "$setOnInsert": {
                            "openalex_id": paper_id,
                            "analysis_result": None,
                            "created_at": datetime.now(UTC).isoformat()
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
                            "created_at": datetime.now(UTC).isoformat()
                        }
                    },
                    upsert=True
                )
                
                failed += 1

            sys.stdout.write(
            f"\rVerarbeitet: {i}/{attempted} | ✅ Neu: {added} | 🔁 Vorhanden: {already_existing} | ❌ Fehlgeschlagen: {failed}"
            )
            sys.stdout.flush()
        
        print()
        total = self.collection.count_documents({})
        print(f"📚 Total DOIs currently stored: {total}")

    def process_paper(self, name: str, dois: list[str]) -> None:
        """
        Performs analysis on papers with missing analysis results.

        Args:
            name (str): Project name for Quinex context.
            dois (list[str]): List of DOIs to analyze.
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
            result = self.quinex.perform_analyis(name, paper_ids)
            print(f"✅ Analysis finished: {result}")
        except Exception as e:
            print(f"❌ Error when performing quinex: {e}")

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

    def update_paper_parquet(self, collection_name, parquet_path, quinex_version, oeo_version):
        """
        Updates the paper parquet file by setting Quinex flags and versions for papers 
        whose DOIs exist in the specified collection.

        Args:
            collection_name (str): Name of the MongoDB collection containing paper info.
            parquet_path (str): File path to the parquet file to update.
            quinex_version (str): Version string to set in 'Quinex_Version' column.
            oeo_version (str): Version string to set in 'OEO_Version' column.
        """
        df = pd.read_parquet(parquet_path)
        collection = self.get_collection(collection_name)
    
        # Build DOI list and map DOI -> quinex_id (openalex_id)
        dois = [i["_id"] for i in collection]
        doi_to_quinex_id = {i["_id"]: i.get("openalex_id") for i in collection}
       
        # Filter rows to update
        mask = df['DOI'].isin(dois)

        # Update DataFrame in one vectorized step
        df.loc[mask, 'Quinex'] = True
        df.loc[mask, 'Quinex_ID'] = df.loc[mask, 'DOI'].map(doi_to_quinex_id)
        df.loc[mask, 'Quinex_Version'] = quinex_version
        df.loc[mask, 'OEO_Version'] = oeo_version

        df.to_parquet(parquet_path, index=False)

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
    
    def get_papers_from_collection(self, df, collection_name: str) -> None:
        """
        Filters a DataFrame to include only DOIs already in the given collection.

        Args:
            df (DataFrame): DataFrame with a 'DOI' column.
            collection_name (str): Name of the MongoDB collection.
        """

        dois_df = df['DOI'].dropna().unique().tolist()
        existing_docs = self.db[collection_name].find({"_id": {"$in": dois_df}}, {"_id": 1})
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