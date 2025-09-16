import json
import spacy
import sqlite3
import os
from utils import POS_TAG_TRANSLATIONS, beautiful_morph, clean_token

# --- IMPORTANT: Comment this line if want to save db context ---
# os.remove("movies.db")


db = sqlite3.connect("movies.db")
cursor = db.cursor()

# Загрузка модели spacy
print("Загрузка модели spaCy 'en_core_web_sm'...")
try:
    nlp = spacy.load('en_core_web_sm')
    print("Модель успешно загружена.")
except OSError:
    print("\n!!! Ошибка: Модель 'en_core_web_sm' не найдена. !!!")
    print("Пожалуйста, скачайте её, выполнив в терминале:")
    print("python -m spacy download en_core_web_sm")
    print("---------------------------------------------------\n")
    db.close()
    exit()

pos_tag_translations = POS_TAG_TRANSLATIONS

cursor.execute("""
CREATE TABLE IF NOT EXISTS texts (
    file_id INTEGER PRIMARY KEY,
    text_id TEXT,
    num_words TEXT,
    genre TEXT,
    date TEXT,
    country TEXT,
    lang TEXT,
    imdb TEXT,
    title TEXT,
    text TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS wordforms (
    wordform_id INTEGER PRIMARY KEY AUTOINCREMENT,
    wordform TEXT,
    lemma TEXT,
    morph TEXT,
    pos TEXT,
    dep TEXT,
    file_id INTEGER,
    FOREIGN KEY (file_id) REFERENCES texts(file_id) ON DELETE CASCADE
);
""")

cursor.execute("CREATE INDEX IF NOT EXISTS idx_wordforms_file_id ON wordforms(file_id);")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_wordforms_wordform ON wordforms(wordform);")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_wordforms_lemma ON wordforms(lemma);")

cursor.execute("PRAGMA foreign_keys = ON;")


print("Чтение sources.json...")
try:
    with open("sources.json", encoding="utf-8") as file:
        sources = json.load(file)
except FileNotFoundError:
    print("Ошибка: Файл sources.json не найден. Запустите generate.py сначала.")
    db.close()
    exit()
except json.JSONDecodeError:
    print("Ошибка: Не удалось декодировать JSON из файла sources.json.")
    db.close()
    exit()

print(f"Найдено {len(sources)} записей в sources.json.")

processed_files = 0
skipped_files = 0
for source_key, source in sources.items():
    file_id = source.get("file_id")
    if file_id is None:
        print(f"Предупреждение: Пропущена запись без file_id: {source.get('title', 'N/A')}")
        skipped_files += 1
        continue

    cursor.execute("SELECT 1 FROM texts WHERE file_id = ?", (file_id,))
    exists = cursor.fetchone()

    if exists:
        skipped_files += 1
        continue

    print(f"Обработка текста file_id {file_id}: {source.get('title', 'N/A')}")

    try:
        cursor.execute("INSERT INTO texts (file_id, text_id, num_words, genre, date, country, lang, imdb, title, text) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                       (file_id, source.get("text_id"), source.get("#words"), source.get("genre"), source.get("date"), source.get("country"), source.get("lang"), source.get("imdb"), source.get("title"), source.get("text")))
    except sqlite3.IntegrityError:
         print(f"Предупреждение: Не удалось вставить текст с file_id {file_id}, возможно дубликат PRIMARY KEY.")
         skipped_files += 1
         continue

    text_to_process = source.get("text", "")
    if not text_to_process:
        print(f"Предупреждение: Пустой текст для file_id {file_id}. Словоформы не будут добавлены.")
        # Текст уже вставлен, просто пропускаем анализ
        processed_files += 1 # Считаем его обработанным (вставленным)
        continue

    # Обработка текста с помощью spacy
    doc = nlp(text_to_process)
    wordforms_to_insert = []
    for token in doc:
        cleaned_text = clean_token(token.text) # Используем функцию очистки
        if not cleaned_text or token.is_space:
            continue

        pos_tag = token.pos_
        human_readable_pos = pos_tag_translations.get(pos_tag, pos_tag) # Используем из utils

        # Используем beautiful_morph из utils
        morph_str = beautiful_morph(token.morph.to_dict())

        wordforms_to_insert.append((
            token.text.lower(), # Сохраняем в нижнем регистре для поиска
            token.lemma_,
            morph_str,
            human_readable_pos,
            token.dep_,
            file_id # Используем file_id, который точно есть
        ))

    # Вставка словоформ пакетом для производительности
    if wordforms_to_insert:
        cursor.executemany('INSERT INTO wordforms (wordform, lemma, morph, pos, dep, file_id) VALUES (?, ?, ?, ?, ?, ?)',
                           wordforms_to_insert)
    processed_files += 1


print(f"\nЗавершено.")
print(f"Обработано и добавлено/обновлено текстов: {processed_files}")
print(f"Пропущено (уже существовали или ошибка): {skipped_files}")
db.commit()
db.close()
print("База данных сохранена и закрыта.")
