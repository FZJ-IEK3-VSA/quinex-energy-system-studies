from dotenv import load_dotenv

import requests
import os

class LanguageModel:
    """
    Wrapper class for interacting with the Helmholtz Blablador LLM API.
    """

    def __init__(self, old: bool = False):
        """
        Initializes the LanguageModel instance by loading the API key from a .env file
        and setting the base URL and request headers.        
        """

        load_dotenv()
        API_KEY = os.getenv("API_KEY")
        if old:
            self.BASE_URL = "http://134.94.199.27:8080/"
        else:
            self.BASE_URL = "https://api.helmholtz-blablador.fz-juelich.de/"
        self.headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }

    def get_models(self):
        """
        Retrieves the list of available model IDs from the API.
        """
        response = requests.get(f"{self.BASE_URL}v1/models", headers=self.headers, timeout=5)
        return [item["id"] for item in response.json()["data"]]

    def select_model(self, num_models: int = 1):
        """
        Select the model(s) used for chatting.
        
        Args:
            num_models (int): Number of models to return. Defaults to 1.
        
        Returns:
            str or list[str]: Single model ID if num_models=1, otherwise a list of model IDs.
        """
        try:
            available_models = self.get_models()

        except Exception:
            raise Exception("The Large Language Models from Blablador are currently not available")
        
        # Priority list of models
        priority_models = [
            "7 - Qwen3-Coder-30B-A3B-Instruct - A code model from August 2025",
            "0 - Ministral-3-14B-Instruct-2512 - The latest Ministral from Dec.2.2025",
            "2 - Qwen3 235, a great model from Alibaba with a long context size",
            "Qwen3-VL-30B-A3B-Instruct-FP8",
            "1 - Ministral 8b - the fast model",
            "alias-large",
            "1 - Llama3 405 the best general model and big context size"
        ]
        
        # Find available models in priority order
        selected_models = []
        for model in priority_models:
            if model in available_models:
                selected_models.append(model)
                if len(selected_models) >= num_models:
                    break
        
        if not selected_models:
            print(available_models)
            raise Exception("The Large Language Models from Blablador are currently not available")
        
        # Return single model if num_models=1, otherwise return list
        if num_models == 1:
            return selected_models[0]
        else:
            return selected_models
    
    # ------------------- SIMPLE CHAT FUNCTION ------------------- 

    def chat(
        self,
        message: str,
        model: str = "gpt-3.5-turbo",
        temperature: float = 0,
        top_p: float = 1.0,
        top_k: int = -1,
        max_tokens: int = 200,
        stop: list[str] | None = None,
        presence_penalty: float = 0.0,
        frequency_penalty: float = 0.0,
        user: str = "test-user",
        verbose: bool = True
    ) -> str:
        """
        Sends a message to the selected language model and retrieves its response.

        Args:
            message (str): The user input prompt.
            model (str): The model ID to use for the request.
            temperature (float): Sampling temperature (higher = more random).
            top_p (float): Nucleus sampling (0.0-1.0); consider only the top tokens with cumulative probability top_p.
            top_k (int): Top-K sampling (number of tokens to consider); -1 means disabled.
            max_tokens (int): The maximum number of tokens to generate in the response.
            stop (list[str] | None): Optional list of stop sequences.
            presence_penalty (float): Penalty for introducing new topics.
            frequency_penalty (float): Penalty for repeating tokens.
            user (str): A user identifier for tracking or rate-limiting.
            verbose (bool): Whether to print the request and response for debugging.
        """
        
        if verbose:
            print("##################################################################################################################################")
            print(message)
        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": message}
            ],
            "temperature": temperature,
            "top_p": top_p,
            "top_k": top_k,
            "n": 1,
            "max_tokens": max_tokens,
            "stop": stop,
            "stream": False,
            "presence_penalty": presence_penalty,
            "frequency_penalty": frequency_penalty,
            "user": user
        }

        try:
            response = requests.post(f"{self.BASE_URL}v1/chat/completions", headers=self.headers, json=payload)
        except Exception:
            print("Error when calling BlaBlaDor Models")
            return None

        if response.status_code == 200:
            if verbose:
                print(response.json())
                print("##################################################################################################################################")
            return response.json()["choices"][0]["message"]["content"]
        else:
            print(response)
            print("##################################################################################################################################")
            return None