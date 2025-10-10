import os
import re
import math
from collections import Counter
import spacy
import ollama
import json
import hashlib

# --- Configuration ---
OLLAMA_MODEL = 'phi3'
SUMMARIES_CACHE_FILE = 'summaries_cache.json'
NLP = None


def load_spacy_model():
    """Loads the spaCy model only when needed."""
    global NLP
    if NLP is None:
        print("Summarizer: Loading spaCy model 'en_core_web_sm'...")
        try:
            NLP = spacy.load('en_core_web_sm')
            print("Summarizer: spaCy model loaded.")
        except OSError:
            print("ERROR: spaCy model 'en_core_web_sm' not found. Please download it.")
            return False
    return True


def get_text_from_file(filepath):
    """Reads a plain text file and returns its content."""
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        return f.read()


def clean_and_tokenize(text):
    """Removes punctuation, numbers, converts to lowercase, and splits into words."""
    text = text.lower()
    text = re.sub(r'[^a-z\sñáéíóúü]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text.split()


class DocumentSummarizer:
    def __init__(self, filepaths):
        if not load_spacy_model():
            raise RuntimeError("spaCy model could not be loaded.")

        self.corpus_stats = self._build_corpus_stats(filepaths)
        self.cache = self._load_cache()
        print("INFO: Corpus statistics built successfully.")

    def _load_cache(self):
        """Loads the summary cache from a JSON file."""
        if not os.path.exists(SUMMARIES_CACHE_FILE):
            print("Summarizer: Cache file not found. A new one will be created.")
            return {}
        try:
            with open(SUMMARIES_CACHE_FILE, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
                print(f"Summarizer: Cache loaded with {len(cache_data)} entries.")
                return cache_data
        except (json.JSONDecodeError, IOError):
            print(f"Summarizer: Warning - Could not read or parse cache file. Starting fresh.")
            return {}

    def _save_cache(self):
        """Saves the current state of the cache to a JSON file."""
        try:
            with open(SUMMARIES_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, indent=4)
            print("Summarizer: Cache saved successfully.")
        except IOError as e:
            print(f"Summarizer: ERROR - Could not save cache file: {e}")

    def _calculate_file_hash(self, filepath):
        """Calculates the SHA256 hash of a file to detect changes."""
        sha256_hash = hashlib.sha256()
        try:
            with open(filepath, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            return sha256_hash.hexdigest()
        except IOError:
            return None

    def _build_corpus_stats(self, filepaths):
        doc_freqs = Counter()
        total_docs = len(filepaths)
        for path in filepaths:
            try:
                text = get_text_from_file(path)
                tokens = clean_and_tokenize(text)
                doc_freqs.update(set(tokens))
            except Exception as e:
                print(f"Warning: Could not process file {path} for stats: {e}")
        return {'doc_freqs': doc_freqs, 'total_docs': total_docs}

    def _get_keyword_summary_ollama(self, text):
        prompt = f"""
        Analyze the following text and extract the top 10-15 most important keywords and key phrases.
        Present them as a simple, comma-separated list.

        Text to analyze:
        ---
        {text}
        ---
        Keywords:
        """
        try:
            response = ollama.chat(
                model=OLLAMA_MODEL,
                messages=[{'role': 'user', 'content': prompt}]
            )
            return response['message']['content']
        except Exception as e:
            return f"Error connecting to Ollama: {e}"

    def _get_classic_summary_extractive(self, text, num_sentences=10):
        all_tokens = clean_and_tokenize(text)
        if not all_tokens: return "Document is empty or contains no processable words."

        tf = Counter(all_tokens)
        tf_max = max(tf.values())
        word_weights = {}

        for word, freq in tf.items():
            df_t = self.corpus_stats['doc_freqs'].get(word, 1)
            total_docs = self.corpus_stats['total_docs']
            if total_docs == 0 or df_t == 0: continue

            w_td = 0.5 * (1 + freq / tf_max) * math.log(total_docs / df_t)
            word_weights[word] = w_td

        doc = NLP(text)
        sentences = list(doc.sents)
        if not sentences: return "Could not split text into sentences."

        sentence_weights = []
        total_doc_chars = len(text)
        chars_before_sent = 0

        for i, sent in enumerate(sentences):
            sent_text = sent.text
            sent_tokens = clean_and_tokenize(sent_text)
            score_si = sum(word_weights.get(token, 0) for token in sent_tokens)
            posd_si = 1 - (chars_before_sent / total_doc_chars) if total_doc_chars > 0 else 0
            posp_si = 1 - (i / len(sentences))

            final_weight = score_si * posd_si * posp_si
            sentence_weights.append((final_weight, i, sent_text))
            chars_before_sent += len(sent_text)

        sentence_weights.sort(key=lambda x: x[0], reverse=True)
        top_sentences = sentence_weights[:num_sentences]
        top_sentences.sort(key=lambda x: x[1])

        return " ".join([sent[2].strip() for sent in top_sentences])

    def create_summaries(self, filepath):
        """
        Creates both classic and keyword summaries for a given file,
        using a cache to avoid re-generating if the file hasn't changed.
        """
        print(f"Summarizer: Processing file '{os.path.basename(filepath)}'...")

        current_hash = self._calculate_file_hash(filepath)
        if not current_hash:
            return {'keywords': "Error: Could not read file to generate hash.",
                    'classic': "Error: Could not read file to generate hash."}

        if filepath in self.cache and self.cache[filepath].get('hash') == current_hash:
            print("  -> Cache HIT. Returning stored summaries.")
            return {
                'keywords': self.cache[filepath]['keyword_summary'],
                'classic': self.cache[filepath]['classic_summary']
            }

        print("  -> Cache MISS or file changed. Generating new summaries...")
        try:
            full_text = get_text_from_file(filepath)

            keyword_summary = self._get_keyword_summary_ollama(full_text)
            classic_summary = self._get_classic_summary_extractive(full_text)

            self.cache[filepath] = {
                'hash': current_hash,
                'keyword_summary': keyword_summary,
                'classic_summary': classic_summary
            }
            self._save_cache()

            return {
                'keywords': keyword_summary,
                'classic': classic_summary
            }
        except Exception as e:
            error_msg = f"Failed to process file: {e}"
            return {'keywords': error_msg, 'classic': error_msg}