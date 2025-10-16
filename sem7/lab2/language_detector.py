import json
import os
import hashlib
import ollama
from langdetect import detect, LangDetectException
from bs4 import BeautifulSoup
from language_profiler import clean_text, generate_ngrams
from collections import Counter

PROFILE_FILE = 'language_profiles.json'
LLM_CACHE_FILE = 'llm_lang_cache.json'
LLM_CONTEXT_SIZE = 100
PROFILE_SIZE = 300
N_VALUE = 5


class LanguageDetector:
    def __init__(self):
        self.profiles = self._load_profiles()
        if not self.profiles:
            print("WARNING: Language profiles are not loaded. N-gram method will not work.")
            print("Please run 'python language_profiler.py' first.")

        self.llm_cache = self._load_llm_cache()
        print(f"LLM Detector: Cache loaded with {len(self.llm_cache)} entries.")

    def _load_profiles(self):
        if not os.path.exists(PROFILE_FILE): return None
        with open(PROFILE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _load_llm_cache(self):
        """Loads the LLM language detection cache from a JSON file."""
        if not os.path.exists(LLM_CACHE_FILE):
            return {}
        try:
            with open(LLM_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            print(f"LLM Detector: Warning - Could not read or parse cache file '{LLM_CACHE_FILE}'. Starting fresh.")
            return {}

    def _save_llm_cache(self):
        """Saves the current state of the LLM cache to a JSON file."""
        try:
            with open(LLM_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.llm_cache, f, indent=4)
        except IOError as e:
            print(f"LLM Detector: ERROR - Could not save cache file: {e}")

    def _get_file_hash(self, filepath):
        """Calculates the SHA256 hash of a file to detect changes."""
        h = hashlib.sha256()
        try:
            with open(filepath, 'rb') as f:
                while chunk := f.read(8192):
                    h.update(chunk)
            return h.hexdigest()
        except (IOError, OSError):
            return None

    def _get_text_from_html(self, filepath):
        """Reads an HTML file and returns its clean text content."""
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        soup = BeautifulSoup(content, 'html.parser')
        return soup.get_text()

    def _calculate_out_of_place_distance(self, doc_profile, lang_profile):
        """Calculates the distance metric as described in the lab document."""
        distance = 0
        lang_profile_map = {ngram: i for i, ngram in enumerate(lang_profile)}
        for i, ngram in enumerate(doc_profile):
            if ngram in lang_profile_map:
                distance += abs(i - lang_profile_map[ngram])
            else:
                distance += PROFILE_SIZE
        return distance

    def detect_by_ngram(self, filepath):
        if not self.profiles: return "Error: Profiles not loaded"
        try:
            raw_text = self._get_text_from_html(filepath)
            cleaned_text = clean_text(raw_text)
            doc_ngrams = Counter(generate_ngrams(cleaned_text, N_VALUE))
            doc_profile = [item[0] for item in doc_ngrams.most_common(PROFILE_SIZE)]
            min_distance = float('inf')
            best_lang = "unknown"
            for lang_code, lang_profile in self.profiles.items():
                dist = self._calculate_out_of_place_distance(doc_profile, lang_profile)
                if dist < min_distance:
                    min_distance = dist
                    best_lang = lang_code
            return best_lang
        except Exception as e:
            return f"Error: {e}"

    def detect_by_alphabet(self, filepath):
        try:
            raw_text = self._get_text_from_html(filepath)
            spanish_chars = {'ñ', 'á', 'é', 'í', 'ó', 'ú', 'ü'}
            text_chars = set(raw_text.lower())
            return "es" if not spanish_chars.isdisjoint(text_chars) else "en"
        except Exception as e:
            return f"Error: {e}"

    def detect_by_nn(self, filepath):
        try:
            raw_text = self._get_text_from_html(filepath)
            if len(raw_text) < 20: return "unknown (too short)"
            return detect(raw_text)
        except LangDetectException:
            return "unknown"
        except Exception as e:
            return f"Error: {e}"

    def detect_by_llm(self, filepath):
        """Detects language by asking a local LLM, with caching."""

        current_hash = self._get_file_hash(filepath)
        if not current_hash:
            return "Error: Hash"

        if filepath in self.llm_cache and self.llm_cache[filepath].get('hash') == current_hash:
            return self.llm_cache[filepath]['lang_code']

        try:
            raw_text = self._get_text_from_html(filepath)
            snippet = raw_text.strip()[:LLM_CONTEXT_SIZE]
            if len(snippet) < 20: return "unknown (too short)"

            response = ollama.chat(
                model='phi3',
                messages=[
                    {
                        'role': 'system',
                        'content': 'You are a language detection expert. Respond with ONLY the two-letter ISO 639-1 code (e.g., "en", "es").'
                    },
                    {'role': 'user', 'content': snippet},
                ],
                options={"temperature": 0.0}
            )

            lang_code = response['message']['content'].strip().lower()

            if lang_code in ['en', 'es']:
                self.llm_cache[filepath] = {
                    'hash': current_hash,
                    'lang_code': lang_code
                }
                self._save_llm_cache()
                return lang_code
            else:
                return f"unknown ({lang_code})"

        except Exception as e:
            print(f"LLM Detector ERROR: {e}")
            return "Error: Ollama"