import tkinter as tk
from tkinter import ttk, messagebox
from idlelib.tooltip import Hovertip
import threading
import queue
import os
import spacy

from search_engine import VectorSearchEngine
from spellchecker import SpellChecker
from watcher import FileSystemWatcher

# --- Constants ---
ROOT_DOCS_FOLDER = "corpus_root"
CHECK_QUEUE_TIME = 5000
NLP_MODEL = None


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
                                 "Please run 'python -m spacy download en_core_web_sm' to use the application.")
            NLP_MODEL = False
            return False
    return NLP_MODEL is not False


class MainApp:
    def __init__(self, root):
        self.root = root
        self.root.title("File System Search Engine")
        self.root.geometry("1100x600")

        self.setup_styles()

        self.search_engine = VectorSearchEngine()
        self.search_engine.load_from_cache()

        self.spell_checker = SpellChecker()
        print("SpellChecker initialized.")

        self.setup_ui()

        self.event_queue = queue.Queue()

        if not os.path.exists(ROOT_DOCS_FOLDER):
            os.makedirs(ROOT_DOCS_FOLDER)
            messagebox.showinfo("Setup",
                                f"Root folder '{ROOT_DOCS_FOLDER}' was created.\nPlease add subfolders and .txt files to it for searching.")

        self.update_index()
        self.start_watcher_thread()
        self.check_queue_for_updates()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    @staticmethod
    def setup_styles():
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", rowheight=25)
        style.configure("Treeview.Heading", font=('TkDefaultFont', 10, 'bold'))

    def setup_ui(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill="both", expand=True)

        top_frame = ttk.Frame(main_frame)
        top_frame.pack(fill="x", pady=5)

        ttk.Label(top_frame, text="Search Query:").pack(side="left", padx=5)
        self.search_var = tk.StringVar()
        entry_search = ttk.Entry(top_frame, textvariable=self.search_var, width=60)
        entry_search.pack(side="left", padx=5, fill="x", expand=True)
        entry_search.bind("<Return>", self.perform_search)
        Hovertip(entry_search, "Enter a phrase and press Enter to search the file system.")

        btn_search = ttk.Button(top_frame, text="Search", command=self.perform_search)
        btn_search.pack(side="left", padx=5)
        Hovertip(btn_search, "Click to start the search.")

        self.suggestion_label = tk.Label(main_frame, text="", fg="blue", cursor="hand2")
        self.suggestion_label.pack(pady=(0, 5), anchor='w', padx=5)

        self.status_var = tk.StringVar(value="Index loaded. Ready to search.")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        table_frame = ttk.Frame(main_frame)
        table_frame.pack(pady=5, fill="both", expand=True)

        columns = ("Score", "Title", "Path", "Snippet")
        self.tree_results = ttk.Treeview(table_frame, columns=columns, show="headings")
        self.tree_results.heading("Score", text="Relevance", anchor='w')
        self.tree_results.column("Score", width=100, anchor='w', stretch=tk.NO)
        self.tree_results.heading("Title", text="Filename", anchor='w')
        self.tree_results.column("Title", width=200, anchor='w')
        self.tree_results.heading("Path", text="Location", anchor='w')
        self.tree_results.column("Path", width=250, anchor='w')
        self.tree_results.heading("Snippet", text="Snippet", anchor='w')
        self.tree_results.column("Snippet", width=400, anchor='w')

        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree_results.yview)
        hsb = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree_results.xview)
        self.tree_results.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        vsb.pack(side="right", fill="y")
        hsb.pack(side="bottom", fill="x")
        self.tree_results.pack(side="left", fill="both", expand=True)

        self.tooltip_window = None
        self.tooltip_label = None
        self.tree_results.bind("<Motion>", self.on_mouse_move_in_tree)
        self.tree_results.bind("<Leave>", self.hide_tooltip)
        self.tree_results.bind("<ButtonPress>", self.hide_tooltip)

    def update_index(self):
        """Asks the search engine to sync its index with the file system."""
        self.status_var.set("Synchronizing index with file system...")
        self.root.config(cursor="watch")
        self.root.update_idletasks()
        changed = self.search_engine.sync_index_with_filesystem(ROOT_DOCS_FOLDER)
        self.root.config(cursor="")
        self.status_var.set(
            "Index is up-to-date. Ready to search." if not changed else "Index updated. Ready to search.")

    def start_watcher_thread(self):
        """Starts the file monitoring in a separate, non-blocking thread."""
        self.watcher = FileSystemWatcher(path=ROOT_DOCS_FOLDER, event_queue=self.event_queue)
        self.thread = threading.Thread(target=self.watcher.run, daemon=True)
        self.thread.start()

    def check_queue_for_updates(self):
        """Checks the queue for messages from the watcher thread."""
        try:
            if self.event_queue.get_nowait() == "rescan_needed":
                self.status_var.set("File change detected! Updating index...")
                self.update_index()
        except queue.Empty:
            pass
        finally:
            self.root.after(CHECK_QUEUE_TIME, self.check_queue_for_updates)

    def perform_search(self, event=None):
        query = self.search_var.get()
        if not query.strip(): return

        self.suggestion_label.config(text="")
        self.suggestion_label.unbind("<Button-1>")

        words = query.lower().split()
        misspelled = self.spell_checker.unknown(words)

        if misspelled:
            corrected_query = " ".join(self.spell_checker.correction(word) or word for word in words)

            if corrected_query != query.lower():
                suggestion_text = f"Did you mean: {corrected_query}?"
                self.suggestion_label.config(text=suggestion_text)
                self.suggestion_label.bind("<Button-1>", lambda e: self.use_suggestion(corrected_query))

        self.root.config(cursor="watch")
        self.status_var.set(f"Searching for: '{query}'...")
        self.root.update_idletasks()

        results = self.search_engine.search(query)

        self.root.config(cursor="")
        self.tree_results.delete(*self.tree_results.get_children())

        if not results:
            self.status_var.set(f"No results found for: '{query}'")
            return

        for res in results:
            path_parts = res['path'].split(os.sep)
            short_path = os.path.join(*path_parts[-2:]) if len(path_parts) > 1 else path_parts[-1]
            values = (f"{res['score']:.4f}", res['title'], short_path, res.get('snippet', '...'))
            self.tree_results.insert("", "end", values=values, iid=res['path'])

        self.status_var.set(f"Found {len(results)} results. Ready for new search.")

    def use_suggestion(self, corrected_query):
        """Updates the search bar with the corrected query and runs the search again."""
        print(f"Using suggestion: '{corrected_query}'")
        self.search_var.set(corrected_query)
        self.perform_search()

    def on_mouse_move_in_tree(self, event):
        row_id = self.tree_results.identify_row(event.y)
        if row_id:
            try:
                if self.tooltip_window is None:
                    self.tooltip_window = tk.Toplevel(self.root)
                    self.tooltip_window.overrideredirect(True)
                    self.tooltip_label = tk.Label(self.tooltip_window, text="", justify='left',
                                                  background="lightyellow", relief='solid', borderwidth=1,
                                                  wraplength=500, padx=5, pady=5)
                    self.tooltip_label.pack()
                    self.tooltip_window.withdraw()

                values = self.tree_results.item(row_id, 'values')
                full_path = row_id
                full_text = f"Snippet: {values[3]}\n\nFile: {values[1]}\nFull Path: {full_path}"

                self.tooltip_label.config(text=full_text)
                self.tooltip_window.geometry(f"+{event.x_root + 20}+{event.y_root + 10}")
                self.tooltip_window.deiconify()
            except (IndexError, tk.TclError):
                self.hide_tooltip()
        else:
            self.hide_tooltip()

    def hide_tooltip(self, event=None):
        if self.tooltip_window:
            self.tooltip_window.withdraw()

    def on_closing(self):
        print("Application shutting down.")
        if hasattr(self, 'watcher'): self.watcher.stop()
        self.root.destroy()


if __name__ == "__main__":
    if load_spacy_model():
        root = tk.Tk()
        app = MainApp(root)
        root.mainloop()
    else:
        messagebox.showerror("Fatal Error", "spaCy model 'en_core_web_sm' not found. "
                                            "The application cannot start.\n\n"
                                            "Please run 'python -m spacy download en_core_web_sm' and restart.")
