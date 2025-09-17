from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import spacy
import re
import pickle
import os

try:
    NLP = spacy.load('en_core_web_sm')
    print("Search Engine: spaCy model 'en_core_web_sm' loaded successfully.")
except OSError:
    print("Search Engine: Could not load 'en_core_web_sm'. Preprocessing will be basic.")
    NLP = None


def preprocess_text(text):
    """
    Function to clean and lemmatize text.
    Removes stop words and punctuation.
    """
    if NLP is None or not text:
        return text if text else ""

    doc = NLP(text.lower())
    # Return a string of lemmas for the vectorizer
    return " ".join([token.lemma_ for token in doc if not token.is_stop and not token.is_punct and not token.is_space])


class VectorSearchEngine:
    """
    Class that encapsulates the vector search logic.
    """

    def __init__(self):
        self.vectorizer = TfidfVectorizer(preprocessor=preprocess_text)
        self.tfidf_matrix = None
        self.doc_id_map = {}  # Dictionary to map matrix row index to document ID (file_id)
        self.raw_documents = {}  # Store original texts for snippet generation

    def build_index(self, documents):
        """
        Builds the TF-IDF matrix for a collection of documents.
        'documents' is a list of dicts, e.g., [{'file_id': 1, 'text': '...'}, ...]
        """
        print("Engine: Building vector search index...")
        if not documents:
            print("Engine: No documents provided to build index.")
            return

        self.doc_id_map = {i: doc['file_id'] for i, doc in enumerate(documents)}
        self.raw_documents = {doc['file_id']: doc['text'] for doc in documents}

        texts = [doc['text'] for doc in documents]
        self.tfidf_matrix = self.vectorizer.fit_transform(texts)
        print(f"Engine: Index built successfully. Vocabulary size: {len(self.vectorizer.get_feature_names_out())}")

    @staticmethod
    def _generate_snippet(text, query_words, length=250):
        """Private method to generate a snippet."""
        match_pos = -1
        # Search for lemmatized query words in the text
        for word in query_words:
            match = re.search(r'\b' + re.escape(word) + r'\b', text, re.IGNORECASE)
            if match:
                match_pos = match.start()
                break

        if match_pos == -1:
            # If no word is found, just take the beginning of the text
            return text[:length] + "..." if len(text) > length else text

        # Cut out a fragment of text around the found word
        start = max(0, match_pos - length // 2)
        end = min(len(text), match_pos + length // 2)
        snippet = text[start:end]

        # Add ellipses if the text was trimmed
        if start > 0: snippet = "..." + snippet
        if end < len(text): snippet = snippet + "..."

        return snippet

    def search(self, query, top_n=20):
        if self.tfidf_matrix is None:
            return []

        processed_query_words = preprocess_text(query).split()
        query_vector = self.vectorizer.transform([query])
        cosine_similarities = cosine_similarity(query_vector, self.tfidf_matrix).flatten()
        related_docs_indices = cosine_similarities.argsort()[:-top_n - 1:-1]

        results = []
        for i in related_docs_indices:
            score = cosine_similarities[i]
            if score > 0.01:
                doc_id = self.doc_id_map[i]
                original_text = self.raw_documents.get(doc_id, "")
                snippet = self._generate_snippet(original_text, processed_query_words)
                results.append({'file_id': doc_id, 'score': score, 'snippet': snippet})

        return results

    def save_index(self, path):
        """Saves the engine's state to a file using pickle."""
        print(f"Engine: Saving index to {path}...")
        try:
            with open(path, 'wb') as f:
                pickle.dump({
                    'vectorizer': self.vectorizer,
                    'tfidf_matrix': self.tfidf_matrix,
                    'doc_id_map': self.doc_id_map,
                    'raw_documents': self.raw_documents
                }, f)
            print("Engine: Index saved successfully.")
        except Exception as e:
            print(f"Engine: Error saving index: {e}")

    def load_index(self, path):
        """Loads the engine's state from a file."""
        if not os.path.exists(path):
            return False

        print(f"Engine: Attempting to load index from {path}...")
        try:
            with open(path, 'rb') as f:
                data = pickle.load(f)
                self.vectorizer = data['vectorizer']
                self.tfidf_matrix = data['tfidf_matrix']
                self.doc_id_map = data['doc_id_map']
                self.raw_documents = data['raw_documents']
            print("Engine: Index loaded successfully from cache.")
            return True
        except Exception as e:
            print(f"Engine: Error loading index from cache: {e}. Index will be rebuilt.")
            return False
