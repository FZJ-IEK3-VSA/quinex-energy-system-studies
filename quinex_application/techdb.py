import requests

class TechDB:
    """
    API wrapper for interacting with the TechDB service.
    Provides functionality to get the TechDB hirarchy.
    """

    def __init__(self):
        """
        Initializes the Quinex client with the base API URL.
        """ 

        self.url_base = "http://134.94.117.230:8000/api/"
    
    def save_entities(self):
        """
        Save the complete number of entities as a list.
        """

        en_tech = self.get_entity_hirarchy("technology")
        list_en_tech = self.extract_labels(en_tech)

        en_mat = self.get_entity_hirarchy("material")
        list_en_mat = self.extract_labels(en_mat)

        en_proc = self.get_entity_hirarchy("process")
        list_en_proc = self.extract_labels(en_proc)

        return list_en_tech + list_en_mat + list_en_proc



    def get_entity_hirarchy(self, entity_type: str = "technology"):
        """
        Get the hirarchy for a defined entity type.

        Args:
            entity_type (str): Entity Type to choose for hirarchy: technology, material and process
        """

        url_endpoint = f"hierarchies/entities/{entity_type}/"
        return self.get_request(url_endpoint)
    
    def save_properties(self):
        """
        Save the complete number of properties as a list.
        """


        prop = self.get_property_hirarchy()
        list_prop = self.extract_labels(prop)
        return list_prop
     
    def get_property_hirarchy(self):
        """
        Get the hirarchy of the properties.
        """

        url_endpoint = "hierarchies/properties/"
        return self.get_request(url_endpoint)
    
    def extract_labels(self, node_or_dict, labels=None):
        """
        Recursively extracts all English labels ('label['en']') from a hierarchical entity structure.

        Args:
            node_or_dict (dict): A single node or a dictionary of root nodes in the hierarchy.
            labels (list, optional): A list to collect labels during recursion. Should be None or empty on the initial call.
        """

        if labels is None:
            labels = []

        # If this is a dictionary of root nodes, recurse into each of them
        if isinstance(node_or_dict, dict) and 'label' not in node_or_dict:
            for key in node_or_dict:
                self.extract_labels(node_or_dict[key], labels)
            return labels

        # Otherwise assume this is a single node
        if 'label' in node_or_dict and 'en' in node_or_dict['label']:
            labels.append(node_or_dict['label']['en'])

        if 'children' in node_or_dict:
            for child_key in node_or_dict['children']:
                self.extract_labels(node_or_dict['children'][child_key], labels)

        return labels

    def get_request(self, url_endpoint: str,):
        """
        Sends a GET request to the TechDB API.

        Args:
            url_endpoint (str): API endpoint path.
        """

        url = self.url_base + url_endpoint
        response = requests.get(url,)
        return response.json()
    
    def post_request(self, url_endpoint: str, **kwargs):
        """
        Sends a POST request to the TechDB API.

        Args:
            url_endpoint (str): API endpoint path.
            **kwargs: Additional arguments for `requests.post`.
        """

        url = self.url_base + url_endpoint
        response = requests.post(url, **kwargs)
        return response.json()