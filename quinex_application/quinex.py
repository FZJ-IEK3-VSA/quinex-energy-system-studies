import requests
import os 
import re

class Quinex:
    """
    API wrapper for interacting with the Quinex bulk analysis service.
    Provides functionality to submit DOIs, PDFs, and retrieve analysis results.
    """

    def __init__(self):
        """
        Initializes the Quinex client with the base API URL.
        """ 
        self.url_base = "http://134.94.117.238:5434/api/"

    def check_status(self):
        """
        Checks if the Quinex API service is alive.
        """

        url_endpoint = "is_alive/"
        return self.get_request(url_endpoint)
    
    def send_sentences(self, text: str, skip_imprecise_quantities: bool=True):
        """
        Sends plain text to the Quinex API for inline sentence annotation.

        Args:
            text (str): The text to be analyzed.
            skip_imprecise_quantities (bool):  Whether to skip imprecise quantities.
        """

        url_endpoint = f"text/annotate?skip_imprecise_quantities={skip_imprecise_quantities}&add_curation_fields=false"
        return self.post_request(url_endpoint, json=text)
    
    def intialize_analysis(self, name: str):
        """
        Initializes a new bulk analysis session.

        Args:
            name (str): Name of the analysis session.
        """

        url_endpoint = f"bulk_analysis/{name}"
        return self.post_request(url_endpoint)

    def add_doi(self, name: str, doi: str):
        """
        Adds a paper to the bulk analysis session by its DOI.

        Args:
            name (str): Name of the analysis session.
            doi (str): DOI of the paper to add.
        """

        url_endpoint = f"bulk_analysis/{name}/papers/doi/?doi={doi}"
        return self.post_request(url_endpoint)
    
    def add_pdf(self, name: str, path: str):
        """
        Adds a paper to the analysis session by uploading a PDF file.

        Args:
            name (str): Name of the analysis session.
            path (str): Local file path to the PDF.
        """

        url_endpoint = f"bulk_analysis/{name}/papers/pdf/"
        filename = os.path.basename(path)

        files = []
        with open(path, "rb") as pdf:
            pdf_test = pdf.read() 
            files.append(('files', (filename, pdf_test, 'application/pdf')))
        
        return self.post_request(url_endpoint, files=files)
    
    def list_added_papers(self, name: str):
        """
        Lists all papers added to a specific analysis session.

        Args:
            name (str): Name of the analysis session.
        """

        url_endpoint = f"bulk_analysis/{name}/papers/"
        return self.get_request(url_endpoint)
    
    def get_paper_id_by_doi(self, name: str, target_doi: str):
        """
        Retrieves the internal Quinex ID for a paper given its DOI.

        Args:
            name (str): Name of the analysis session.
            target_doi (str): DOI of the target paper.
        """

        papers = self.list_added_papers(name)
        for paper in papers:
            try:
                doi = re.search(r"doi:([^,]+)", paper["provenance"]["metadata_source"]["url"]).group(1)
            except KeyError:
                continue
            if doi == target_doi:
                return paper["id"]
        return None
    
    def perform_analyis(self, name: str, papers_to_process: list, number_of_gpus: int=5, skip_imprecise_quantities: bool=True):
        """
        Starts the analysis process for selected paper IDs.

        Args:
            name (str): Name of the analysis session.
            papers_to_process (list): List of paper IDs to process.
            number_of_gpus (int): Number of GPUs to use for processing.
            skip_imprecise_quantities (bool): Whether to skip imprecise quantities.
        """
    
        url_endpoint = f"bulk_analysis/{name}/process?skip_imprecise_quantities={skip_imprecise_quantities}&gpu_count={number_of_gpus}"
        return self.post_request(url_endpoint, json={"paper_ids": papers_to_process})
    
    def get_analysis(self, name: str, paper_to_get: str):
        """
        Retrieves analysis results for a specific paper ID.

        Args:
            name (str): Name of the analysis session.
            paper_to_get (str): Paper ID to retrieve results for.
        """

        url_endpoint = f"bulk_analysis/{name}/papers/{paper_to_get}"
        return self.get_request(url_endpoint)
    
    def get_request(self, url_endpoint: str,):
        """
        Sends a GET request to the Quinex API.

        Args:
            url_endpoint (str): API endpoint path.
        """
        url = self.url_base + url_endpoint
        response = requests.get(url,)
        return response.json()
    
    def post_request(self, url_endpoint: str, **kwargs):
        """
        Sends a POST request to the Quinex API.

        Args:
            url_endpoint (str): API endpoint path.
            **kwargs: Additional arguments for `requests.post`.
        """

        url = self.url_base + url_endpoint
        response = requests.post(url, **kwargs)
        return response.json()
    
    def get_bibliographic_metadata(self, quinex_result):
        return quinex_result[0]['analysis_result']['metadata']['bibliographic']
    
    def get_figures(self, quinex_result):
        return quinex_result[0]['analysis_result']['figures']

    def get_tables(self, quinex_result):
        return quinex_result[0]['analysis_result']['tables']
    
    def get_bibliography(self, quinex_result):
        return quinex_result[0]['analysis_result']['bibliography']
