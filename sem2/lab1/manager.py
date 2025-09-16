import sqlite3
from dataclasses import dataclass, field
from pprint import pprint
import tkinter as tk
import os
from tkinter import ttk, messagebox, scrolledtext, Toplevel, filedialog
from idlelib.tooltip import Hovertip
import spacy
import re
from utils import POS_TAG_TRANSLATIONS, beautiful_morph, clean_token
from search_engine import VectorSearchEngine # <-- Наш новый класс
import json

NLP_MODEL = None


def load_spacy_model():
    global NLP_MODEL
    if NLP_MODEL is None:
        print("Loading spaCy model 'en_core_web_sm' for editor...")
        try:
            NLP_MODEL = spacy.load('en_core_web_sm')
            print("spaCy model loaded successfully.")
            return True
        except OSError:
            print("\n!!! ERROR: spaCy model 'en_core_web_sm' not found. !!!")
            print("Text editing with re-analysis will not work.")
            print("Please download it by running in your terminal:")
            print("python -m spacy download en_core_web_sm")
            print("---------------------------------------------------\n")
            messagebox.showerror("spaCy Model Error",
                                 "Model 'en_core_web_sm' not found.\n"
                                 "Text editing with re-analysis will not be available.\n"
                                 "Download the model: python -m spacy download en_core_web_sm")
            NLP_MODEL = False
            return False
    elif NLP_MODEL is False:
        return False
    else:
        return True


@dataclass
class SearchResult:
    wordform_id: int
    wordform: str
    lemma: str
    morph: str
    pos: str
    link: str
    examples: list[str] = field(default_factory=list)


class DBConnection:

    def __init__(self, path) -> None:
        try:
            self.db = sqlite3.connect(f"file:{path}?mode=rw", uri=True)
            self.db.row_factory = sqlite3.Row
            self.cursor = self.db.cursor()
            print(f"Successfully connected to database: {path}")
            self.cursor.execute("PRAGMA foreign_keys = ON;")
        except sqlite3.OperationalError as e:
            print(f"Database connection error for {path}: {e}")
            messagebox.showerror("Database Error",
                                 f"Could not connect to database '{path}'.\n"
                                 f"Ensure the file exists, is accessible, and analyze.py "
                                 f"has been run successfully (with ON DELETE CASCADE enabled).")
            raise  # Re-raise the exception to stop app initialization

        # --- Фрагмент manager.py (внутри класса DBConnection) ---

        def update_wordform(self, wordform_id, data):
            """
            Обновляет поля wordform, lemma, morph, pos для указанного wordform_id.
            Возвращает True, если команда выполнилась без SQL ошибки, иначе False.
            """
            # data - словарь {'wordform': ..., 'lemma': ..., 'morph': ..., 'pos': ...}
            print(f"DB: Попытка обновить wordform_id={wordform_id} данными: {data}")  # <-- Отладка
            try:
                # Выполняем SQL команду UPDATE
                self.cursor.execute("""
                    UPDATE wordforms
                    SET wordform = ?, lemma = ?, morph = ?, pos = ?
                    WHERE wordform_id = ?
                """, (data['wordform'], data['lemma'], data['morph'], data['pos'], wordform_id))

                # Получаем количество строк, которые были изменены последней командой
                updated_rows = self.cursor.rowcount
                print(f"DB: Затронуто строк при обновлении ID {wordform_id}: {updated_rows}")  # <-- Отладка

                if updated_rows == 0:
                    # Если 0 строк затронуто, значит запись с таким ID не была найдена
                    print(
                        f"DB: Предупреждение - Запись с ID {wordform_id} не найдена в таблице 'wordforms' для обновления.")
                    # Это не ошибка SQL, просто условие WHERE не выполнилось.

                # Фиксируем изменения (даже если ничего не обновилось, т.к. команда выполнилась)
                self.db.commit()
                print(f"DB: Commit выполнен для операции с ID {wordform_id}.")  # <-- Отладка

                # Сигнализируем, что SQL команда прошла успешно (даже если 0 строк обновлено)
                return True

            except sqlite3.Error as e:
                # Ловим ошибки базы данных (например, нарушение ограничений, синтаксис)
                print(f"DB: Ошибка SQLite при обновлении wordform_id {wordform_id}: {e}")  # <-- Отладка
                try:
                    self.db.rollback()  # Откатываем транзакцию в случае ошибки
                    print(f"DB: Rollback выполнен из-за ошибки для ID {wordform_id}.")  # <-- Отладка
                except Exception as rollback_e:
                    print(f"DB: Дополнительная ошибка при попытке отката транзакции: {rollback_e}")
                # Показываем ошибку пользователю
                messagebox.showerror("Database Update Error", f"Could not update wordform entry ID {wordform_id}:\n{e}")
                return False
            except KeyError as e:
                # Ловим ошибки, если в словаре 'data' не хватает нужного ключа
                print(f"DB: Отсутствует ключ '{e}' в данных для обновления ID {wordform_id}.")  # <-- Отладка
                messagebox.showerror("Data Error",
                                     f"Missing data field ('{e}') needed for updating wordform ID {wordform_id}.")
                # Откат не нужен, так как SQL команда не выполнялась
                return False
            except Exception as e:
                # Ловим любые другие непредвиденные ошибки
                print(f"DB: Неожиданная ошибка при обновлении wordform_id {wordform_id}: {e}")
                try:
                    self.db.rollback()
                    print(f"DB: Rollback выполнен из-за неожиданной ошибки для ID {wordform_id}.")
                except Exception as rollback_e:
                    print(f"DB: Дополнительная ошибка при попытке отката транзакции: {rollback_e}")
                messagebox.showerror("Unexpected Error",
                                     f"An unexpected error occurred during update for ID {wordform_id}:\n{e}")
                return False

        # --- Фрагмент manager.py (внутри класса DBConnection) ---

    def replace_wordform(self, wordform_id, data):
        """
        Обновляет поля wordform, lemma, morph, pos для указанного wordform_id,
        предварительно проверив его существование.
        Возвращает количество обновленных строк (0 или 1) в случае успеха,
        или -1 в случае ошибки SQL/данных.
        """
        print(f"DB: Попытка обновить (SELECT+UPDATE) wordform_id={wordform_id} данными: {data}")
        try:
            # Шаг 1: Проверяем, существует ли запись с таким ID
            self.cursor.execute("SELECT 1 FROM wordforms WHERE wordform_id = ?", (wordform_id,))
            exists = self.cursor.fetchone()

            if not exists:
                print(f"DB: Запись с ID {wordform_id} не существует. Обновление невозможно.")
                return 0  # Возвращаем 0, т.к. обновлять нечего

            # Шаг 2: Если существует, выполняем UPDATE
            # Транзакция начнется неявно здесь
            self.cursor.execute("""
                UPDATE wordforms
                SET wordform = ?, lemma = ?, morph = ?, pos = ?
                WHERE wordform_id = ?
            """, (data['wordform'], data['lemma'], data['morph'], data['pos'], wordform_id))

            updated_rows = self.cursor.rowcount
            print(f"DB: Затронуто строк при обновлении ID {wordform_id}: {updated_rows}")

            # Шаг 3: Фиксируем изменения неявной транзакции
            self.db.commit()
            print(f"DB: Commit выполнен для операции обновления с ID {wordform_id}.")
            return updated_rows  # Возвращаем количество обновленных строк (должно быть 1)

        except sqlite3.Error as e:
            print(f"DB: Ошибка SQLite при обновлении wordform_id {wordform_id}: {e}")
            try:
                # Откатываем неявную транзакцию, если она была начата и произошла ошибка
                self.db.rollback()
                print(f"DB: Rollback выполнен из-за ошибки для ID {wordform_id}.")
            except Exception as rollback_e:
                print(f"DB: Дополнительная ошибка при попытке отката транзакции: {rollback_e}")
            messagebox.showerror("Database Update Error", f"Could not update entry ID {wordform_id}:\n{e}")
            return -1
        except KeyError as e:
            print(f"DB: Отсутствует ключ '{e}' в данных для ID {wordform_id}.")
            messagebox.showerror("Data Error", f"Missing data field ('{e}') for ID {wordform_id}.")
            return -1  # Ошибка данных, возвращаем -1 (можно было бы и -2, но -1 достаточно)
        except Exception as e:
            print(f"DB: Неожиданная ошибка при обновлении wordform_id {wordform_id}: {e}")
            try:
                self.db.rollback()
                print(f"DB: Rollback выполнен из-за неожиданной ошибки для ID {wordform_id}.")
            except Exception as rollback_e:
                print(f"DB: Дополнительная ошибка при попытке отката транзакции: {rollback_e}")
            messagebox.showerror("Unexpected Error", f"Error during update for ID {wordform_id}:\n{e}")
            return -1

    def find_info_by_word(self, word, limit=500):
        query_word = word.lower().strip()
        if not query_word:
            return {"occurences": "0", "search_results": [], "examples": []}

        try:
            self.cursor.execute(f"""
                SELECT DISTINCT
                    wf.wordform_id, wf.wordform, wf.lemma, wf.morph, wf.pos,
                    ts.title, ts.country, ts.date, ts.file_id
                FROM wordforms wf
                JOIN texts ts ON wf.file_id = ts.file_id
                WHERE wf.wordform LIKE ? OR wf.lemma LIKE ?
                ORDER BY wf.wordform
                LIMIT ?
            """, (f'%{query_word}%', f'%{query_word}%', limit))
            results_raw = self.cursor.fetchall()

            self.cursor.execute("""
                SELECT count(*) FROM wordforms wf
                WHERE wf.wordform LIKE ? OR wf.lemma LIKE ?
            """, (f'%{query_word}%', f'%{query_word}%'))
            occurences = self.cursor.fetchone()

            examples = []
            MAX_EXAMPLES_PER_QUERY = 20
            MAX_TEXTS_TO_SCAN = 50
            self.cursor.execute("""
                SELECT DISTINCT ts.file_id
                FROM texts ts JOIN wordforms wf ON wf.file_id = ts.file_id
                WHERE wf.wordform LIKE ? OR wf.lemma LIKE ? LIMIT ?
            """, (f'%{query_word}%', f'%{query_word}%', MAX_TEXTS_TO_SCAN))
            text_ids_with_word = [row['file_id'] for row in self.cursor.fetchall()]
            if text_ids_with_word:
                placeholders = ','.join('?' * len(text_ids_with_word))
                self.cursor.execute(f"""
                    SELECT file_id, text, title, country, date, genre
                    FROM texts WHERE file_id IN ({placeholders})
                """, text_ids_with_word)
                raw_example_texts = self.cursor.fetchall()
                try:
                    pattern = re.compile(r'\b' + re.escape(query_word) + r'\b', re.IGNORECASE)
                except re.error as re_err:
                    print(f"Regex error for query '{query_word}': {re_err}")
                    pattern = None
                if pattern:
                    example_count = 0
                    for text_row in raw_example_texts:
                        if example_count >= MAX_EXAMPLES_PER_QUERY: break
                        full_text = text_row['text']
                        if not full_text: continue
                        for match in pattern.finditer(full_text):
                            start_match, end_match = match.span()
                            sentence_delimiters = ['.', '!', '?', '\n']
                            sentence_start = -1
                            for delim in sentence_delimiters: sentence_start = max(sentence_start,
                                                                                   full_text.rfind(delim, 0,
                                                                                                   start_match))
                            sentence_start += 1
                            sentence_end = len(full_text)
                            for delim in sentence_delimiters:
                                found_pos = full_text.find(delim, end_match)
                                if found_pos != -1: sentence_end = min(sentence_end, found_pos)
                            if sentence_end < len(full_text): sentence_end += 1
                            example_text = full_text[sentence_start:sentence_end].strip().replace("\n", " ")
                            if len(example_text) > 10:
                                examples.append({"text": example_text,
                                                 "link": f"{text_row['title']} ({text_row['country']}, {text_row['date']})",
                                                 "genre": text_row['genre']})
                                example_count += 1
                                if example_count >= MAX_EXAMPLES_PER_QUERY: break

            search_results_obj = [
                SearchResult(
                    r['wordform_id'],
                    r['wordform'], r['lemma'], r['morph'], r['pos'],
                    f"{r['title']} ({r['country']}, {r['date']})"
                ) for r in results_raw
            ]

            return {
                "occurences": str(occurences['count(*)'] if occurences else 0),
                "search_results": search_results_obj,
                "examples": examples
            }
        except sqlite3.Error as e:
            print(f"Database error during search for '{word}': {e}")
            messagebox.showerror("Search Error",
                                 f"A database error occurred during the search:\n{e}\n\nCheck if the database schema is up-to-date (column 'wordform_id' might be missing).")
            return {"occurences": "0", "search_results": [], "examples": []}

    def get_overall_pos_stats(self):
        try:
            self.cursor.execute("""
                SELECT pos, COUNT(*) as count
                FROM wordforms
                WHERE pos IS NOT NULL AND pos != '' AND pos != 'space' -- Exclude empty/space       
                GROUP BY pos
                ORDER BY count DESC
            """)
            return self.cursor.fetchall()
        except sqlite3.Error as e:
            print(f"Error getting overall POS stats: {e}")
            messagebox.showerror("Statistics Error", f"Could not retrieve overall statistics:\n{e}")
            return []

    def get_document_pos_stats(self, file_id):
        """Retrieves part-of-speech statistics for a specific document."""
        try:
            self.cursor.execute("""
                SELECT pos, COUNT(*) as count
                FROM wordforms
                WHERE file_id = ? AND pos IS NOT NULL AND pos != '' AND pos != 'space'
                GROUP BY pos
                ORDER BY count DESC
            """, (file_id,))
            return self.cursor.fetchall()
        except sqlite3.Error as e:
            print(f"Error getting document POS stats for file_id {file_id}: {e}")
            messagebox.showerror("Statistics Error", f"Could not retrieve statistics for the document:\n{e}")
            return []

    def get_all_texts_summary(self):
        """Retrieves a list of all text IDs and titles for dropdowns."""
        try:
            self.cursor.execute("SELECT file_id, title FROM texts ORDER BY title COLLATE NOCASE")
            return [{'file_id': row['file_id'], 'title': row['title']} for row in self.cursor.fetchall()]
        except sqlite3.Error as e:
            print(f"Error getting text list: {e}")
            return []

    def get_text_metadata(self, file_id):
        """Retrieves all metadata (including text content) for a specific file_id."""
        try:
            self.cursor.execute("SELECT * FROM texts WHERE file_id = ?", (file_id,))
            return self.cursor.fetchone()
        except sqlite3.Error as e:
            print(f"Error getting metadata for file_id {file_id}: {e}")
            return None

    def update_text_metadata(self, file_id, data):
        """Updates metadata fields (excluding 'text') for a given file_id."""
        fields_to_update = {k: v for k, v in data.items() if k != 'text'}
        if not fields_to_update:
            print("No metadata fields (excluding text) provided for update.")
            return True  # No update needed, considered success

        try:
            set_clause = ", ".join([f"\"{key}\" = ?" for key in fields_to_update.keys()])  # Quote keys just in case
            values = list(fields_to_update.values()) + [file_id]
            sql = f"UPDATE texts SET {set_clause} WHERE file_id = ?"
            self.cursor.execute(sql, values)
            self.db.commit()
            return True
        except sqlite3.Error as e:
            print(f"Error updating metadata for file_id {file_id}: {e}")
            messagebox.showerror("Update Error", f"Could not update metadata:\n{e}")
            self.db.rollback()
            return False

    def update_text_content_and_reanalyze(self, file_id, new_text):
        if not load_spacy_model():
            return False, "spaCy model not loaded. Cannot re-analyze."

        global NLP_MODEL

        try:
            self.cursor.execute("BEGIN TRANSACTION")

            self.cursor.execute("UPDATE texts SET text = ? WHERE file_id = ?", (new_text, file_id))
            print(f"Text content updated for file_id {file_id}.")

            self.cursor.execute("DELETE FROM wordforms WHERE file_id = ?", (file_id,))
            print(f"Old annotations deleted for file_id {file_id}.")

            print(f"Starting spaCy analysis for file_id {file_id}...")
            doc = NLP_MODEL(new_text)
            print(f"spaCy analysis complete.")

            wordforms_to_insert = []
            for token in doc:
                cleaned = clean_token(token.text)
                if not cleaned or token.is_space:
                    continue
                pos_tag = POS_TAG_TRANSLATIONS.get(token.pos_, token.pos_)
                morph = beautiful_morph(token.morph.to_dict())
                wordforms_to_insert.append((
                    token.text.lower(), token.lemma_, morph, pos_tag, token.dep_, file_id
                ))

            if wordforms_to_insert:
                self.cursor.executemany(
                    'INSERT INTO wordforms (wordform, lemma, morph, pos, dep, file_id) VALUES (?, ?, ?, ?, ?, ?)',
                    wordforms_to_insert)
                print(f"Inserted {len(wordforms_to_insert)} new annotations for file_id {file_id}.")
            else:
                print(f"No new annotations generated for file_id {file_id} (text might be empty).")

            self.db.commit()
            return True, "Text content and annotations successfully updated."

        except sqlite3.Error as e:
            print(f"SQLite error during text update/re-analysis for file_id {file_id}: {e}")
            self.db.rollback()
            return False, f"Database error during update: {e}"
        except Exception as e:
            print(f"General error during text update/re-analysis for file_id {file_id}: {e}")
            self.db.rollback()
            return False, f"Processing error: {e}"

    def get_wordform_details(self, wordform_id):
        try:
            self.cursor.execute("SELECT wordform_id, wordform, lemma, morph, pos FROM wordforms WHERE wordform_id = ?",
                                (wordform_id,))
            return self.cursor.fetchone()
        except sqlite3.Error as e:
            print(f"Error getting details for wordform_id {wordform_id}: {e}")
            return None

        # --- Фрагмент manager.py (внутри класса DBConnection) ---

    def update_wordform(self, wordform_id, data):
        """
        Обновляет поля wordform, lemma, morph, pos для указанного wordform_id.
        Возвращает количество обновленных строк (0 или 1) в случае успеха,
        или -1 в случае ошибки SQL/данных.
        """
        print(f"DB: Попытка обновить wordform_id={wordform_id} данными: {data}")
        try:
            # Выполняем SQL команду UPDATE
            self.cursor.execute("""
                    UPDATE wordforms
                    SET wordform = ?, lemma = ?, morph = ?, pos = ?
                    WHERE wordform_id = ?
                """, (data['wordform'], data['lemma'], data['morph'], data['pos'], wordform_id))

            # Получаем количество строк, которые были изменены последней командой
            updated_rows = self.cursor.rowcount
            print(f"DB: Затронуто строк при обновлении ID {wordform_id}: {updated_rows}")

            if updated_rows == 0:
                print(f"DB: Предупреждение - Запись с ID {wordform_id} не найдена для обновления.")

            # Фиксируем изменения
            self.db.commit()
            print(f"DB: Commit выполнен для операции с ID {wordform_id}.")

            # Возвращаем количество реально обновленных строк
            return updated_rows

        except sqlite3.Error as e:
            print(f"DB: Ошибка SQLite при обновлении wordform_id {wordform_id}: {e}")
            try:
                self.db.rollback()
                print(f"DB: Rollback выполнен из-за ошибки для ID {wordform_id}.")
            except Exception as rollback_e:
                print(f"DB: Дополнительная ошибка при попытке отката транзакции: {rollback_e}")
            messagebox.showerror("Database Update Error", f"Could not update wordform entry ID {wordform_id}:\n{e}")
            return -1  # Возвращаем -1 при ошибке
        except KeyError as e:
            print(f"DB: Отсутствует ключ '{e}' в данных для обновления ID {wordform_id}.")
            messagebox.showerror("Data Error",
                                 f"Missing data field ('{e}') needed for updating wordform ID {wordform_id}.")
            return -1  # Возвращаем -1 при ошибке
        except Exception as e:
            print(f"DB: Неожиданная ошибка при обновлении wordform_id {wordform_id}: {e}")
            try:
                self.db.rollback()
                print(f"DB: Rollback выполнен из-за неожиданной ошибки для ID {wordform_id}.")
            except Exception as rollback_e:
                print(f"DB: Дополнительная ошибка при попытке отката транзакции: {rollback_e}")
            messagebox.showerror("Unexpected Error",
                                 f"An unexpected error occurred during update for ID {wordform_id}:\n{e}")
            return -1  # Возвращаем -1 при ошибке

    def delete_wordform(self, wordform_id):
        try:
            self.cursor.execute("DELETE FROM wordforms WHERE wordform_id = ?", (wordform_id,))
            deleted_rows = self.cursor.rowcount
            self.db.commit()
            if deleted_rows == 0:
                print(f"Warning: No row found with wordform_id {wordform_id} to delete.")
            return deleted_rows > 0
        except sqlite3.Error as e:
            print(f"Error deleting wordform_id {wordform_id}: {e}")
            self.db.rollback()
            messagebox.showerror("Deletion Error", f"Could not delete wordform entry:\n{e}")
            return False

    def get_all_documents_for_indexing(self):
        """Извлекает ID, заголовок и текст всех документов для векторного поиска."""
        try:
            self.cursor.execute("SELECT file_id, title, text FROM texts WHERE text IS NOT NULL AND text != ''")
            rows = self.cursor.fetchall()
            # Преобразуем строки sqlite3.Row в обычные словари для удобства
            return [{'file_id': row['file_id'], 'title': row['title'], 'text': row['text']} for row in rows]
        except sqlite3.Error as e:
            print(f"DB: Error fetching all documents for indexing: {e}")
            return []

    def close(self):
        if self.db:
            self.db.close()
            print("Database connection closed.")


class ManagerApp:

    def __init__(self, root) -> None:
        try:
            self.conn = DBConnection("movies.db")
        except Exception:
            root.quit()
            return  # Stop initialization

        self.root = root
        self.root.title("Corpus Manager")
        self.root.geometry("1200x800")

        self.setup_styles()

        self.notebook = ttk.Notebook(root)
        self.notebook.pack(pady=10, padx=10, expand=True, fill="both")

        self.search_frame = ttk.Frame(self.notebook, padding="10")
        self.stats_overall_frame = ttk.Frame(self.notebook, padding="10")
        self.stats_doc_frame = ttk.Frame(self.notebook, padding="10")
        self.edit_meta_frame = ttk.Frame(self.notebook, padding="10")
        self.edit_text_frame = ttk.Frame(self.notebook, padding="10")

        self.notebook.add(self.search_frame, text="Search")
        self.notebook.add(self.stats_overall_frame, text="Overall Stats")
        self.notebook.add(self.stats_doc_frame, text="Document Stats")
        self.notebook.add(self.edit_meta_frame, text="Edit Metadata")
        self.notebook.add(self.edit_text_frame, text="Edit Text")

        self.vector_search_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(self.vector_search_frame, text="Vector Search")
        self.setup_vector_search_tab()

        # Инициализация и построение индекса для векторного поиска
        self.search_engine = VectorSearchEngine()
        self.build_vector_index()

        self.setup_search_tab()
        self.setup_stats_overall_tab()
        self.setup_stats_doc_tab()
        self.setup_edit_meta_tab()
        self.setup_edit_text_tab()

        self.load_texts_list()
        self.last_search_word = ""

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def setup_styles(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            print("Clam theme not available, using default.")
            style.theme_use("default")

        style.configure("Treeview", rowheight=25, font=('TkDefaultFont', 10))
        style.configure("Treeview.Heading", font=('TkDefaultFont', 11, 'bold'))
        style.configure("TLabel", font=('TkDefaultFont', 10))
        style.configure("TButton", font=('TkDefaultFont', 10), padding=5)
        style.configure("TEntry", font=('TkDefaultFont', 10), padding=5)
        style.configure("TCombobox", font=('TkDefaultFont', 10))
        style.configure("TLabelframe.Label", font=('TkDefaultFont', 10, 'bold'))

    def on_closing(self):
        if messagebox.askokcancel("Exit", "Are you sure you want to exit?"):
            self.conn.close()
            self.root.destroy()

    def load_texts_list(self):
        self.texts_list = self.conn.get_all_texts_summary()
        self.text_titles = [text['title'] if text['title'] else f"ID: {text['file_id']}"
                            for text in self.texts_list]

        widgets_to_update = [
            getattr(self, 'doc_selector_combo', None),
            getattr(self, 'edit_meta_doc_selector_combo', None),
            getattr(self, 'edit_text_doc_selector_combo', None)
        ]
        for combo in widgets_to_update:
            if combo:
                current_selection = combo.get()
                combo['values'] = self.text_titles
                if current_selection in self.text_titles:
                    combo.set(current_selection)
                elif self.text_titles:
                    combo.current(0)
                else:
                    combo.set('')

    # --- Tab Setup Methods ---

    def setup_search_tab(self):
        frame = self.search_frame
        top_frame = ttk.Frame(frame)
        top_frame.pack(fill="x", pady=5)

        ttk.Label(top_frame, text="Query:").pack(side="left", padx=5)
        self.entry_var = tk.StringVar()
        entry_search = ttk.Entry(top_frame, textvariable=self.entry_var, width=40)
        entry_search.pack(side="left", padx=5)
        Hovertip(entry_search, "Enter word or lemma to search.")
        entry_search.bind("<Return>", self.search)

        btn_search = ttk.Button(top_frame, text="Search", command=self.search)
        btn_search.pack(side="left", padx=5)
        Hovertip(btn_search, "Perform search in the corpus.")

        ttk.Label(top_frame, text="Occurrences:").pack(side="left", padx=(20, 5))
        self.occ_numb_var = tk.StringVar(value="0")
        entry_occ = ttk.Entry(top_frame, textvariable=self.occ_numb_var, state="readonly", width=10)
        entry_occ.pack(side="left", padx=5)
        Hovertip(entry_occ, "Total number of matching wordforms found.")

        ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=10)

        lbl_results = ttk.Label(frame, text="Search Results (Wordforms):", style="TLabelframe.Label")
        lbl_results.pack(pady=5, anchor="w")
        table_results_frame = ttk.Frame(frame)
        table_results_frame.pack(pady=5, fill="x")

        columns = ("ID", "Wordform", "Lemma", "Morph", "POS", "Link")
        self.tree_search = ttk.Treeview(table_results_frame, columns=columns, show="headings", height=10)

        col_widths = {"ID": 0, "Wordform": 150, "Lemma": 150, "Morph": 300, "POS": 150, "Link": 300}
        for col in columns:
            self.tree_search.heading(col, text=col, anchor='w')
            stretch = tk.NO if col == "ID" else tk.YES  # Don't stretch hidden ID column
            self.tree_search.column(col, width=col_widths[col], anchor='w', stretch=stretch)

        vsb_results = ttk.Scrollbar(table_results_frame, orient="vertical", command=self.tree_search.yview)
        hsb_results = ttk.Scrollbar(table_results_frame, orient="horizontal", command=self.tree_search.xview)
        self.tree_search.configure(yscrollcommand=vsb_results.set, xscrollcommand=hsb_results.set)

        vsb_results.pack(side="right", fill="y")
        hsb_results.pack(side="bottom", fill="x")
        self.tree_search.pack(side="left", fill="both", expand=True)
        Hovertip(self.tree_search, "Double-click a row to edit the wordform details.")

        self.tree_search.bind("<Double-1>", self.open_wordform_edit_window)

        button_frame_results = ttk.Frame(frame)  # Новый фрейм для кнопок
        button_frame_results.pack(fill="x", pady=5)

        # Кнопка Удалить
        delete_button = ttk.Button(button_frame_results, text="Delete Selected Wordform",
                                   command=self.delete_selected_wordform)
        delete_button.pack(side="left", padx=(0, 10))  # Добавляем отступ справа
        Hovertip(delete_button, "Permanently delete the selected wordform entry from the database.")

        # Кнопка Экспорт
        export_button = ttk.Button(button_frame_results, text="Export Selected to JSON",
                                   command=self.export_selected_wordform)
        export_button.pack(side="left", padx=(0, 10))
        Hovertip(export_button, "Export the details of the selected wordform entry to a JSON file.")

        # Кнопка Импорт
        import_button = ttk.Button(button_frame_results, text="Import from JSON",
                                   command=self.import_wordforms_from_json)
        import_button.pack(side="left")
        Hovertip(import_button, "Import wordform data from a JSON file to update existing entries in the database.")

        btn_delete = ttk.Button(frame, text="Delete Selected Wordform", command=self.delete_selected_wordform)
        btn_delete.pack(pady=5)
        Hovertip(btn_delete, "Permanently delete the selected wordform entry from the database.")

        lbl_examples = ttk.Label(frame, text="Usage Examples (Concordance):", style="TLabelframe.Label")
        lbl_examples.pack(pady=5, anchor="w")
        table_examples_frame = ttk.Frame(frame)
        table_examples_frame.pack(pady=5, fill="both", expand=True)

        columns_ex = ("Example", "Link", "Genre")
        self.tree_examples = ttk.Treeview(table_examples_frame, columns=columns_ex, show="headings", height=10)
        col_widths_ex = {"Example": 600, "Link": 300, "Genre": 150}
        for col in columns_ex:
            self.tree_examples.heading(col, text=col, anchor='w')
            self.tree_examples.column(col, width=col_widths_ex[col], anchor='w', stretch=tk.YES)

        vsb_examples = ttk.Scrollbar(table_examples_frame, orient="vertical", command=self.tree_examples.yview)
        hsb_examples = ttk.Scrollbar(table_examples_frame, orient="horizontal", command=self.tree_examples.xview)
        self.tree_examples.configure(yscrollcommand=vsb_examples.set, xscrollcommand=hsb_examples.set)

        vsb_examples.pack(side="right", fill="y")
        hsb_examples.pack(side="bottom", fill="x")
        self.tree_examples.pack(side="left", fill="both", expand=True)
        Hovertip(self.tree_examples, "Sentences containing the searched word.")

    def setup_stats_overall_tab(self):
        frame = self.stats_overall_frame
        ttk.Button(frame, text="Load / Refresh Overall Statistics", command=self.load_overall_stats).pack(pady=10)

        stats_table_frame = ttk.Frame(frame)
        stats_table_frame.pack(pady=5, fill="both", expand=True)

        self.tree_stats_overall = ttk.Treeview(stats_table_frame, columns=("POS", "Count"), show="headings", height=20)
        vsb = ttk.Scrollbar(stats_table_frame, orient="vertical", command=self.tree_stats_overall.yview)
        self.tree_stats_overall.configure(yscrollcommand=vsb.set)

        self.tree_stats_overall.heading("POS", text="Part of Speech", anchor='w')
        self.tree_stats_overall.column("POS", width=300, anchor='w')
        self.tree_stats_overall.heading("Count", text="Count", anchor='e')
        self.tree_stats_overall.column("Count", width=150, anchor='e', stretch=tk.NO)

        vsb.pack(side="right", fill="y")
        self.tree_stats_overall.pack(side="left", fill="both", expand=True)
        Hovertip(self.tree_stats_overall, "Total count for each part of speech across the entire corpus.")

    def setup_stats_doc_tab(self):
        frame = self.stats_doc_frame
        # Document selection
        selector_frame = ttk.Frame(frame)
        selector_frame.pack(fill="x", pady=10)
        ttk.Label(selector_frame, text="Select Text:").pack(side="left", padx=5)
        self.doc_selector_var = tk.StringVar()
        self.doc_selector_combo = ttk.Combobox(selector_frame, textvariable=self.doc_selector_var, state="readonly",
                                               width=60)
        self.doc_selector_combo.pack(side="left", padx=5, fill="x", expand=True)
        Hovertip(self.doc_selector_combo, "Choose a text to view its POS statistics.")
        self.doc_selector_combo.bind("<<ComboboxSelected>>", self.load_doc_stats)  # Load stats on selection

        # Statistics table
        stats_table_frame = ttk.Frame(frame)
        stats_table_frame.pack(pady=5, fill="both", expand=True)

        self.tree_stats_doc = ttk.Treeview(stats_table_frame, columns=("POS", "Count"), show="headings", height=20)
        vsb = ttk.Scrollbar(stats_table_frame, orient="vertical", command=self.tree_stats_doc.yview)
        self.tree_stats_doc.configure(yscrollcommand=vsb.set)

        self.tree_stats_doc.heading("POS", text="Part of Speech", anchor='w')
        self.tree_stats_doc.column("POS", width=300, anchor='w')
        self.tree_stats_doc.heading("Count", text="Count", anchor='e')
        self.tree_stats_doc.column("Count", width=150, anchor='e', stretch=tk.NO)

        vsb.pack(side="right", fill="y")
        self.tree_stats_doc.pack(side="left", fill="both", expand=True)
        Hovertip(self.tree_stats_doc, "Part of speech counts for the selected text.")

    def setup_edit_meta_tab(self):
        frame = self.edit_meta_frame
        selector_frame = ttk.Frame(frame)
        selector_frame.pack(fill="x", pady=10)
        ttk.Label(selector_frame, text="Select Text:").pack(side="left", padx=5)
        self.edit_meta_doc_selector_var = tk.StringVar()
        self.edit_meta_doc_selector_combo = ttk.Combobox(selector_frame, textvariable=self.edit_meta_doc_selector_var,
                                                         state="readonly", width=50)
        self.edit_meta_doc_selector_combo.pack(side="left", padx=5, fill="x", expand=True)
        Hovertip(self.edit_meta_doc_selector_combo, "Choose a text to edit its metadata.")
        self.edit_meta_doc_selector_combo.bind("<<ComboboxSelected>>", self.load_metadata_for_editing)

        edit_fields_frame = ttk.LabelFrame(frame, text="Text Metadata", padding="10")
        edit_fields_frame.pack(pady=10, fill="x")

        self.edit_meta_entries = {}  # Dictionary to hold the StringVar for each field
        # Define fields to edit and their display labels
        fields_to_edit = ["title", "genre", "date", "country", "lang", "imdb", "text_id", "num_words"]
        labels = {
            "title": "Title:", "genre": "Genre:", "date": "Date:", "country": "Country:",
            "lang": "Language:", "imdb": "IMDB ID:", "text_id": "Text ID:", "num_words": "# Words:"
        }

        for i, field in enumerate(fields_to_edit):
            row, col = i // 2, (i % 2) * 2
            ttk.Label(edit_fields_frame, text=labels.get(field, field.capitalize()) + ":").grid(row=row, column=col,
                                                                                                padx=5, pady=5,
                                                                                                sticky="w")
            entry_var = tk.StringVar()
            entry = ttk.Entry(edit_fields_frame, textvariable=entry_var, width=40)
            entry.grid(row=row, column=col + 1, padx=5, pady=5, sticky="ew")
            self.edit_meta_entries[field] = entry_var

        edit_fields_frame.columnconfigure(1, weight=1)
        edit_fields_frame.columnconfigure(3, weight=1)

        btn_save = ttk.Button(frame, text="Save Metadata Changes", command=self.save_metadata_changes)
        btn_save.pack(pady=10)
        Hovertip(btn_save, "Save the modified metadata fields to the database.")

    def setup_edit_text_tab(self):
        frame = self.edit_text_frame

        selector_frame = ttk.Frame(frame)
        selector_frame.pack(fill="x", pady=10)
        ttk.Label(selector_frame, text="Select Text:").pack(side="left", padx=5)
        self.edit_text_doc_selector_var = tk.StringVar()
        self.edit_text_doc_selector_combo = ttk.Combobox(selector_frame, textvariable=self.edit_text_doc_selector_var,
                                                         state="readonly", width=50)
        self.edit_text_doc_selector_combo.pack(side="left", padx=5, fill="x", expand=True)
        Hovertip(self.edit_text_doc_selector_combo, "Choose a text to edit its content.")
        self.edit_text_doc_selector_combo.bind("<<ComboboxSelected>>", self.load_text_for_editing)

        text_frame = ttk.LabelFrame(frame, text="Text Content", padding="10")
        text_frame.pack(pady=10, fill="both", expand=True)

        self.text_edit_widget = scrolledtext.ScrolledText(text_frame, wrap=tk.WORD, width=80, height=20,
                                                          font=('TkDefaultFont', 10), undo=True)  # Enable undo
        self.text_edit_widget.pack(fill="both", expand=True)
        Hovertip(self.text_edit_widget, "Edit the text content here. Undo/Redo available (Ctrl+Z/Ctrl+Y).")

        btn_save_analyze = ttk.Button(frame, text="Save Text and Re-analyze Annotations",
                                      command=self.save_and_reanalyze_text)
        btn_save_analyze.pack(pady=10)
        Hovertip(btn_save_analyze,
                 "Save the edited text. WARNING: This will delete all existing annotations (lemma, POS, etc.) for this text and generate new ones based on the edited content. This can be slow.")

    # --- Action Handler Methods ---

    def search(self, event=None):
        word = self.entry_var.get()
        if not word:
            # Optional: Show warning if search query is empty
            # messagebox.showwarning("Empty Query", "Please enter a word or lemma to search.")
            return  # Don't search if query is empty

        print(f"Searching for: {word}")
        self.last_search_word = word

        res = self.conn.find_info_by_word(word)

        self.occ_numb_var.set(res["occurences"])

        self.tree_search.delete(*self.tree_search.get_children())
        for result in res["search_results"]:
            values = (
                result.wordform_id,
                result.wordform,
                result.lemma,
                result.morph,
                result.pos,
                result.link
            )
            self.tree_search.insert("", "end", values=values, iid=result.wordform_id)

        self.tree_examples.delete(*self.tree_examples.get_children())
        for example in res["examples"]:
            self.tree_examples.insert("", "end", values=(
                example["text"], example["link"], example["genre"]
            ))
        print("Search complete.")

    def load_overall_stats(self):
        print("Loading overall statistics...")
        stats = self.conn.get_overall_pos_stats()
        self.tree_stats_overall.delete(*self.tree_stats_overall.get_children())
        for row in stats:
            self.tree_stats_overall.insert("", "end", values=(row['pos'], row['count']))
        print("Overall statistics loaded.")

    def load_doc_stats(self, event=None):
        file_id = self.get_selected_file_id(self.doc_selector_var)
        self.tree_stats_doc.delete(*self.tree_stats_doc.get_children())
        if file_id is not None:
            print(f"Loading document statistics for file_id: {file_id}")
            stats = self.conn.get_document_pos_stats(file_id)
            for row in stats:
                self.tree_stats_doc.insert("", "end", values=(row['pos'], row['count']))
            print("Document statistics loaded.")
        else:
            print("No document selected for statistics.")

    def get_selected_file_id(self, combo_var):
        selected_title_display = combo_var.get()
        if not selected_title_display:
            return None
        for text_info in self.texts_list:
            display_title = text_info['title'] if text_info['title'] else f"ID: {text_info['file_id']}"
            if display_title == selected_title_display:
                return text_info['file_id']
        print(f"Warning: Could not find file_id for selection '{selected_title_display}'")
        return None

    def load_metadata_for_editing(self, event=None):
        self.current_edit_meta_file_id = self.get_selected_file_id(self.edit_meta_doc_selector_var)
        for entry_var in self.edit_meta_entries.values():
            entry_var.set("")

        if self.current_edit_meta_file_id is not None:
            print(f"Loading metadata for editing file_id: {self.current_edit_meta_file_id}")
            metadata = self.conn.get_text_metadata(self.current_edit_meta_file_id)
            if metadata:
                for field, entry_var in self.edit_meta_entries.items():
                    entry_var.set(metadata[field] if metadata[field] is not None else "")
                print("Metadata loaded into fields.")
            else:
                messagebox.showerror("Error", f"Could not load metadata for file ID: {self.current_edit_meta_file_id}")
        else:
            print("No document selected for metadata editing.")

    def save_metadata_changes(self):
        if not hasattr(self, 'current_edit_meta_file_id') or self.current_edit_meta_file_id is None:
            messagebox.showwarning("No Selection", "Please select a text to edit its metadata first.")
            return

        print(f"Saving metadata for file_id: {self.current_edit_meta_file_id}")
        data_to_update = {field: entry_var.get() for field, entry_var in self.edit_meta_entries.items()}

        if self.conn.update_text_metadata(self.current_edit_meta_file_id, data_to_update):
            messagebox.showinfo("Success", "Metadata updated successfully.")
            self.load_texts_list()
            # Try to re-select the edited item in the current combobox
            # (get_text_metadata needed again to find potential new title)
            updated_metadata = self.conn.get_text_metadata(self.current_edit_meta_file_id)
            if updated_metadata:
                new_display_title = updated_metadata['title'] if updated_metadata[
                    'title'] else f"ID: {updated_metadata['file_id']}"
                if new_display_title in self.text_titles:
                    self.edit_meta_doc_selector_var.set(new_display_title)

        else:
            # Error message already shown by DBConnection method
            print("Metadata save failed.")

    def load_text_for_editing(self, event=None):
        self.current_edit_text_file_id = self.get_selected_file_id(self.edit_text_doc_selector_var)
        self.text_edit_widget.delete('1.0', tk.END)
        self.text_edit_widget.edit_reset()

        if self.current_edit_text_file_id is not None:
            print(f"Loading text content for editing file_id: {self.current_edit_text_file_id}")
            metadata = self.conn.get_text_metadata(self.current_edit_text_file_id)
            if metadata and metadata['text'] is not None:
                self.text_edit_widget.insert('1.0', metadata['text'])
                print("Text content loaded.")
            elif metadata:
                print(f"Text content is empty for file_id: {self.current_edit_text_file_id}")
            else:
                messagebox.showerror("Error",
                                     f"Could not load text content for file ID: {self.current_edit_text_file_id}")
        else:
            print("No document selected for text editing.")

    def save_and_reanalyze_text(self):
        """Saves edited text content and triggers database update and spaCy re-analysis."""
        if not hasattr(self, 'current_edit_text_file_id') or self.current_edit_text_file_id is None:
            messagebox.showwarning("No Selection", "Please select a text to save first.")
            return

        # Get edited text from the widget
        new_text = self.text_edit_widget.get('1.0', tk.END).strip()  # Strip trailing whitespace/newlines

        # Confirm with the user due to destructive nature of re-analysis
        if not messagebox.askyesno("Confirm Re-analysis",
                                   "Saving this text will DELETE all existing annotations (lemma, POS, etc.) "
                                   "for this document and generate new ones.\n\n"
                                   "This process might take some time and cannot be undone.\n\n"
                                   "Are you sure you want to continue?"):
            return  # User cancelled

        print(f"Starting save and re-analyze process for file_id: {self.current_edit_text_file_id}")
        self.root.config(cursor="watch")
        self.root.update_idletasks()

        success, message = self.conn.update_text_content_and_reanalyze(self.current_edit_text_file_id, new_text)

        self.root.config(cursor="")
        if success:
            messagebox.showinfo("Success", message)
            self.text_edit_widget.edit_reset()
        else:
            messagebox.showerror("Error", message)

        print(f"Save and re-analyze process finished for file_id: {self.current_edit_text_file_id}")

    def get_selected_wordform_id(self):
        selected_items = self.tree_search.selection()
        if not selected_items:
            messagebox.showwarning("No Selection", "Please select a wordform entry in the search results table first.")
            return None

        selected_iid = selected_items[0]
        try:
            wordform_id = int(selected_iid)
            return wordform_id
        except (ValueError, TypeError):
            # Fallback: try getting it from the hidden first column value
            try:
                item_values = self.tree_search.item(selected_iid, 'values')
                wordform_id = int(item_values[0])
                return wordform_id
            except (IndexError, ValueError, TypeError, tk.TclError):
                messagebox.showerror("Error", "Could not retrieve the ID for the selected wordform entry.")
                return None

    def open_wordform_edit_window(self, event):
        wordform_id = self.get_selected_wordform_id()
        if wordform_id is None:
            return  # Message already shown by helper function

        print(f"Opening edit window for wordform_id: {wordform_id}")
        details = self.conn.get_wordform_details(wordform_id)
        if not details:
            messagebox.showerror("Error", f"Could not load details for wordform ID: {wordform_id}")
            return

        popup = Toplevel(self.root)
        popup.title(f"Edit Wordform ID: {wordform_id}")
        popup.geometry("600x300")
        popup.transient(self.root)
        popup.update_idletasks()
        popup.grab_set()  # Make popup modal (block interaction with main window)
        popup.resizable(False, False)

        form_frame = ttk.Frame(popup, padding="10")
        form_frame.pack(expand=True, fill="both")

        entries = {}
        fields_to_edit = ['wordform', 'lemma', 'morph', 'pos']
        labels = {'wordform': 'Wordform:', 'lemma': 'Lemma:', 'morph': 'Morphology:', 'pos': 'POS:'}

        # Create labels and entry fields
        for i, field in enumerate(fields_to_edit):
            ttk.Label(form_frame, text=labels[field]).grid(row=i, column=0, padx=5, pady=8, sticky="w")
            var = tk.StringVar(value=details[field])  # Pre-fill with current value
            entry = ttk.Entry(form_frame, textvariable=var, width=50)
            entry.grid(row=i, column=1, padx=5, pady=8, sticky="ew")
            entries[field] = var

        form_frame.columnconfigure(1, weight=1)

        button_frame = ttk.Frame(popup, padding=(10, 10, 10, 15))
        button_frame.pack(fill="x", side="bottom")

        save_button = ttk.Button(button_frame, text="Save Changes",
                                 command=lambda: self.save_wordform_edit(wordform_id, entries, popup))
        save_button.pack(side="left", padx=10)

        cancel_button = ttk.Button(button_frame, text="Cancel", command=popup.destroy)
        cancel_button.pack(side="right", padx=10)

        # Set initial focus on the first entry field
        # Need to find the actual widget associated with 'wordform' StringVar
        first_entry_widget = form_frame.grid_slaves(row=0, column=1)[0]
        first_entry_widget.focus_set()

    def save_wordform_edit(self, wordform_id, entries, popup_window):
        """Callback function to save edited wordform data."""
        print(f"Attempting to save changes for wordform_id: {wordform_id}")
        # Get data from StringVars
        new_data = {field: var.get().strip() for field, var in entries.items()}  # Strip whitespace

        new_data['wordform'] = new_data['wordform'].lower()

        if self.conn.update_wordform(wordform_id, new_data):
            print(f"Wordform ID {wordform_id} updated successfully in DB.")
            # Optional: Show success message inside the popup before destroying it
            # messagebox.showinfo("Success", "Entry updated successfully.", parent=popup_window)
            popup_window.destroy()

            try:
                current_values = list(self.tree_search.item(wordform_id, 'values'))
                link_value = current_values[5]  # Assuming Link is the 6th column (index 5)

                # Prepare the updated values tuple (including hidden ID)
                updated_values = (
                    wordform_id,
                    new_data['wordform'],
                    new_data['lemma'],
                    new_data['morph'],
                    new_data['pos'],
                    link_value  # Preserve the original Link
                )
                # Update the item in the Treeview
                self.tree_search.item(wordform_id, values=updated_values)
                print(f"Treeview row updated for iid {wordform_id}.")
            except (tk.TclError, IndexError, Exception) as e:
                # If updating the specific row fails (e.g., item deleted), refresh the whole search
                print(f"Error updating Treeview row {wordform_id}: {e}. Refreshing search results.")
                self.refresh_search_results()
        else:
            print(f"Failed to save changes for wordform_id: {wordform_id}")
            popup_window.focus_set()
            popup_window.grab_set()

    def delete_selected_wordform(self):
        """Deletes the selected wordform entry from the database and the table."""
        wordform_id = self.get_selected_wordform_id()
        if wordform_id is None:
            return  # Message already shown

        print(f"Attempting to delete wordform_id: {wordform_id}")
        # Confirm deletion with the user
        if messagebox.askyesno("Confirm Deletion",
                               f"Are you sure you want to permanently delete wordform entry ID: {wordform_id}?\n"
                               "This action cannot be undone."):
            # Call DBConnection method to delete from database
            if self.conn.delete_wordform(wordform_id):
                print(f"Wordform ID {wordform_id} deleted successfully from DB.")
                # Remove the row from the Treeview table
                try:
                    if self.tree_search.exists(wordform_id):  # Check if item still exists
                        self.tree_search.delete(wordform_id)  # Use iid to delete
                        print(f"Treeview row deleted for iid {wordform_id}.")
                        # Decrement the occurrence counter
                        try:
                            current_count = int(self.occ_numb_var.get())
                            self.occ_numb_var.set(str(max(0, current_count - 1)))  # Avoid going below zero
                        except ValueError:
                            self.refresh_search_results()
                    else:
                        print(f"Treeview item {wordform_id} already removed or never existed.")
                        self.refresh_search_results()

                except (tk.TclError, Exception) as e:
                    print(f"Error deleting Treeview row {wordform_id}: {e}. Refreshing search results.")
                    self.refresh_search_results()
            else:
                print(f"Failed to delete wordform_id: {wordform_id}")
        else:
            print("Deletion cancelled by user.")

    def refresh_search_results(self):
        print("Refreshing search results...")
        if self.last_search_word:
            self.search()
            print("Search results refreshed.")
        else:
            self.tree_search.delete(*self.tree_search.get_children())
            self.tree_examples.delete(*self.tree_examples.get_children())
            self.occ_numb_var.set("0")
            print("No previous search query found to refresh.")

    def export_selected_wordform(self):
        """Exports the selected wordform's details to a JSON file."""
        selected_iid = self.get_selected_wordform_id()  # Используем существующий метод для получения ID
        if selected_iid is None:
            return  # Сообщение уже показано

        # Получаем полные данные из БД и таблицы
        db_details = self.conn.get_wordform_details(selected_iid)
        print(db_details)
        if not db_details:
            messagebox.showerror("Error", f"Could not fetch details for ID {selected_iid} from database.")
            return

        try:
            # Получаем значение Link из таблицы (может вызвать ошибку, если строка удалена)
            table_values = self.tree_search.item(selected_iid, 'values')
            link_info = table_values[5]  # Индекс 5 для Link
        except (IndexError, tk.TclError):
            link_info = "N/A"  # Значение по умолчанию, если не удалось получить
            print(f"Warning: Could not get 'Link' value for wordform {selected_iid} from table.")

        # Формируем данные для экспорта
        wordform_id_str = str(selected_iid)  # Ключи JSON должны быть строками
        export_entry_data = {
            "wordform": db_details['wordform'],
            "lemma": db_details['lemma'],
            "morph": db_details['morph'],
            "pos": db_details['pos'],
            "source_link": link_info  # Добавляем информацию об источнике
        }
        export_data = {wordform_id_str: export_entry_data}

        # Запрашиваем путь для сохранения файла
        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Save Wordform Data As..."
        )

        if not file_path:
            print("Export cancelled by user.")
            return  # Пользователь нажал "Отмена"

        existing_data = {}
        file_exists = os.path.exists(file_path)

        # --- Логика чтения/обновления/записи файла ---
        try:
            if file_exists:
                with open(file_path, 'r', encoding='utf-8') as f:
                    try:
                        existing_data = json.load(f)
                        if not isinstance(existing_data, dict):
                            print("Warning: Existing file does not contain a valid JSON dictionary. Overwriting.")
                            existing_data = {}
                    except json.JSONDecodeError:
                        print(f"Warning: Could not decode JSON from {file_path}. Overwriting content.")
                        existing_data = {}  # Перезаписываем, если файл поврежден

                # Проверяем, существует ли уже запись с таким ID
                if wordform_id_str in existing_data:
                    overwrite = messagebox.askyesno(
                        "Overwrite Confirmation",
                        f"An entry for Wordform ID '{wordform_id_str}' already exists in the file.\n"
                        f"Do you want to overwrite it?",
                        parent=self.root  # Указываем родителя для модальности
                    )
                    if overwrite:
                        existing_data[wordform_id_str] = export_entry_data
                        print(f"Overwriting entry for ID {wordform_id_str} in {file_path}")
                    else:
                        print(f"Skipping update for existing ID {wordform_id_str}.")
                        return  # Не перезаписываем и выходим
                else:
                    # Добавляем новые данные к существующим
                    existing_data.update(export_data)
                    print(f"Adding entry for ID {wordform_id_str} to {file_path}")

                # Записываем обновленные данные
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(existing_data, f, indent=4, ensure_ascii=False)
                messagebox.showinfo("Success",
                                    f"Data for Wordform ID '{wordform_id_str}' was appended/updated in {os.path.basename(file_path)}.")

            else:  # Файл не существует, просто записываем новые данные
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, indent=4, ensure_ascii=False)
                print(f"Exported entry for ID {wordform_id_str} to new file {file_path}")
                messagebox.showinfo("Success",
                                    f"Data for Wordform ID '{wordform_id_str}' exported to {os.path.basename(file_path)}.")

        except IOError as e:
            messagebox.showerror("File Error", f"An error occurred while writing to file:\n{e}")
        except Exception as e:
            messagebox.showerror("Error", f"An unexpected error occurred during export:\n{e}")

        # --- Фрагмент manager.py (внутри класса ManagerApp) ---

    def import_wordforms_from_json(self):
        """
        Imports wordform data from a JSON file to update existing entries in the database.
        Reads a JSON file where keys are wordform_ids (as strings) and values
        are dictionaries containing 'wordform', 'lemma', 'morph', 'pos'.
        """
        file_path = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Select JSON File to Import Wordform Data"
        )

        # Если пользователь не выбрал файл
        if not file_path:
            print("APP: Import cancelled by user (no file selected).")
            return

        print(f"APP: Attempting to import data from: {file_path}")

        # Инициализация счетчиков для итоговой статистики
        actually_updated_count = 0  # Счетчик РЕАЛЬНО обновленных строк в БД
        processed_ok_count = 0  # Счетчик успешно выполненных DB операций (без SQL/Data ошибок)
        not_found_count = 0  # Счетчик ID, не найденных в БД для обновления
        error_count = 0  # Счетчик ошибок SQL или данных при попытке обновления
        skipped_count = 0  # Счетчик записей с неверным форматом/ID в JSON файле

        try:
            # Шаг 1: Чтение и парсинг JSON файла
            with open(file_path, 'r', encoding='utf-8') as f:
                try:
                    data_to_import = json.load(f)
                except json.JSONDecodeError as e:
                    messagebox.showerror("JSON Error",
                                         f"Failed to decode JSON file:\n{e}\n\nPlease ensure the file contains valid JSON.")
                    return

            # Шаг 2: Проверка основного формата данных (должен быть словарь)
            if not isinstance(data_to_import, dict):
                messagebox.showerror("Format Error",
                                     "The JSON file must contain a dictionary (key-value pairs representing wordform_id: data) at the top level.")
                return

            # Шаг 3: Подтверждение перед началом импорта
            num_entries = len(data_to_import)
            if num_entries == 0:
                messagebox.showinfo("Info", "The selected JSON file contains no data entries.")
                return

            confirm = messagebox.askyesno(
                "Confirm Import",
                f"Found {num_entries} potential entries in the JSON file.\n"
                f"This will attempt to update existing wordform entries in the database using the IDs from the file.\n\n"
                f"Proceed with the import?",
                parent=self.root  # Делаем окно подтверждения модальным относительно главного
            )

            if not confirm:
                print("APP: Import cancelled by user confirmation.")
                return

            # Шаг 4: Итерация по записям из файла и обработка каждой
            print(f"APP: Starting import process for {num_entries} entries...")
            for wordform_id_str, entry_data in data_to_import.items():

                # 4.1 Валидация ID (должен быть конвертируемым в int)
                try:
                    wordform_id = int(wordform_id_str)
                except (ValueError, TypeError):
                    print(f"APP: Skipping invalid ID '{wordform_id_str}' (not an integer).")
                    skipped_count += 1
                    continue  # Переходим к следующей записи в файле

                # 4.2 Валидация формата данных для записи (должен быть словарем)
                if not isinstance(entry_data, dict):
                    print(
                        f"APP: Skipping invalid data format for ID {wordform_id} (expected dictionary, got {type(entry_data)}).")
                    skipped_count += 1
                    continue

                # 4.3 Проверка наличия обязательных полей для обновления
                required_fields = ['wordform', 'lemma', 'morph', 'pos']
                missing_fields = [field for field in required_fields if field not in entry_data]
                if missing_fields:
                    print(
                        f"APP: Skipping incomplete data for ID {wordform_id} (missing fields: {', '.join(missing_fields)}).")
                    skipped_count += 1
                    continue

                # 4.4 Подготовка данных (очистка, приведение типов)
                try:
                    update_data = {
                        'wordform': str(entry_data['wordform']).lower().strip(),
                        'lemma': str(entry_data['lemma']).strip(),
                        'morph': str(entry_data['morph']).strip(),
                        'pos': str(entry_data['pos']).strip()
                    }
                except Exception as e:
                    # Ошибка при обработке значений полей (например, если там не строки)
                    print(f"APP: Error preparing data fields for ID {wordform_id}: {e}. Skipping.")
                    skipped_count += 1
                    continue

                # 4.5 Вызов метода обновления/замены в БД и получение результата
                # (Метод replace_wordform теперь делает SELECT + UPDATE)
                rows_affected = self.conn.replace_wordform(wordform_id, update_data)
                print(f"APP: Result (rows affected) from DB operation for ID {wordform_id}: {rows_affected}")

                # 4.6 Интерпретация результата и обновление счетчиков
                # rows_affected: >0 (обычно 1) = Успешно обновлено; 0 = ID не найден; -1 = Ошибка SQL; -2 = Ошибка данных
                if rows_affected >= 0:  # Если не было ошибки (-1 или -2)
                    processed_ok_count += 1  # Считаем, что операция в БД прошла без сбоя
                    if rows_affected > 0:  # Если реально была обновлена строка
                        actually_updated_count += 1
                        # Немедленно обновляем видимую строку в таблице, если она там есть
                        if self.tree_search.exists(wordform_id):
                            try:
                                current_values = list(self.tree_search.item(wordform_id, 'values'))
                                link_value = current_values[5] if len(current_values) > 5 else "N/A"
                                updated_values = (
                                    wordform_id, update_data['wordform'], update_data['lemma'],
                                    update_data['morph'], update_data['pos'], link_value
                                )
                                self.tree_search.item(wordform_id, values=updated_values)
                                print(f"APP: Treeview row for ID {wordform_id} updated visually.")
                            except (tk.TclError, IndexError, Exception) as e:
                                print(
                                    f"APP: Warning - Could not update Treeview row for ID {wordform_id} after import: {e}")
                    elif rows_affected == 0:
                        # ID не был найден в базе данных, считаем это отдельно
                        not_found_count += 1
                else:  # Если rows_affected < 0 (была ошибка -1 или -2)
                    error_count += 1
                    # Можно добавить опцию остановки импорта при первой ошибке
                    # print("APP: Stopping import due to database error.")
                    # break # Раскомментировать для остановки

            # Шаг 5: Показ итогового сообщения пользователю
            summary_message = (f"Import process finished.\n\n"
                               f"Entries in JSON file: {num_entries}\n"
                               f"DB operations attempted: {processed_ok_count}\n"
                               f"Entries actually updated in DB: {actually_updated_count}\n"
                               f"Entries not found in DB: {not_found_count}\n"
                               f"Database/Data errors during update: {error_count}\n"
                               f"Skipped entries (invalid format/ID): {skipped_count}")
            print(
                f"APP: Import Summary - {summary_message.replace('\n\n', ' // ').replace('\n', ' / ')}")  # Логируем итог

            # Выбираем тип сообщения в зависимости от наличия ошибок
            if error_count > 0:
                messagebox.showwarning("Import Complete with Errors", summary_message)
            else:
                messagebox.showinfo("Import Complete", summary_message)

            # Шаг 6: Обновление результатов поиска после импорта
            # Обновляем, если были реальные изменения, ошибки или ID не были найдены (чтобы убедиться в консистентности)
            if actually_updated_count > 0 or error_count > 0 or not_found_count > 0:
                print("APP: Refreshing search results after import.")
                self.refresh_search_results()
            else:
                print("APP: No actual updates, errors, or 'not found' entries occurred; skipping search refresh.")

        # Обработка ошибок чтения файла или других непредвиденных исключений
        except FileNotFoundError:
            messagebox.showerror("File Error", f"The selected file was not found:\n{file_path}")
            print(f"APP: Error - File not found: {file_path}")
        except IOError as e:
            messagebox.showerror("File Error", f"An error occurred while reading the file:\n{e}")
            print(f"APP: Error - I/O error reading file: {e}")
        except Exception as e:
            messagebox.showerror("Import Error", f"An unexpected error occurred during the import process:\n{e}")
            import traceback
            traceback.print_exc()  # Выводим traceback в консоль для полной диагностики
            print(f"APP: Error - Unexpected exception during import: {e}")

    def build_vector_index(self):
        """Получает документы из БД и строит поисковый индекс."""
        print("APP: Fetching documents from DB for vector indexing...")
        all_docs = self.conn.get_all_documents_for_indexing()

        if not all_docs:
            messagebox.showwarning("Indexing Warning", "No documents found in the database to build a search index.")
            return

        # Создаем словарь {file_id: title} для быстрого отображения результатов
        self.doc_titles_map = {doc['file_id']: doc['title'] for doc in all_docs}

        # Запускаем сам процесс индексации
        self.search_engine.build_index(all_docs)
        print("APP: Vector index is ready.")

    def setup_vector_search_tab(self):
        """Создает виджеты для вкладки векторного поиска."""
        frame = self.vector_search_frame
        top_frame = ttk.Frame(frame)
        top_frame.pack(fill="x", pady=5)

        ttk.Label(top_frame, text="Full-text query:").pack(side="left", padx=5)
        self.vector_entry_var = tk.StringVar()
        entry_search = ttk.Entry(top_frame, textvariable=self.vector_entry_var, width=60)
        entry_search.pack(side="left", padx=5, fill="x", expand=True)
        Hovertip(entry_search, "Enter a phrase or sentence to search for relevant documents.")
        entry_search.bind("<Return>", self.perform_vector_search)

        btn_search = ttk.Button(top_frame, text="Search Documents", command=self.perform_vector_search)
        btn_search.pack(side="left", padx=5)

        ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=10)

        lbl_results = ttk.Label(frame, text="Relevant Documents:", style="TLabelframe.Label")
        lbl_results.pack(pady=5, anchor="w")
        table_frame = ttk.Frame(frame)
        table_frame.pack(pady=5, fill="both", expand=True)

        columns = ("Score", "Title")
        self.tree_vector_search = ttk.Treeview(table_frame, columns=columns, show="headings", height=15)

        self.tree_vector_search.heading("Score", text="Relevance Score", anchor='w')
        self.tree_vector_search.column("Score", width=120, anchor='w', stretch=tk.NO)
        self.tree_vector_search.heading("Title", text="Document Title", anchor='w')
        self.tree_vector_search.column("Title", width=800, anchor='w')

        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree_vector_search.yview)
        self.tree_vector_search.configure(yscrollcommand=vsb.set)

        vsb.pack(side="right", fill="y")
        self.tree_vector_search.pack(side="left", fill="both", expand=True)
        Hovertip(self.tree_vector_search, "List of documents sorted by relevance to your query.")

    def perform_vector_search(self, event=None):
        """Обработчик для кнопки векторного поиска."""
        query = self.vector_entry_var.get()
        if not query.strip():
            messagebox.showinfo("Info", "Please enter a search query.")
            return

        print(f"APP: Performing vector search for: '{query}'")
        self.root.config(cursor="watch")  # Показываем курсор ожидания
        self.root.update_idletasks()

        results = self.search_engine.search(query)

        self.root.config(cursor="")  # Возвращаем обычный курсор

        # Очищаем предыдущие результаты
        self.tree_vector_search.delete(*self.tree_vector_search.get_children())

        if not results:
            messagebox.showinfo("No Results", "No relevant documents were found for your query.")
            return

        for res in results:
            file_id = res['file_id']
            score = res['score']
            # Используем наш словарь для получения заголовка по ID
            title = self.doc_titles_map.get(file_id, f"Unknown Title (ID: {file_id})")

            formatted_score = f"{score:.4f}"  # Форматируем для красивого вывода
            values = (formatted_score, title)
            self.tree_vector_search.insert("", "end", values=values)

        print("APP: Vector search complete.")


if __name__ == "__main__":
    load_spacy_model()

    root = tk.Tk()
    app = ManagerApp(root)

    if hasattr(app, 'conn') and app.conn:
        root.mainloop()
    else:
        print("Application failed to initialize due to database connection issues.")
