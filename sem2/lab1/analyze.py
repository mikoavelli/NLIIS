import json
import spacy
import sqlite3
from utils import POS_TAG_TRANSLATIONS, beautiful_morph, clean_token

# --- IMPORTANT: Comment this line if you want to save the db context ---
# os.remove("movies.db")


db = sqlite3.connect("movies.db")
cursor = db.cursor()

print("Loading spaCy model 'en_core_web_sm'...")
try:
    nlp = spacy.load('en_core_web_sm')
    print("Model loaded successfully.")
except OSError:
    print("\n!!! Error: Model 'en_core_web_sm' not found. !!!")
    print("Please download it by running in the terminal:")
    print("python -m spacy download en_core_web_sm")
    print("---------------------------------------------------\n")
    db.close()
    exit()

pos_tag_translations = POS_TAG_TRANSLATIONS

cursor.execute("""
               CREATE TABLE IF NOT EXISTS texts
               (
                   file_id   INTEGER PRIMARY KEY,
                   text_id   TEXT,
                   num_words TEXT,
                   genre     TEXT,
                   date      TEXT,
                   country   TEXT,
                   lang      TEXT,
                   imdb      TEXT,
                   title     TEXT,
                   text      TEXT
               )
               """)

cursor.execute("""
               CREATE TABLE IF NOT EXISTS wordforms
               (
                   wordform_id INTEGER PRIMARY KEY AUTOINCREMENT,
                   wordform    TEXT,
                   lemma       TEXT,
                   morph       TEXT,
                   pos         TEXT,
                   dep         TEXT,
                   file_id     INTEGER,
                   FOREIGN KEY (file_id) REFERENCES texts (file_id) ON DELETE CASCADE
               );
               """)

cursor.execute("CREATE INDEX IF NOT EXISTS idx_wordforms_file_id ON wordforms(file_id);")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_wordforms_wordform ON wordforms(wordform);")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_wordforms_lemma ON wordforms(lemma);")

cursor.execute("PRAGMA foreign_keys = ON;")

print("Reading sources.json...")
try:
    with open("sources.json", encoding="utf-8") as file:
        sources = json.load(file)
except FileNotFoundError:
    print("Error: File sources.json not found. Run generate.py first.")
    db.close()
    exit()
except json.JSONDecodeError:
    print("Error: Failed to decode JSON from sources.json.")
    db.close()
    exit()

print(f"Found {len(sources)} records in sources.json.")

processed_files = 0
skipped_files = 0
for source_key, source in sources.items():
    file_id = source.get("file_id")
    if file_id is None:
        print(f"Warning: Skipped record without file_id: {source.get('title', 'N/A')}")
        skipped_files += 1
        continue

    cursor.execute("SELECT 1 FROM texts WHERE file_id = ?", (file_id,))
    exists = cursor.fetchone()

    if exists:
        skipped_files += 1
        continue

    print(f"Processing text file_id {file_id}: {source.get('title', 'N/A')}")

    try:
        cursor.execute(
            "INSERT INTO texts (file_id, text_id, num_words, genre, date, country, lang, imdb, title, text) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (file_id, source.get("text_id"), source.get("#words"), source.get("genre"), source.get("date"),
             source.get("country"), source.get("lang"), source.get("imdb"), source.get("title"), source.get("text")))
    except sqlite3.IntegrityError:
        print(f"Warning: Failed to insert text with file_id {file_id}, possibly a duplicate PRIMARY KEY.")
        skipped_files += 1
        continue

    text_to_process = source.get("text", "")
    if not text_to_process:
        print(f"Warning: Empty text for file_id {file_id}. Word forms will not be added.")
        processed_files += 1
        continue

    doc = nlp(text_to_process)
    wordforms_to_insert = []
    for token in doc:
        cleaned_text = clean_token(token.text)
        if not cleaned_text or token.is_space:
            continue

        pos_tag = token.pos_
        human_readable_pos = pos_tag_translations.get(pos_tag, pos_tag)

        morph_str = beautiful_morph(token.morph.to_dict())

        wordforms_to_insert.append((
            token.text.lower(),
            token.lemma_,
            morph_str,
            human_readable_pos,
            token.dep_,
            file_id
        ))

    if wordforms_to_insert:
        cursor.executemany(
            'INSERT INTO wordforms (wordform, lemma, morph, pos, dep, file_id) VALUES (?, ?, ?, ?, ?, ?)',
            wordforms_to_insert)
    processed_files += 1

print(f"\nCompleted.")
print(f"Processed and added/updated texts: {processed_files}")
print(f"Skipped (already existed or error): {skipped_files}")
db.commit()
db.close()
print("Database saved and closed.")
