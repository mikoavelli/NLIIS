import requests


class OllamaTranslator:
    """A client for interacting with the Ollama API for translation tasks."""

    def __init__(self, base_url="http://localhost:11434"):
        """Initializes the translator with the Ollama API endpoint."""
        self.base_url = f"{base_url}/api/generate"

    def translate(self, text: str, model_name: str, source_lang: str, target_lang: str) -> str:
        """
        Sends text to a specified Ollama model for translation.

        Args:
            text: The text to be translated.
            model_name: The name of the Ollama model to use.
            source_lang: The source language (e.g., "English").
            target_lang: The target language (e.g., "Russian").

        Returns:
            The translated text as a string, or an error message if the request fails.
        """
        prompt = (
            f"Translate the following text from {source_lang} to {target_lang}. "
            f"Do not provide any explanation or preamble, only the translated text. "
            f"Text to translate: \"{text}\""
        )

        payload = {
            "model": model_name,
            "prompt": prompt,
            "stream": False
        }

        try:
            response = requests.post(self.base_url, json=payload, timeout=300)
            response.raise_for_status()
            data = response.json()
            return data.get("response", "").strip()
        except requests.exceptions.RequestException as e:
            error_message = (
                f"Error connecting to Ollama: {e}\n"
                f"Please ensure Ollama is running and the model '{model_name}' is available."
            )
            print(error_message)
            return error_message
