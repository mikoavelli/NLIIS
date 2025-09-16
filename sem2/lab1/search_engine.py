from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import spacy

# Загружаем модель spaCy один раз, чтобы использовать ее для предобработки текста.
# Это гарантирует, что запросы и документы обрабатываются одинаково.
try:
    NLP = spacy.load('en_core_web_sm')
    print("Search Engine: spaCy model 'en_core_web_sm' loaded successfully.")
except OSError:
    print("Search Engine: Could not load 'en_core_web_sm'. Preprocessing will be basic.")
    NLP = None


def preprocess_text(text):
    """
    Функция для очистки и лемматизации текста.
    Удаляет стоп-слова и знаки препинания.
    """
    if NLP is None or not text:
        return text if text else ""

    doc = NLP(text.lower())
    # Возвращаем строку из лемм для векторизатора
    return " ".join([token.lemma_ for token in doc if not token.is_stop and not token.is_punct and not token.is_space])


class VectorSearchEngine:
    """
    Класс, инкапсулирующий логику векторного поиска.
    """

    def __init__(self):
        # Инициализируем TF-IDF векторизатор, передавая ему нашу функцию предобработки
        self.vectorizer = TfidfVectorizer(preprocessor=preprocess_text)
        self.tfidf_matrix = None
        self.doc_id_map = {}  # Словарь для связи индекса строки в матрице с ID документа (file_id)

    def build_index(self, documents):
        """
        Создает TF-IDF матрицу для коллекции документов.
        'documents' - это список словарей, e.g., [{'file_id': 1, 'text': '...'}, ...]
        """
        print("Engine: Building vector search index...")
        if not documents:
            print("Engine: No documents provided to build index.")
            return

        # Сохраняем соответствие: индекс строки матрицы -> file_id
        self.doc_id_map = {i: doc['file_id'] for i, doc in enumerate(documents)}

        # Извлекаем только тексты для векторизации
        texts = [doc['text'] for doc in documents]

        # Обучаем векторизатор и строим матрицу
        self.tfidf_matrix = self.vectorizer.fit_transform(texts)
        print(f"Engine: Index built successfully. Vocabulary size: {len(self.vectorizer.get_feature_names_out())}")

    def search(self, query, top_n=20):
        """
        Выполняет поиск по индексу и возвращает N самых релевантных документов.
        """
        if self.tfidf_matrix is None:
            print("Engine: Search index has not been built yet.")
            return []

        # 1. Преобразуем поисковый запрос в TF-IDF вектор, используя тот же векторизатор
        query_vector = self.vectorizer.transform([query])

        # 2. Вычисляем косинусное сходство между вектором запроса и всеми векторами документов
        cosine_similarities = cosine_similarity(query_vector, self.tfidf_matrix).flatten()

        # 3. Находим индексы N лучших результатов
        # argsort() возвращает индексы, которые бы отсортировали массив.
        # Берем N последних индексов в обратном порядке.
        related_docs_indices = cosine_similarities.argsort()[:-top_n - 1:-1]

        # 4. Формируем результат
        results = []
        for i in related_docs_indices:
            score = cosine_similarities[i]
            # Отсекаем документы с нулевой или очень низкой релевантностью
            if score > 0.01:
                doc_id = self.doc_id_map[i]
                results.append({'file_id': doc_id, 'score': score})

        return results