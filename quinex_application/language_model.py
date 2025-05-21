from dotenv import load_dotenv
import requests
import os

class LanguageModel:
    """
    Wrapper class for interacting with the Helmholtz Blablador LLM API.
    """

    def __init__(self):
        """
        Initializes the LanguageModel instance by loading the API key from a .env file
        and setting the base URL and request headers.        
        """

        load_dotenv()
        API_KEY = os.getenv("API_KEY")
        self.BASE_URL = "https://api.helmholtz-blablador.fz-juelich.de/"
        self.headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }

    def get_models(self):
        """
        Retrieves the list of available model IDs from the API.
        """

        response = requests.get(f"{self.BASE_URL}v1/models", headers=self.headers)
        return [item["id"] for item in response.json()["data"]]
    

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
        user: str = "test-user"
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
        """

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


        response = requests.post(f"{self.BASE_URL}v1/chat/completions", headers=self.headers, json=payload)
        return response.json()["choices"][0]["message"]["content"]
        
