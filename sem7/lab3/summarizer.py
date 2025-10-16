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
    global NLP
    if NLP is None:
        try:
            NLP = spacy.load('en_core_web_sm')
        except OSError:
            print("ERROR: spaCy model 'en_core_web_sm' not found.")
            return False
    return True


def get_text_from_file(filepath):
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        return f.read()


def clean_and_tokenize(text):
    text = text.lower()
    text = re.sub(r'[^a-z\sñáéíóúü]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text.split()


class DocumentSummarizer:
    def __init__(self, filepaths):
        if not load_spacy_model(): raise RuntimeError("spaCy model could not be loaded.")
        self.corpus_stats = self._build_corpus_stats(filepaths)
        self.cache = self._load_cache()
        print("Corpus statistics built successfully.")

    def _load_cache(self):
        if not os.path.exists(SUMMARIES_CACHE_FILE): return {}
        try:
            with open(SUMMARIES_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}

    def _save_cache(self):
        try:
            with open(SUMMARIES_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, indent=4)
        except IOError as e:
            print(f"Summarizer: ERROR - Could not save cache: {e}")

    def _calculate_file_hash(self, filepath):
        sha256_hash = hashlib.sha256()
        try:
            with open(filepath, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""): sha256_hash.update(byte_block)
            return sha256_hash.hexdigest()
        except IOError:
            return None

    def _build_corpus_stats(self, filepaths):
        doc_freqs = Counter()
        for path in filepaths:
            try:
                doc_freqs.update(set(clean_and_tokenize(get_text_from_file(path))))
            except Exception as e:
                print(f"Warning: Could not process {path} for stats: {e}")
        return {'doc_freqs': doc_freqs, 'total_docs': len(filepaths)}

    def _get_classic_summary_extractive(self, text, word_weights, num_sentences=10):
        doc = NLP(text)
        sentences = list(doc.sents)
        if not sentences: return "Could not split text into sentences."
        sentence_weights = []
        total_doc_chars, chars_before_sent = len(text), 0
        for i, sent in enumerate(sentences):
            sent_text = sent.text
            score_si = sum(word_weights.get(token, 0) for token in clean_and_tokenize(sent_text))
            posd_si = 1 - (chars_before_sent / total_doc_chars) if total_doc_chars > 0 else 0
            posp_si = 1 - (i / len(sentences))
            sentence_weights.append((score_si * posd_si * posp_si, i, sent_text))
            chars_before_sent += len(sent_text)
        top_sentences = sorted(sorted(sentence_weights, key=lambda x: x[0], reverse=True)[:num_sentences],
                               key=lambda x: x[1])
        return " ".join([sent[2].strip() for sent in top_sentences])

    def _get_keyword_summary_extractive(self, word_weights, num_keywords=15):
        sorted_words = sorted(word_weights.items(), key=lambda item: item[1], reverse=True)
        return ", ".join([word for word, weight in sorted_words[:num_keywords]])

    def create_algorithmic_summary(self, text):
        all_tokens = clean_and_tokenize(text)
        if not all_tokens: return {'classic': "Document is empty.", 'keywords': "Document is empty."}
        tf, tf_max, word_weights = Counter(all_tokens), max(Counter(all_tokens).values()), {}
        for word, freq in tf.items():
            df_t = self.corpus_stats['doc_freqs'].get(word, 1)
            total_docs = self.corpus_stats['total_docs']
            if total_docs == 0 or df_t == 0: continue
            word_weights[word] = 0.5 * (1 + freq / tf_max) * math.log(total_docs / df_t)
        return {'classic': self._get_classic_summary_extractive(text, word_weights),
                'keywords': self._get_keyword_summary_extractive(word_weights)}

    def _get_classic_summary_ollama(self, text):
        prompt = f"Read the following text and generate a concise, abstractive summary. The summary should be in language of the article. The summary should be a single paragraph of about 4-5 sentences, capturing the main essence of the text.\n\nText:\n---\n{text}\n---\nSummary:"
        try:
            response = ollama.chat(model=OLLAMA_MODEL, messages=[{'role': 'user', 'content': prompt}])
            return response['message']['content']
        except Exception as e:
            return f"Error connecting to Ollama: {e}"

    def _get_keyword_summary_ollama(self, text):
        prompt = f"Analyze the following text and extract the top 10-15 most important keywords and key phrases. Present them as a simple, comma-separated list.\n\nText:\n---\n{text}\n---\nKeywords:"
        try:
            response = ollama.chat(model=OLLAMA_MODEL, messages=[{'role': 'user', 'content': prompt}])
            return response['message']['content']
        except Exception as e:
            return f"Error connecting to Ollama: {e}"

    def create_ollama_summary(self, text):
        return {'classic': self._get_classic_summary_ollama(text),
                'keywords': self._get_keyword_summary_ollama(text)}

    def create_all_summaries(self, filepath):
        print(f"Summarizer: Processing file '{os.path.basename(filepath)}'...")
        current_hash = self._calculate_file_hash(filepath)
        if not current_hash: return None

        cached_item = self.cache.get(filepath)
        if (cached_item and
                cached_item.get('hash') == current_hash and
                'algorithmic' in cached_item and
                'ollama' in cached_item):
            print("  -> Cache HIT. Returning stored summaries.")
            return cached_item

        print("  -> Cache MISS or file changed/stale cache. Generating new summaries...")
        try:
            full_text = get_text_from_file(filepath)

            algorithmic_summaries = self.create_algorithmic_summary(full_text)
            ollama_summaries = self.create_ollama_summary(full_text)

            cache_entry = {
                'hash': current_hash,
                'algorithmic': algorithmic_summaries,
                'ollama': ollama_summaries
            }

            self.cache[filepath] = cache_entry
            self._save_cache()

            return cache_entry
        except Exception as e:
            print(f"ERROR: Failed to process file {filepath}: {e}")
            return None
