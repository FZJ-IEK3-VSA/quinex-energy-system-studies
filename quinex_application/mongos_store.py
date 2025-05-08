from datetime import datetime, UTC
from pymongo import MongoClient

import sys

class MongoStore:
    def __init__(self, quinex, database_name, collection_name):
        self.quinex = quinex

        client = MongoClient("mongodb://localhost:27017/")
        self.db = client[database_name]
        self.collection = self.db[collection_name]
        self.failed_collection = self.db["failed_papers"]

    def insert_paper(self, df_doi, name):
        attempted = len(df_doi["DOI"])
        added = 0 
        already_existing = 0
        failed = 0

        for i, doi in enumerate(df_doi["DOI"], 1):
            result = self.quinex.add_doi(name, doi)
            paper_id = self.quinex.get_paper_id_by_doi(name, doi)

            if paper_id:
                # Erfolgreich: in 'papers' speichern
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
                # Fehlgeschlagen: in 'failed_papers' speichern
                result = self.failed_collection.update_one(
                    {"_id": doi},
                    {
                        "$setOnInsert": {
                            "created_at": datetime.now(UTC).isoformat()
                        }
                    },
                    upsert=True
                )
                if result.upserted_id:
                    failed += 1
                else:
                    failed += 1

            sys.stdout.write(
            f"\rVerarbeitet: {i}/{attempted} | ✅ Neu: {added} | 🔁 Vorhanden: {already_existing} | ❌ Fehlgeschlagen: {failed}"
            )
            sys.stdout.flush()
        
        print()
        # Optional: aktueller Gesamtstand in der Datenbank
        total = self.collection.count_documents({})
        print(f"📚 Total DOIs currently stored: {total}")

    def process_paper(self, name: str, dois: list[str]):
        # Nur DOIs auswählen, bei denen noch keine Analyse durchgeführt wurde
        papers_to_analyze = list(self.collection.find(
            {
                "_id": {"$in": dois},
                "analysis_result": None
            },
            {"_id": 1, "openalex_id": 1}
        ))

        if not papers_to_analyze:
            print("No new entries for analysis.")
            return
        
        paper_ids = [p["openalex_id"] for p in papers_to_analyze]
        print(paper_ids)
        
        try:
            result = self.quinex.perform_analyis(name, paper_ids)
            print(result)
        except Exception as e:
            print(f"Error when performing quinex: {e}")

        total = len(papers_to_analyze)
        saved = 0

        for paper in papers_to_analyze:
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
                    print(f"No analysis for {doi}")
            except Exception as e:
                 print(f"Error in Analysis for {doi}: {e}")

        print("\n📊 Analysis of quinex :")
        print(f"\n📊 Successfully processed: {saved} of {total} DOIs")

    def reset_quinex_result(self, dois: list[str]):
        result = self.collection.update_many(
            {"_id": {"$in": dois}},
            {"$set": {"analysis_result": None}}
        )
        print(f"🔄 Zurückgesetzt: {result.modified_count} von {len(dois)} angefragten DOIs.")
    
    def get_collection(self, collection_name):
        doc = []
        for i in self.db[collection_name].find():
            doc.append(i)
        return doc


    def delete_collection(self, collection_name):
        self.db[collection_name].drop()

    