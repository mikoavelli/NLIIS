import json
import os
from langdetect import detect, LangDetectException
from bs4 import BeautifulSoup
from language_profiler import clean_text, generate_ngrams
from collections import Counter

PROFILE_FILE = 'language_profiles.json'
PROFILE_SIZE = 300
N_VALUE = 5


class LanguageDetector:
    def __init__(self):
        self.profiles = self._load_profiles()
        if not self.profiles:
            print("WARNING: Language profiles are not loaded. N-gram method will not work.")
            print("Please run 'python language_profiler.py' first.")

    @staticmethod
    def _load_profiles():
        if not os.path.exists(PROFILE_FILE):
            return None
        with open(PROFILE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)

    @staticmethod
    def _get_text_from_html(filepath):
        """Reads an HTML file and returns its clean text content."""
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        soup = BeautifulSoup(content, 'html.parser')
        return soup.get_text()

    @staticmethod
    def _calculate_out_of_place_distance(doc_profile, lang_profile):
        """Calculates the distance metric as described in the lab document."""
        distance = 0
        lang_profile_map = {ngram: i for i, ngram in enumerate(lang_profile)}

        for i, ngram in enumerate(doc_profile):
            doc_rank = i
            if ngram in lang_profile_map:
                lang_rank = lang_profile_map[ngram]
                distance += abs(doc_rank - lang_rank)
            else:
                distance += PROFILE_SIZE

        return distance

    def detect_by_ngram(self, filepath):
        """Detects language using the N-gram Out-Of-Place distance method."""
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
        """Detects language by checking for unique characters."""
        try:
            raw_text = self._get_text_from_html(filepath)
            spanish_chars = {'ñ', 'á', 'é', 'í', 'ó', 'ú', 'ü'}

            text_chars = set(raw_text.lower())

            if not spanish_chars.isdisjoint(text_chars):
                return "es"
            else:
                return "en"
        except Exception as e:
            return f"Error: {e}"

    def detect_by_nn(self, filepath):
        """Detects language using the pre-trained 'langdetect' library."""
        try:
            raw_text = self._get_text_from_html(filepath)
            if len(raw_text) < 20: return "unknown (too short)"
            return detect(raw_text)
        except LangDetectException:
            return "unknown"
        except Exception as e:
            return f"Error: {e}"
