import requests
import os 
import re

class Quenix:
    def __init__(self):
        self.url_base = "http://134.94.117.238:5434/api/"

    def check_status(self):
        url_endpoint = "is_alive/"
        return self.get_request(url_endpoint)
    
    def send_sentences(self, text, skip_imprecise_quantities=True):
        url_endpoint = f"text/annotate?skip_imprecise_quantities={skip_imprecise_quantities}&add_curation_fields=false"
        return self.post_request(url_endpoint, json=text)
    
    def intialize_analysis(self, name):
        url_endpoint = f"bulk_analysis/{name}"
        return self.post_request(url_endpoint)

    def add_doi(self, name, doi):
        url_endpoint = f"bulk_analysis/{name}/papers/doi/?doi={doi}"
        return self.post_request(url_endpoint)
    
    def add_pdf(self, name, path):
        url_endpoint = f"bulk_analysis/{name}/papers/pdf/"
        filename = os.path.basename(path)

        files = []
        with open(path, "rb") as pdf:
            pdf_test = pdf.read() 
            files.append(('files', (filename, pdf_test, 'application/pdf')))
        
        return self.post_request(url_endpoint, files=files)
    
    def list_added_papers(self, name):
        url_endpoint = f"bulk_analysis/{name}/papers/"
        return self.get_request(url_endpoint)
    
    def get_paper_id_by_doi(self, name, target_doi):
        papers = self.list_added_papers(name)
        for paper in papers:
            try:
                doi = re.search(r"doi:([^,]+)", paper["provenance"]["metadata_source"]["url"]).group(1)
            except KeyError:
                continue
            if doi == target_doi:
                return paper["id"]
        return None
    
    def perform_analyis(self, name, papers_to_process, number_of_gpus=1, skip_imprecise_quantities=True):
        url_endpoint = f"bulk_analysis/{name}/process?skip_imprecise_quantities={skip_imprecise_quantities}&gpu_count={number_of_gpus}"
        return self.post_request(url_endpoint, json={"paper_ids": papers_to_process})
    
    def get_analysis(self, name, paper_to_get):
        url_endpoint = f"bulk_analysis/{name}/papers/{paper_to_get}"
        return self.get_request(url_endpoint)
    
    def get_request(self, url_endpoint, timeout=500):
        url = self.url_base + url_endpoint
        response = requests.get(url, timeout=timeout)
        return response.json()
    
    def post_request(self, url_endpoint, timeout=500, **kwargs):
        url = self.url_base + url_endpoint
        response = requests.post(url, timeout=timeout, **kwargs)
        return response.json()
