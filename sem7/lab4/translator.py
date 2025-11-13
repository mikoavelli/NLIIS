import requests
import json
import os


class OllamaTranslator:
    """A client for interacting with the Ollama API, with support for a user-defined dictionary."""

    def __init__(self, base_url="http://localhost:11434", dictionary_path="user_dictionary.json"):
        """Initializes the translator, loading the user dictionary if it exists."""
        self.base_url = f"{base_url}/api/generate"
        self.dictionary_path = dictionary_path
        self.user_dictionary = self._load_dictionary()
        print(f"Loaded {len(self.user_dictionary)} entries from user dictionary.")

    def _load_dictionary(self) -> dict:
        """Loads the user's correction dictionary from a JSON file."""
        if os.path.exists(self.dictionary_path):
            try:
                with open(self.dictionary_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Could not load user dictionary. Error: {e}")
        return {}

    def save_correction(self, source_word: str, corrected_translation: str):
        """Saves a new or updated translation to the user dictionary and file."""
        self.user_dictionary[source_word.lower()] = corrected_translation
        try:
            with open(self.dictionary_path, 'w', encoding='utf-8') as f:
                json.dump(self.user_dictionary, f, ensure_ascii=False, indent=4)
        except IOError as e:
            print(f"Error: Could not save user dictionary to file. Error: {e}")

    def translate(self, text: str, model_name: str, source_lang: str, target_lang: str) -> str:
        """
        Translates text. First checks the user dictionary for single-word translations,
        then falls back to the Ollama API.

        Returns:
            The translated text as a string, or an error message if the request fails.
        """
        cleaned_text = text.strip().lower()
        if len(cleaned_text.split()) == 1 and cleaned_text in self.user_dictionary:
            return self.user_dictionary[cleaned_text]

        prompt = (
            f"Translate the following text from {source_lang} to {target_lang}. "
            f"Do not provide any explanation or preamble, only the translated text. "
            f"Text to translate: \"{text}\""
        )
        payload = {"model": model_name, "prompt": prompt, "stream": False}

        try:
            response = requests.post(self.base_url, json=payload, timeout=300)
            response.raise_for_status()
            data = response.json()
            return data.get("response", "").strip()
        except requests.exceptions.RequestException as e:
            error_message = f"Error connecting to Ollama: {e}"
            print(error_message)
            return error_message
