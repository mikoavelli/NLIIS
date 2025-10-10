import os
import re
import json
from collections import Counter
from bs4 import BeautifulSoup

# --- Configuration ---
TRAINING_DIR = 'training_corpus'
LANGUAGES = ['en', 'es']
N_VALUE = 5
PROFILE_SIZE = 300
OUTPUT_FILE = 'language_profiles.json'


def clean_text(text):
    """Removes punctuation, numbers and converts to lowercase."""

    text = text.lower()
    text = re.sub(r'[^a-z\sñáéíóúü]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def get_text_from_file(filepath):
    """Reads a file and extracts clean text, handling HTML."""

    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    if filepath.endswith('.html'):
        soup = BeautifulSoup(content, 'html.parser')
        return soup.get_text()
    return content


def generate_ngrams(text, n):
    """Generates a list of all n-grams from a text."""

    padded_text = ' ' + text + ' '
    return [padded_text[i:i + n] for i in range(len(padded_text) - n + 1)]


def create_language_profile(lang_code):
    """Creates a language profile by analyzing all training files for a given language."""

    print(f"Creating profile for language: '{lang_code}'...")
    lang_dir = os.path.join(TRAINING_DIR, lang_code)
    if not os.path.isdir(lang_dir):
        print(f"Error: Directory not found for language '{lang_code}': {lang_dir}")
        return None

    all_ngrams = Counter()

    for filename in os.listdir(lang_dir):
        filepath = os.path.join(lang_dir, filename)
        try:
            raw_text = get_text_from_file(filepath)
            cleaned_text = clean_text(raw_text)
            ngrams = generate_ngrams(cleaned_text, N_VALUE)
            all_ngrams.update(ngrams)
        except Exception as e:
            print(f"  - Could not process file {filename}: {e}")

    most_common = [item[0] for item in all_ngrams.most_common(PROFILE_SIZE)]
    print(f"  - Profile created with {len(most_common)} n-grams.")
    return most_common


def main():
    """Main function to generate and save all language profiles."""

    print("Starting language profiler...")

    master_profile = {}
    for lang in LANGUAGES:
        profile = create_language_profile(lang)
        if profile:
            master_profile[lang] = profile

    if master_profile:
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(master_profile, f, indent=4, ensure_ascii=False)
        print(f"\nSuccessfully created and saved language profiles to '{OUTPUT_FILE}'")
    else:
        print("\nNo profiles were created. Please check your training data.")


if __name__ == '__main__':
    main()
