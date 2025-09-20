from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import hashlib
import pickle
import spacy
import re
import os

try:
    NLP = spacy.load('en_core_web_sm')
    print("Search Engine: spaCy model 'en_core_web_sm' loaded successfully.")
except OSError:
    print("Search Engine: Could not load 'en_core_web_sm'. Preprocessing will be basic.")
    NLP = None


def preprocess_text_content(text):
    """Processes raw text content for search queries."""
    if NLP is None or not text: return text if text else ""
    doc = NLP(text.lower())
    return " ".join([token.lemma_ for token in doc if not token.is_stop and not token.is_punct and not token.is_space])


def preprocess_filepath(filepath):
    """Processes a file for the vectorizer by reading its content."""
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    return preprocess_text_content(content)


class VectorSearchEngine:
    def __init__(self, cache_path="vector_index.pkl"):
        self.cache_path = cache_path
        self.vectorizer = TfidfVectorizer(preprocessor=preprocess_filepath)
        self.tfidf_matrix = None
        self.idx_to_filepath = {}
        self.file_hashes = {}
        self.file_metadata = {}

    def _get_file_hash(self, filepath):
        """Calculates the SHA256 hash of a file to detect changes."""
        h = hashlib.sha256()
        try:
            with open(filepath, 'rb') as f:
                while True:
                    chunk = f.read(8192)
                    if not chunk: break
                    h.update(chunk)
            return h.hexdigest()
        except (IOError, OSError):
            return None

    def load_from_cache(self):
        """Loads the engine's state from the cache file if it exists."""
        if not os.path.exists(self.cache_path):
            print("Engine: Cache not found. Starting with a fresh index.")
            return
        try:
            with open(self.cache_path, 'rb') as f:
                state = pickle.load(f)
                self.vectorizer = state['vectorizer']
                self.tfidf_matrix = state['tfidf_matrix']
                self.idx_to_filepath = state['idx_to_filepath']
                self.file_hashes = state['file_hashes']
                self.file_metadata = state['file_metadata']
            print(f"Engine: Successfully loaded index for {len(self.file_hashes)} files from cache.")
        except Exception as e:
            print(f"Engine: Error loading from cache: {e}. A fresh index will be built.")

    def save_to_cache(self):
        """Saves the current state of the index to the cache file."""
        print(f"Engine: Saving index with {len(self.file_hashes)} files to cache...")
        state = {
            'vectorizer': self.vectorizer,
            'tfidf_matrix': self.tfidf_matrix,
            'idx_to_filepath': self.idx_to_filepath,
            'file_hashes': self.file_hashes,
            'file_metadata': self.file_metadata
        }
        try:
            with open(self.cache_path, 'wb') as f:
                pickle.dump(state, f)
            print("Engine: Cache saved successfully.")
        except Exception as e:
            print(f"Engine: Error saving cache: {e}")

    def sync_index_with_filesystem(self, root_folder):
        """
        Scans a root folder, finds changes, and rebuilds the index if necessary.
        Returns True if changes were detected, otherwise False.
        """
        print("Engine: Synchronizing index with file system...")
        changed = False
        current_files = set()

        for dirpath, _, filenames in os.walk(root_folder):
            for filename in filenames:
                if filename.endswith(".txt"):
                    filepath = os.path.join(dirpath, filename)
                    current_files.add(filepath)

                    new_hash = self._get_file_hash(filepath)
                    if not new_hash: continue

                    if filepath not in self.file_hashes or self.file_hashes[filepath] != new_hash:
                        print(f"Engine: Detected change in file: {filepath}")
                        self.file_hashes[filepath] = new_hash
                        changed = True

        deleted_files = set(self.file_hashes.keys()) - current_files
        if deleted_files:
            for filepath in deleted_files:
                print(f"Engine: Detected deletion of file: {filepath}")
                del self.file_hashes[filepath]
            changed = True

        if changed:
            print("Engine: Rebuilding entire index due to file system changes...")
            all_filepaths = sorted(list(self.file_hashes.keys()))
            if not all_filepaths:
                self.tfidf_matrix = None
                self.idx_to_filepath = {}
                self.file_metadata = {}
                print("Engine: Index is now empty.")
            else:
                self.tfidf_matrix = self.vectorizer.fit_transform(all_filepaths)
                self.idx_to_filepath = {i: path for i, path in enumerate(all_filepaths)}
                self.file_metadata = {path: os.path.basename(path) for path in all_filepaths}

            self.save_to_cache()

        print("Engine: Synchronization complete.")
        return changed

    def search(self, query, top_n=20):
        """Performs a search against the current index."""
        if self.tfidf_matrix is None or self.tfidf_matrix.shape[0] == 0:
            return []

        processed_query = preprocess_text_content(query)

        original_preprocessor = self.vectorizer.preprocessor
        self.vectorizer.preprocessor = lambda x: x

        try:
            query_vector = self.vectorizer.transform([processed_query])
        finally:
            self.vectorizer.preprocessor = original_preprocessor

        cosine_similarities = cosine_similarity(query_vector, self.tfidf_matrix).flatten()
        related_docs_indices = cosine_similarities.argsort()[:-top_n - 1:-1]

        results = []
        for i in related_docs_indices:
            score = cosine_similarities[i]
            if score > 0.01:
                filepath = self.idx_to_filepath[i]
                title = self.file_metadata.get(filepath, os.path.basename(filepath))
                try:
                    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    snippet = self._generate_snippet(content, processed_query.split())
                except Exception:
                    snippet = "[Could not read file content for snippet]"

                results.append({'title': title, 'score': score, 'snippet': snippet, 'path': filepath})
        return results

    @staticmethod
    def _generate_snippet(text, query_words, length=250):
        """Private method to generate a snippet."""
        match_pos = -1
        for word in query_words:
            match = re.search(r'\b' + re.escape(word) + r'\b', text, re.IGNORECASE)
            if match:
                match_pos = match.start()
                break

        if match_pos == -1:
            return text[:length] + "..." if len(text) > length else text

        start = max(0, match_pos - length // 2)
        end = min(len(text), match_pos + length // 2)
        snippet = text[start:end]

        if start > 0: snippet = "..." + snippet
        if end < len(text): snippet = snippet + "..."

        return snippet