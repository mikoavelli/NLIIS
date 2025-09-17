import sqlite3
import tkinter as tk
import os
from tkinter import ttk, messagebox, scrolledtext
from idlelib.tooltip import Hovertip

# Logic for analysis and DB operations, required for the text editor
import spacy
from utils import POS_TAG_TRANSLATIONS, beautiful_morph, clean_token

# Our search engine
from search_engine import VectorSearchEngine

VECTOR_INDEX_CACHE = "vector_index.pkl" # Filename for the index cache
NLP_MODEL = None                        # Global variable for the spaCy model


def load_spacy_model():
    """Loads the spaCy model required for text re-analysis."""
    global NLP_MODEL
    if NLP_MODEL is None:
        print("Loading spaCy model 'en_core_web_sm' for editor...")
        try:
            NLP_MODEL = spacy.load('en_core_web_sm')
            print("spaCy model loaded successfully.")
            return True
        except OSError:
            messagebox.showerror("spaCy Model Error",
                                 "Model 'en_core_web_sm' not found.\n"
                                 "Text editing will not be available.\n"
                                 "Download it: python -m spacy download en_core_web_sm")
            NLP_MODEL = False
            return False
    return NLP_MODEL is not False


class DBConnection:
    """Class for DB operations, trimmed down to the essentials."""

    def __init__(self, path) -> None:
        try:
            self.db = sqlite3.connect(f"file:{path}?mode=rw", uri=True)
            self.db.row_factory = sqlite3.Row
            self.cursor = self.db.cursor()
            self.cursor.execute("PRAGMA foreign_keys = ON;")
            print(f"Successfully connected to database: {path}")
        except sqlite3.OperationalError as e:
            messagebox.showerror("Database Error", f"Could not connect to database '{path}'.")
            raise

    def get_all_documents_for_indexing(self):
        """Fetches all documents to build the vector index."""
        try:
            self.cursor.execute("SELECT file_id, title, text FROM texts WHERE text IS NOT NULL AND text != ''")
            return [{'file_id': r['file_id'], 'title': r['title'], 'text': r['text']} for r in self.cursor.fetchall()]
        except sqlite3.Error as e:
            print(f"DB Error fetching documents for indexing: {e}")
            return []

    def get_all_texts_summary(self):
        """Gets a list of all texts for the editor's dropdown menu."""
        try:
            self.cursor.execute("SELECT file_id, title FROM texts ORDER BY title COLLATE NOCASE")
            return [{'file_id': r['file_id'], 'title': r['title']} for r in self.cursor.fetchall()]
        except sqlite3.Error as e:
            print(f"Error getting text list: {e}")
            return []

    def get_text_metadata(self, file_id):
        """Gets the text and metadata for a single document by ID."""
        try:
            self.cursor.execute("SELECT * FROM texts WHERE file_id = ?", (file_id,))
            return self.cursor.fetchone()
        except sqlite3.Error as e:
            print(f"Error getting metadata for file_id {file_id}: {e}")
            return None

    def update_text_content_and_reanalyze(self, file_id, new_text):
        """Updates the document text and rebuilds its linguistic annotations."""
        if not load_spacy_model():
            return False, "spaCy model not loaded. Cannot re-analyze."
        try:
            self.cursor.execute("BEGIN TRANSACTION")
            self.cursor.execute("UPDATE texts SET text = ? WHERE file_id = ?", (new_text, file_id))
            self.cursor.execute("DELETE FROM wordforms WHERE file_id = ?", (file_id,))

            doc = NLP_MODEL(new_text)
            wordforms_to_insert = []
            for token in doc:
                cleaned = clean_token(token.text)
                if not cleaned or token.is_space: continue
                pos_tag = POS_TAG_TRANSLATIONS.get(token.pos_, token.pos_)
                morph = beautiful_morph(token.morph.to_dict())
                wordforms_to_insert.append((
                    token.text.lower(), token.lemma_, morph, pos_tag, token.dep_, file_id
                ))
            if wordforms_to_insert:
                self.cursor.executemany(
                    'INSERT INTO wordforms (wordform, lemma, morph, pos, dep, file_id) VALUES (?, ?, ?, ?, ?, ?)',
                    wordforms_to_insert)
            self.db.commit()
            return True, "Text and annotations updated successfully."
        except Exception as e:
            self.db.rollback()
            return False, f"An error occurred during re-analysis: {e}"

    def close(self):
        if self.db:
            self.db.close()
            print("Database connection closed.")


class ManagerApp:
    def __init__(self, root) -> None:
        try:
            self.conn = DBConnection("movies.db")
        except Exception:
            root.destroy()
            return

        self.root = root
        self.root.title("Vector Search System")
        self.root.geometry("1200x700")

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", rowheight=25)
        style.configure("Treeview.Heading", font=('TkDefaultFont', 10, 'bold'))

        self.notebook = ttk.Notebook(root)
        self.notebook.pack(pady=10, padx=10, expand=True, fill="both")

        self.vector_search_frame = ttk.Frame(self.notebook, padding="10")
        self.edit_text_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(self.vector_search_frame, text="Vector Search")
        self.notebook.add(self.edit_text_frame, text="Edit Text Content")

        self.setup_vector_search_tab()
        self.setup_edit_text_tab()

        # --- NEW: Initialize custom tooltip variables ---
        self.tooltip_window = None
        self.last_hovered_row = None

        self.search_engine = VectorSearchEngine()
        self.build_vector_index()

        self.load_texts_list_for_editor()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def on_closing(self):
        self.conn.close()
        self.root.destroy()

    ### VECTOR SEARCH METHODS ###

    def build_vector_index(self):
        """Tries to load the index from cache, otherwise rebuilds it."""
        if self.search_engine.load_index(VECTOR_INDEX_CACHE):
            all_docs = self.conn.get_all_documents_for_indexing()
            self.doc_titles_map = {doc['file_id']: doc['title'] for doc in all_docs}
            print("APP: Vector index loaded from cache.")
            return

        print("APP: Building new vector index...")
        all_docs = self.conn.get_all_documents_for_indexing()
        if not all_docs:
            messagebox.showwarning("Indexing Warning", "No documents found to build a search index.")
            return

        self.doc_titles_map = {doc['file_id']: doc['title'] for doc in all_docs}
        self.search_engine.build_index(all_docs)
        self.search_engine.save_index(VECTOR_INDEX_CACHE)
        print("APP: Vector index is ready and saved to cache.")

    def setup_vector_search_tab(self):
        frame = self.vector_search_frame
        top_frame = ttk.Frame(frame)
        top_frame.pack(fill="x", pady=5)

        ttk.Label(top_frame, text="Full-text query:").pack(side="left", padx=5)
        self.vector_entry_var = tk.StringVar()
        entry_search = ttk.Entry(top_frame, textvariable=self.vector_entry_var, width=60)
        entry_search.pack(side="left", padx=5, fill="x", expand=True)
        entry_search.bind("<Return>", self.perform_vector_search)
        Hovertip(entry_search, "Enter a phrase or sentence to find relevant documents.\nPress Enter to search.")

        btn_search = ttk.Button(top_frame, text="Search Documents", command=self.perform_vector_search)
        btn_search.pack(side="left", padx=5)
        Hovertip(btn_search, "Click to start the search.")

        ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=10)
        ttk.Label(frame, text="Relevant Documents:", font=('TkDefaultFont', 10, 'bold')).pack(pady=5, anchor="w")

        table_frame = ttk.Frame(frame)
        table_frame.pack(pady=5, fill="both", expand=True)

        columns = ("Score", "Title", "Snippet")
        self.tree_vector_search = ttk.Treeview(table_frame, columns=columns, show="headings")
        self.tree_vector_search.heading("Score", text="Relevance", anchor='w')
        self.tree_vector_search.column("Score", width=120, anchor='w', stretch=tk.NO)
        self.tree_vector_search.heading("Title", text="Document Title", anchor='w')
        self.tree_vector_search.column("Title", width=300, anchor='w')
        self.tree_vector_search.heading("Snippet", text="Snippet", anchor='w')
        self.tree_vector_search.column("Snippet", width=600, anchor='w')

        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree_vector_search.yview)
        hsb = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree_vector_search.xview)
        self.tree_vector_search.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        vsb.pack(side="right", fill="y")
        hsb.pack(side="bottom", fill="x")
        self.tree_vector_search.pack(side="left", fill="both", expand=True)

        # --- MODIFIED: Remove old tooltip and add dynamic mouse events ---
        self.tree_vector_search.bind("<Motion>", self.on_mouse_move_in_tree)
        self.tree_vector_search.bind("<Leave>", self.hide_tooltip)
        self.tree_vector_search.bind("<ButtonPress>", self.hide_tooltip)

    def perform_vector_search(self, event=None):
        query = self.vector_entry_var.get()
        if not query.strip(): return

        self.root.config(cursor="watch")
        self.root.update_idletasks()
        results = self.search_engine.search(query)
        self.root.config(cursor="")

        self.tree_vector_search.delete(*self.tree_vector_search.get_children())
        if not results:
            messagebox.showinfo("No Results", "No relevant documents were found.")
            return

        for res in results:
            title = self.doc_titles_map.get(res['file_id'], f"ID: {res['file_id']}")
            values = (f"{res['score']:.4f}", title, res.get('snippet', '...').replace('\n', ' '))
            self.tree_vector_search.insert("", "end", values=values)

    def rebuild_vector_index_and_clear_cache(self):
        """Deletes the old cache and triggers a full index rebuild."""
        print("APP: Rebuilding vector index due to data changes...")
        if os.path.exists(VECTOR_INDEX_CACHE):
            try:
                os.remove(VECTOR_INDEX_CACHE)
                print(f"APP: Removed outdated cache file: {VECTOR_INDEX_CACHE}")
            except OSError as e:
                print(f"APP: Error removing cache file: {e}")
        self.build_vector_index()

    ### DYNAMIC TOOLTIP METHODS ###

    def on_mouse_move_in_tree(self, event):
        """Shows a tooltip with the full snippet text when hovering over a row."""
        row_id = self.tree_vector_search.identify_row(event.y)

        if row_id and row_id != self.last_hovered_row:
            self.last_hovered_row = row_id
            try:
                values = self.tree_vector_search.item(row_id, 'values')
                snippet_text = values[2]  # Snippet is the 3rd column (index 2)

                if not self.tooltip_window:
                    # Create the tooltip window once
                    self.tooltip_window = tk.Toplevel(self.root)
                    self.tooltip_window.overrideredirect(True)  # No title bar
                    self.tooltip_label = tk.Label(self.tooltip_window, text="", justify='left',
                                                  background="lightyellow", relief='solid', borderwidth=1,
                                                  wraplength=500)  # Wrap long text
                    self.tooltip_label.pack(ipadx=5, ipady=5)

                # Update text and position
                self.tooltip_label.config(text=snippet_text)
                self.tooltip_window.geometry(f"+{event.x_root + 20}+{event.y_root + 10}")
                self.tooltip_window.deiconify()  # Show the window
            except (IndexError, tk.TclError):
                self.hide_tooltip()  # Hide if there's an error getting data

        elif not row_id:
            self.hide_tooltip()

    def hide_tooltip(self, event=None):
        """Hides the custom tooltip window."""
        self.last_hovered_row = None
        if self.tooltip_window:
            self.tooltip_window.withdraw()  # Hide the window

    ### TEXT EDITING METHODS ###

    def setup_edit_text_tab(self):
        frame = self.edit_text_frame
        selector_frame = ttk.Frame(frame)
        selector_frame.pack(fill="x", pady=10)
        ttk.Label(selector_frame, text="Select Text:").pack(side="left", padx=5)

        self.edit_text_doc_selector_var = tk.StringVar()
        self.edit_text_doc_selector_combo = ttk.Combobox(selector_frame, textvariable=self.edit_text_doc_selector_var,
                                                         state="readonly", width=50)
        self.edit_text_doc_selector_combo.pack(side="left", padx=5, fill="x", expand=True)
        self.edit_text_doc_selector_combo.bind("<<ComboboxSelected>>", self.load_text_for_editing)
        Hovertip(self.edit_text_doc_selector_combo, "Choose a document from the list to view and edit its content.")

        text_frame = ttk.LabelFrame(frame, text="Text Content", padding="10")
        text_frame.pack(pady=10, fill="both", expand=True)

        self.text_edit_widget = scrolledtext.ScrolledText(text_frame, wrap=tk.WORD, undo=True)
        self.text_edit_widget.pack(fill="both", expand=True)
        Hovertip(self.text_edit_widget,
                 "Edit the text content of the selected document here.\nUndo/Redo is available (Ctrl+Z / Ctrl+Y).")

        btn_save = ttk.Button(frame, text="Save Text and Re-analyze", command=self.save_and_reanalyze_text)
        btn_save.pack(pady=10)
        Hovertip(btn_save,
                 "WARNING: This action updates the database, deletes old annotations,\nand triggers a full rebuild of the search index, which may take time.")

    def load_texts_list_for_editor(self):
        self.texts_list = self.conn.get_all_texts_summary()
        titles = [t['title'] if t['title'] else f"ID: {t['file_id']}" for t in self.texts_list]
        self.edit_text_doc_selector_combo['values'] = titles
        if titles: self.edit_text_doc_selector_combo.current(0)
        self.load_text_for_editing()

    def get_selected_file_id_for_editor(self):
        selected_title = self.edit_text_doc_selector_var.get()
        if not selected_title: return None
        for text_info in self.texts_list:
            display_title = text_info['title'] if text_info['title'] else f"ID: {text_info['file_id']}"
            if display_title == selected_title:
                return text_info['file_id']
        return None

    def load_text_for_editing(self, event=None):
        self.current_edit_text_file_id = self.get_selected_file_id_for_editor()
        self.text_edit_widget.delete('1.0', tk.END)
        self.text_edit_widget.edit_reset()
        if self.current_edit_text_file_id is not None:
            metadata = self.conn.get_text_metadata(self.current_edit_text_file_id)
            if metadata and metadata['text'] is not None:
                self.text_edit_widget.insert('1.0', metadata['text'])

    def save_and_reanalyze_text(self):
        if not hasattr(self, 'current_edit_text_file_id') or self.current_edit_text_file_id is None:
            return

        new_text = self.text_edit_widget.get('1.0', tk.END).strip()
        if not messagebox.askyesno("Confirm Action",
                                   "This will update the database and require a full rebuild of the search index.\nThis action cannot be undone. Continue?"):
            return

        self.root.config(cursor="watch");
        self.root.update_idletasks()
        success, message = self.conn.update_text_content_and_reanalyze(self.current_edit_text_file_id, new_text)
        self.root.config(cursor="")

        if success:
            messagebox.showinfo("Success", message)
            self.text_edit_widget.edit_reset()
            self.rebuild_vector_index_and_clear_cache()
        else:
            messagebox.showerror("Error", message)


if __name__ == "__main__":
    if load_spacy_model():
        root = tk.Tk()
        app = ManagerApp(root)
        root.mainloop()
    else:
        print("Application cannot start without the spaCy model for the text editor.")
