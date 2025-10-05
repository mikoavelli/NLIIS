import ollama
import time
import json
import os

OLLAMA_MODEL = 'phi3'
CACHE_FILE = 'summary_cache.json'


class SummarizationManager:
    """
    Manages generating and caching AI-powered summaries.
    """

    def __init__(self):
        self.cache = self._load_cache()
        print(f"Summarizer: Cache loaded with {len(self.cache)} entries.")

    def _load_cache(self):
        """Loads the summary cache from a JSON file."""
        if not os.path.exists(CACHE_FILE):
            return {}
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            print(f"Summarizer: Warning - Could not read or parse cache file '{CACHE_FILE}'. Starting fresh.")
            return {}

    def _save_cache(self):
        """Saves the current state of the cache to a JSON file."""
        try:
            with open(CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, indent=4)
        except IOError as e:
            print(f"Summarizer: ERROR - Could not save cache file: {e}")

    def _generate_summary_with_ollama(self, content: str) -> (str, bool):
        """Internal function to call the Ollama API."""
        if not content.strip():
            return "File is empty. No summary available.", True

        prompt = f"""
        You are an expert at summarizing texts. 
        Please provide a concise summary of the following content in 3 to 4 sentences, 
        capturing the main plot, characters, or key ideas.

        Content to summarize:
        ---
        {content}
        ---
        """

        print(f"Summarizer: Sending request to Ollama model '{OLLAMA_MODEL}'...")
        start_time = time.time()

        try:
            response = ollama.chat(
                model=OLLAMA_MODEL,
                messages=[{'role': 'user', 'content': prompt}]
            )
            summary = response['message']['content']
            end_time = time.time()
            print(f"Summarizer: Received response in {end_time - start_time:.2f} seconds.")
            return summary, True
        except Exception as e:
            print(f"Summarizer: ERROR - Could not connect to Ollama. {e}")
            error_msg = (f"Error: Could not get summary.\n\n"
                         f"Please ensure Ollama is running and the '{OLLAMA_MODEL}' model is installed.")
            return error_msg, False

    def get_summary(self, filepath: str, current_file_hash: str) -> str:
        """
        Gets a summary for a file, using a cache to avoid re-generation.

        :param filepath: The full path to the file.
        :param current_file_hash: The current SHA256 hash of the file.
        :return: A summary string.
        """
        # --- Cache Check ---
        if filepath in self.cache and self.cache[filepath].get('hash') == current_file_hash:
            print(f"Summarizer: Cache HIT for '{os.path.basename(filepath)}'.")
            return self.cache[filepath]['summary']

        print(f"Summarizer: Cache MISS for '{os.path.basename(filepath)}'. Generating new summary.")

        # --- Cache Miss or Stale: Generate a new summary ---
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except IOError as e:
            return f"Error: Could not read file '{filepath}': {e}"

        summary, success = self._generate_summary_with_ollama(content)

        # If generation was successful, update the cache
        if success and "Error:" not in summary:
            self.cache[filepath] = {
                'hash': current_file_hash,
                'summary': summary
            }
            self._save_cache()

        return summary