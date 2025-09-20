import io
import os
import nltk
import json
import spacy
import tkinter as tk
from bs4 import BeautifulSoup
from PIL import Image, ImageTk
from idlelib.tooltip import Hovertip
from tkinter import ttk, messagebox, filedialog, scrolledtext
from nltk.corpus import wordnet as wn

try:
    wn.synsets('dog', pos=wn.NOUN)
    print("WordNet data found.")
except LookupError:
    print("WordNet data not found. Attempting to download...")
    try:
        nltk.download('punkt')
        nltk.download('averaged_perceptron_tagger')
        nltk.download('wordnet', quiet=True)
        nltk.download('omw-1.4', quiet=True)
        wn.synsets('dog', pos=wn.NOUN)
        print("WordNet data downloaded successfully.")
    except Exception as e:
        print(f"--- ERROR: Failed to download WordNet data: {e} ---")
        print("Synonyms, Antonyms, and Definitions will not be available.")
        print("Please run 'import nltk; nltk.download(\"wordnet\"); nltk.download(\"omw-1.4\")' manually in Python.")
        messagebox.showwarning("WordNet Missing",
                               "WordNet data not found or failed to download.\nSemantic features (Synonyms, Antonyms, Definitions) will be unavailable.\nSee console for details.")
except Exception as e:
    print(f"An unexpected error occurred while checking/loading WordNet: {e}")

SVG_RENDERER = None
try:
    import cairosvg

    SVG_RENDERER = 'cairosvg'
    print("Found SVG renderer: cairosvg")
except ImportError:
    try:
        from svglib.svglib import svg2rlg
        from reportlab.graphics import renderPM

        SVG_RENDERER = 'svglib'
        print("Found SVG renderer: svglib/reportlab")
    except ImportError:
        print("--- WARNING: SVG renderer (cairosvg or svglib) not found. ---")
        print("Dependency trees will not be displayed.")
        print("Recommended installation: pip install cairosvg")
        print("-" * 60)

try:
    from utils import POS_TAG_TRANSLATIONS, beautiful_morph, clean_token
except ImportError:
    print("Error: utils.py not found. Please create it.")
    POS_TAG_TRANSLATIONS = {}


    def beautiful_morph(d):
        return str(d) if d else "None"


    def clean_token(t):
        return t.strip()

try:
    from utils import POS_TAG_TRANSLATIONS, beautiful_morph, clean_token
except ImportError:
    print("Error: utils.py not found. Using placeholder functions.")
    POS_TAG_TRANSLATIONS = {}


    def beautiful_morph(d):
        return str(d) if d else "None"


    def clean_token(t):
        return t.strip()

SPACY_MODEL_NAME = 'en_core_web_sm'
NLP = None


class SessionAnalysisApp:
    def __init__(self, root):
        self.root = root
        self.root.title("HTML Text Analyzer (Session)")
        self.root.geometry("1500x1600")

        self.current_html_path = ""
        self.original_text = ""
        self.analyzed_doc = None
        self.analysis_overrides = {}
        self.tree_token_map = {}

        self._load_spacy_model()
        self._setup_styles()
        self._create_widgets()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    @staticmethod
    def _load_spacy_model():
        global NLP
        if NLP is None:
            print(f"Loading spaCy model '{SPACY_MODEL_NAME}'...")
            try:
                NLP = spacy.load(SPACY_MODEL_NAME)
                print("spaCy model loaded successfully.")
            except OSError:
                messagebox.showerror(
                    "spaCy Error",
                    f"Model '{SPACY_MODEL_NAME}' not found.\n"
                    f"Text analysis will not work.\n"
                    f"Download the model: python -m spacy download {SPACY_MODEL_NAME}"
                )
                print(f"!!! Error: Model '{SPACY_MODEL_NAME}' not found. Please install it.")
            except Exception as e:
                messagebox.showerror("spaCy Error", f"Could not load spaCy model:\n{e}")
                print(f"!!! spaCy loading error: {e}")

    @staticmethod
    def _setup_styles():
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            style.theme_use("default")
        style.configure("Treeview", rowheight=30, font=('TkDefaultFont', 10))
        style.configure("Treeview.Heading", font=('TkDefaultFont', 11, 'bold'))
        style.configure("TLabel", font=('TkDefaultFont', 10))
        style.configure("TButton", font=('TkDefaultFont', 10), padding=5)
        style.configure("TEntry", font=('TkDefaultFont', 10), padding=5)
        style.configure("TLabelframe.Label", font=('TkDefaultFont', 10, 'bold'))

    def _create_widgets(self):
        file_frame = ttk.LabelFrame(self.root, text="Input Text", padding="10")
        file_frame.pack(padx=10, pady=(10, 5), fill="x")
        btn_load = ttk.Button(file_frame, text="Load HTML File", command=self.load_html_file)
        btn_load.pack(side="left", padx=(0, 10))
        Hovertip(btn_load, "Select an HTML file to extract and load its text content.")
        self.loaded_file_label = ttk.Label(file_frame, text="No file loaded.", width=60, relief="sunken", anchor="w")
        self.loaded_file_label.pack(side="left", padx=5, fill="x", expand=True)
        Hovertip(self.loaded_file_label, "Path of the currently loaded HTML file.")
        btn_analyze = ttk.Button(file_frame, text="Analyze Current Text", command=self.analyze_text)
        btn_analyze.pack(side="left", padx=5)
        Hovertip(btn_analyze, "Perform linguistic analysis (POS tagging, dependency parsing) on the text below.")

        text_frame = ttk.LabelFrame(self.root, text="Text Content (Editable)", padding="10")
        text_frame.pack(padx=10, pady=5, fill="x", expand=False)
        self.text_edit_widget = scrolledtext.ScrolledText(text_frame, wrap=tk.WORD, height=10,
                                                          font=('TkDefaultFont', 10),
                                                          undo=True)
        self.text_edit_widget.pack(fill="both", expand=True, pady=(0, 5))
        Hovertip(self.text_edit_widget, "Edit text here. Use 'Re-analyze' after modification.")
        btn_reanalyze = ttk.Button(text_frame, text="Re-analyze Edited Text", command=self.reanalyze_edited_text)
        btn_reanalyze.pack(side="bottom", pady=(5, 0))
        Hovertip(btn_reanalyze, "Re-run analysis on modified text. This resets manual overrides.")

        search_filter_frame = ttk.LabelFrame(self.root, text="Filter Analysis Results", padding="10")
        search_filter_frame.pack(padx=10, pady=5, fill="x")
        ttk.Label(search_filter_frame, text="Filter by:").pack(side="left", padx=(0, 5))
        self.search_filter_var = tk.StringVar()
        entry_filter = ttk.Entry(search_filter_frame, textvariable=self.search_filter_var, width=40)
        entry_filter.pack(side="left", padx=5, fill="x", expand=True)
        Hovertip(entry_filter,
                 "Enter text to filter rows (searches Token, Lemma, POS, Morphology, Dependency). Case-insensitive.")
        entry_filter.bind("<Return>", self.filter_analysis_results)
        btn_filter = ttk.Button(search_filter_frame, text="Filter", command=self.filter_analysis_results)
        btn_filter.pack(side="left", padx=5)
        Hovertip(btn_filter, "Apply the filter to the analysis table.")
        btn_clear_filter = ttk.Button(search_filter_frame, text="Clear Filter", command=self.clear_filter)
        btn_clear_filter.pack(side="left", padx=5)
        Hovertip(btn_clear_filter, "Remove the filter and show all analyzed tokens.")

        results_frame = ttk.LabelFrame(self.root, text="Analysis Results (Editable)", padding="10")
        results_frame.pack(padx=10, pady=5, fill="both", expand=True)

        cols = ("ID", "Token", "Lemma", "POS", "Morphology", "Dependency", "Synonyms", "Antonyms", "Definition")
        self.analysis_tree = ttk.Treeview(results_frame, columns=cols, show="headings", height=15)
        col_widths = {"ID": 40, "Token": 110, "Lemma": 110, "POS": 100, "Morphology": 180, "Dependency": 100,
                      "Synonyms": 150, "Antonyms": 150, "Definition": 250}

        for col in cols:
            self.analysis_tree.heading(col, text=col, anchor='w')
            stretch = tk.NO if col == "ID" else tk.YES
            self.analysis_tree.column(col, width=col_widths[col], anchor='w', stretch=stretch)

        vsb = ttk.Scrollbar(results_frame, orient="vertical", command=self.analysis_tree.yview)
        hsb = ttk.Scrollbar(results_frame, orient="horizontal", command=self.analysis_tree.xview)
        self.analysis_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side="right", fill="y")
        hsb.pack(side="bottom", fill="x")
        self.analysis_tree.pack(side="top", fill="both", expand=True)
        Hovertip(self.analysis_tree,
                 "Linguistic analysis results.\nDouble-click a row to edit core fields. Semantic info from WordNet.")
        self.analysis_tree.bind("<Double-1>", self.open_wordform_edit_window)

        analysis_buttons_frame = ttk.Frame(self.root, padding=(10, 5, 10, 10))
        analysis_buttons_frame.pack(fill="x", side="bottom")
        btn_export = ttk.Button(analysis_buttons_frame, text="Export Selected", command=self.export_selected_wordform)
        btn_export.pack(side="left", padx=5)
        Hovertip(btn_export, "Export analysis of the selected token to JSON.")
        btn_import = ttk.Button(analysis_buttons_frame, text="Import Overrides", command=self.import_wordform_overrides)
        btn_import.pack(side="left", padx=5)
        Hovertip(btn_import, "Import analysis overrides from JSON.")
        btn_delete = ttk.Button(analysis_buttons_frame, text="Ignore Selected", command=self.ignore_selected_wordform)
        btn_delete.pack(side="left", padx=5)
        Hovertip(btn_delete, "Mark selected token as ignored.")
        btn_show_tree = ttk.Button(analysis_buttons_frame, text="Show Dependency Tree",
                                   command=self.show_dependency_tree_window)
        btn_show_tree.pack(side="left", padx=5)
        Hovertip(btn_show_tree, "Show the dependency parse tree in a new window.")

    def filter_analysis_results(self, event=None):
        query = self.search_filter_var.get().lower().strip()
        print(f"Filtering analysis table with query: '{query}'")

        self._populate_analysis_table()

        if not query:
            print("Filter query is empty, showing all rows.")
            return

        all_iids = list(self.analysis_tree.get_children(''))
        iids_to_remove = []

        for iid in all_iids:
            try:
                values = self.analysis_tree.item(iid, 'values')
                match_found = False
                for col_index in range(1, len(values)):
                    value_str = str(values[col_index]).lower()
                    if query in value_str:
                        match_found = True
                        break
                if not match_found:
                    iids_to_remove.append(iid)
            except tk.TclError:
                print(f"Warning: Could not get values for item {iid} during filtering.")
                continue

        if iids_to_remove:
            print(f"Removing {len(iids_to_remove)} non-matching rows.")
            for iid_to_remove in iids_to_remove:
                if self.analysis_tree.exists(iid_to_remove):
                    self.analysis_tree.delete(iid_to_remove)
        else:
            print("No rows to remove.")

    def clear_filter(self):
        print("Clearing filter.")
        self.search_filter_var.set("")
        self._populate_analysis_table()

    def load_html_file(self):
        filepath = filedialog.askopenfilename(
            title="Select HTML File",
            filetypes=[("HTML files", "*.htm *.html"), ("All files", "*.*")]
        )
        if not filepath: return
        print(f"Loading HTML: {filepath}")
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                soup = BeautifulSoup(f, 'html.parser')
            extracted_text = soup.get_text(separator='\n', strip=True)
            if not extracted_text:
                messagebox.showwarning("Empty Text", "Could not extract text from the HTML file.")
                self.original_text = ""
                self.current_html_path = ""
            else:
                self.original_text = extracted_text
                self.current_html_path = filepath
                print(f"Extracted characters: {len(self.original_text)}")
            self.text_edit_widget.delete('1.0', tk.END)
            self.text_edit_widget.insert('1.0', self.original_text)
            self.text_edit_widget.edit_reset()
            self.loaded_file_label.config(text=os.path.basename(filepath))
            Hovertip(self.loaded_file_label, filepath)
            self.analyzed_doc = None
            self.analysis_overrides = {}
            self.tree_token_map = {}
            self.analysis_tree.delete(*self.analysis_tree.get_children())
        except Exception as e:
            messagebox.showerror("Error Loading HTML", f"Could not load/parse HTML:\n{e}")
            self.original_text = ""
            self.current_html_path = ""
            self.loaded_file_label.config(text="Error loading file.")

    def analyze_text(self):
        global NLP
        if NLP is None:
            messagebox.showerror("Error", "spaCy model not loaded.")
            return
        text_to_analyze = self.text_edit_widget.get('1.0', tk.END).strip()
        if not text_to_analyze:
            messagebox.showwarning("Empty Text", "No text to analyze.")
            return
        self.original_text = text_to_analyze
        self.analysis_overrides = {}
        print("Starting text analysis...")
        self.root.config(cursor="watch")
        self.root.update_idletasks()
        try:
            self.analyzed_doc = NLP(self.original_text)
            print(f"Analysis complete. Tokens: {len(self.analyzed_doc)}")
            self._populate_analysis_table()
        except Exception as e:
            messagebox.showerror("Analysis Error", f"Error during analysis:\n{e}")
            print(f"!!! spaCy analysis error: {e}")
            self.analyzed_doc = None
            self.analysis_tree.delete(*self.analysis_tree.get_children())
        finally:
            self.root.config(cursor="")

    def reanalyze_edited_text(self):
        print("Re-analyzing text from editor...")
        self.analyze_text()

    def _populate_analysis_table(self):
        """Populates the analysis table with data from spaCy doc and WordNet."""
        self.analysis_tree.delete(*self.analysis_tree.get_children())
        self.tree_token_map.clear()
        if not self.analyzed_doc: return

        print("Populating analysis table (including WordNet lookup)...")
        visible_token_count = 0
        wordnet_errors = 0

        for i, token in enumerate(self.analyzed_doc):
            cleaned = clean_token(token.text)
            if not cleaned or token.is_space: continue

            override = self.analysis_overrides.get(i, {})
            if override.get("deleted", False): continue

            wordform = override.get("wordform", token.text).replace("\n", " ")
            lemma = override.get("lemma", token.lemma_).replace("\n", " ")
            pos_tag = override.get("pos", POS_TAG_TRANSLATIONS.get(token.pos_, token.pos_)).replace("\n", " ")
            morph_str = override.get("morph", beautiful_morph(token.morph.to_dict())).replace("\n", " ")
            dep_rel = override.get("dep", token.dep_).replace("\n", " ")

            wordnet_info = {"synonyms": "N/A", "antonyms": "N/A", "definition": "N/A"}
            try:
                lookup_lemma = override.get("lemma", token.lemma_)
                original_spacy_pos = token.pos_
                if original_spacy_pos in ['NOUN', 'VERB', 'ADJ', 'ADV']:
                    wordnet_info = self._get_wordnet_info(lookup_lemma, original_spacy_pos)
            except Exception as e:
                if wordnet_errors == 0:
                    print(
                        f"Warning: WordNet lookup failed for '{lemma}' ({original_spacy_pos}). Error: {e}. Further errors suppressed.")
                wordnet_errors += 1

            iid = f"token_{i}"
            self.tree_token_map[iid] = i
            values = (
                i,
                wordform,
                lemma,
                pos_tag,
                morph_str,
                dep_rel,
                wordnet_info["synonyms"],
                wordnet_info["antonyms"],
                wordnet_info["definition"]
            )
            self.analysis_tree.insert("", "end", values=values, iid=iid)
            visible_token_count += 1

        print(f"Analysis table populated. Displayed tokens: {visible_token_count}. WordNet errors: {wordnet_errors}")

    def _render_dependency_tree(self, target_label_widget, sentence_index=0):
        global SVG_RENDERER
        target_label_widget.image_tk = None
        if not self.analyzed_doc:
            message = "Analysis needed."
            target_label_widget.config(image="", text=message)
            print(message)
            return False
        if not SVG_RENDERER:
            message = "SVG renderer missing."
            target_label_widget.config(image="", text=message)
            print(message)
            return False

        sentences = list(self.analyzed_doc.sents)
        if not sentences or sentence_index < 0 or sentence_index >= len(sentences):
            message = f"Sentence index {sentence_index} out of bounds (0-{len(sentences) - 1})."
            target_label_widget.config(image="", text=message)
            print(message)
            return False

        sentence_to_render = sentences[sentence_index]
        print(f"Rendering tree for sentence {sentence_index}...")

        svg_options = {
            "compact": False,
            "font": "Arial",
            "bg": "#fafafa",
            "color": "#000000",
            "word_spacing": 45,
            "arrow_spacing": 20
        }
        render_dpi = 100

        try:
            svg_code = spacy.displacy.render(sentence_to_render, style="dep", jupyter=False, options=svg_options)
            png_bytes = None

            if SVG_RENDERER == 'cairosvg':
                try:
                    png_bytes = cairosvg.svg2png(bytestring=svg_code.encode('utf-8'), dpi=render_dpi)
                except Exception as e:
                    print(f"cairosvg error: {e}")
            elif SVG_RENDERER == 'svglib':
                try:
                    drawing = svg2rlg(io.BytesIO(svg_code.encode('utf-8')))
                    if drawing:
                        png_bytes_io = io.BytesIO()
                        renderPM.drawToFile(drawing, png_bytes_io, fmt="PNG")
                        png_bytes = png_bytes_io.getvalue()
                    else:
                        print("svglib failed to create drawing.")
                except Exception as e:
                    print(f"svglib/reportlab error: {e}")

            if png_bytes:
                img = Image.open(io.BytesIO(png_bytes))
                image_tk = ImageTk.PhotoImage(img)
                target_label_widget.image_tk = image_tk
                target_label_widget.config(image=image_tk, text="")
                print("Dependency tree rendered.")
                return True
            else:
                message = "Failed to convert SVG to PNG."
                target_label_widget.config(image="", text=message)
                print(message)
                return False
        except Exception as e:
            message = f"Error rendering tree:\n{e}"
            target_label_widget.config(image="", text=message)
            print(f"Error during tree rendering: {e}")
            return False

    def show_dependency_tree_window(self):
        if not self.analyzed_doc:
            messagebox.showwarning("No Analysis", "Please analyze the text first.")
            return
        popup = tk.Toplevel(self.root)
        popup.title("Dependency Parse Tree")
        popup.geometry("900x600")
        popup.transient(self.root)
        control_frame = ttk.Frame(popup, padding=5)
        control_frame.pack(fill="x")
        ttk.Label(control_frame, text="Sentence Index:").pack(side="left", padx=5)
        vcmd = (popup.register(self._validate_int_input), '%P')
        self.sent_index_var = tk.StringVar(value="0")
        sent_index_entry = ttk.Entry(control_frame, textvariable=self.sent_index_var, width=5, validate='key',
                                     validatecommand=vcmd)
        sent_index_entry.pack(side="left", padx=5)
        Hovertip(sent_index_entry, "Enter sentence index (starts from 0).")
        canvas_widget, tree_label_widget = self._create_scrolled_image_widget(popup)
        btn_update_tree = ttk.Button(control_frame, text="Update Tree",
                                     command=lambda: self._update_tree_in_popup(popup, canvas_widget,
                                                                                tree_label_widget))
        btn_update_tree.pack(side="left", padx=5)
        Hovertip(btn_update_tree, "Render tree for the specified index.")
        self._update_tree_in_popup(popup, canvas_widget, tree_label_widget)

    @staticmethod
    def _create_scrolled_image_widget(parent_widget):
        tree_label_frame = ttk.Frame(parent_widget, relief="sunken", borderwidth=1)
        tree_label_frame.pack(fill="both", expand=True, padx=5, pady=5)
        canvas = tk.Canvas(tree_label_frame, bg='white')
        h_scroll = ttk.Scrollbar(tree_label_frame, orient=tk.HORIZONTAL, command=canvas.xview)
        v_scroll = ttk.Scrollbar(tree_label_frame, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(xscrollcommand=h_scroll.set, yscrollcommand=v_scroll.set)
        h_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_label = ttk.Label(canvas, anchor="nw", background="white")
        canvas.create_window((0, 0), window=tree_label, anchor="nw", tags="image_label")
        tree_label.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        return canvas, tree_label

    @staticmethod
    def _validate_int_input(P):
        return str.isdigit(P) or P == ""

    def _update_tree_in_popup(self, popup_window, target_canvas, target_label):
        try:
            sent_index = int(self.sent_index_var.get())
        except ValueError:
            messagebox.showerror("Invalid Input", "Enter a valid sentence index.", parent=popup_window)
            return
        success = self._render_dependency_tree(target_label, sent_index)
        if success:
            target_canvas.update_idletasks()
            scroll_bbox = target_canvas.bbox("all")
            if scroll_bbox:
                target_canvas.configure(scrollregion=scroll_bbox)
                print(f"Scrollregion updated: {scroll_bbox}")
            else:
                print("Could not get bbox.")
            target_canvas.xview_moveto(0)
            target_canvas.yview_moveto(0)

    def get_selected_item_details(self):
        selected_items = self.analysis_tree.selection()
        if not selected_items:
            messagebox.showwarning("No Selection", "Select an entry.")
            return None, None
        selected_iid = selected_items[0]
        token_index = self.tree_token_map.get(selected_iid)
        if token_index is None:
            messagebox.showerror("Error", "Could not find token data.")
            return None, None
        return selected_iid, token_index

    def open_wordform_edit_window(self, event):
        selected_iid, token_index = self.get_selected_item_details()
        if selected_iid is None: return
        if not self.analyzed_doc or token_index >= len(self.analyzed_doc):
            messagebox.showerror("Error", "Analysis data is missing or index is out of bounds.")
            return

        token = self.analyzed_doc[token_index]
        current_override = self.analysis_overrides.get(token_index, {})
        print(f"DEBUG: Opening edit window for token {token_index}. Current overrides: {current_override}")

        current_data = {
            "wordform": token.text,
            "lemma": str(current_override.get("lemma", token.lemma_)),
            "pos": str(current_override.get("pos", POS_TAG_TRANSLATIONS.get(token.pos_, token.pos_))),
            "morph": str(current_override.get("morph", beautiful_morph(token.morph.to_dict()))),
            "dep": str(current_override.get("dep", token.dep_))
        }
        print(f"DEBUG: Data for edit window: {current_data}")

        popup = tk.Toplevel(self.root)
        popup.title(f"Edit Token {token_index} ('{current_data['wordform']}')")
        popup.transient(self.root)
        popup.resizable(False, False)

        form_frame = ttk.Frame(popup, padding="15")
        form_frame.pack(expand=True, fill="both")

        ttk.Label(form_frame, text="Original Token:").grid(row=0, column=0, padx=5, pady=8, sticky="w")
        orig_token_label = ttk.Label(form_frame, text=current_data["wordform"], relief="sunken", padding=3, anchor="w")
        orig_token_label.grid(row=0, column=1, padx=5, pady=8, sticky="ew")

        entries = {}
        fields_to_edit = ['lemma', 'pos', 'morph', 'dep']
        labels = {'lemma': 'Lemma:', 'pos': 'POS Tag:', 'morph': 'Morphology:', 'dep': 'Dependency:'}

        for i, field in enumerate(fields_to_edit):
            print(f"DEBUG: Creating widgets for field '{field}' at row {i + 1}")
            lbl = ttk.Label(form_frame, text=labels[field])
            lbl.grid(row=i + 1, column=0, padx=5, pady=8, sticky="w")
            var = tk.StringVar(value=current_data[field])
            entry = ttk.Entry(form_frame, textvariable=var, width=50)
            entry.grid(row=i + 1, column=1, padx=5, pady=8, sticky="ew")
            entries[field] = var
            print(f"DEBUG: Widgets for '{field}' created and placed.")

        form_frame.columnconfigure(1, weight=1)

        button_frame = ttk.Frame(popup, padding=(10, 10, 10, 15))
        button_frame.pack(fill="x", side="bottom")
        save_button = ttk.Button(button_frame, text="Save Changes",
                                 command=lambda: self.save_wordform_edit(token_index, entries, popup))
        save_button.pack(side="right", padx=(10, 0))
        cancel_button = ttk.Button(button_frame, text="Cancel", command=popup.destroy)
        cancel_button.pack(side="right", padx=(0, 5))

        popup.update_idletasks()
        parent_x = self.root.winfo_x()
        parent_y = self.root.winfo_y()
        parent_w = self.root.winfo_width()
        parent_h = self.root.winfo_height()
        popup_w = popup.winfo_width()
        popup_h = popup.winfo_height()
        x = parent_x + (parent_w // 2) - (popup_w // 2)
        y = parent_y + (parent_h // 2) - (popup_h // 2)
        popup.geometry(f'+{x}+{y}')
        first_entry_widget = form_frame.grid_slaves(row=1, column=1)
        if first_entry_widget: first_entry_widget[0].focus_set()
        try:
            if popup.winfo_viewable():
                popup.grab_set()
                print("DEBUG: Grab set.")
            else:
                print("DEBUG: Warning - Popup not viewable for grab_set.")
        except tk.TclError as e:
            print(f"DEBUG: Error during grab_set: {e}")

    def save_wordform_edit(self, token_index, entries, popup_window):
        print(f"Saving overrides for token {token_index}")
        new_override = self.analysis_overrides.get(token_index, {}).copy()
        updated = False
        for field, var in entries.items():
            new_value = var.get().strip()
            original_token = self.analyzed_doc[token_index]
            original_value = None
            if field == 'lemma':
                original_value = original_token.lemma_
            elif field == 'pos':
                original_value = POS_TAG_TRANSLATIONS.get(original_token.pos_, original_token.pos_)
            elif field == 'morph':
                original_value = beautiful_morph(original_token.morph.to_dict())
            elif field == 'dep':
                original_value = original_token.dep_
            else:
                continue

            previous_value = self.analysis_overrides.get(token_index, {}).get(field, original_value)
            if new_value != previous_value:
                if new_value == original_value or new_value == '':
                    if field in new_override:
                        del new_override[field]
                        updated = True
                else:
                    new_override[field] = new_value
                    updated = True

        is_empty_override = not any(f != 'deleted' for f in new_override)
        if is_empty_override:
            if token_index in self.analysis_overrides:
                if "deleted" in self.analysis_overrides[token_index]:
                    if len(self.analysis_overrides[token_index]) > 1:
                        self.analysis_overrides[token_index] = {"deleted": True}
                        updated = True
                    else:
                        pass
                else:
                    del self.analysis_overrides[token_index]
                    updated = True
        elif updated:
            self.analysis_overrides[token_index] = new_override

        popup_window.destroy()
        if updated:
            print(f"Overrides for token {token_index} updated.")
            self._update_treeview_row(token_index)
        else:
            print(f"No changes made for token {token_index}.")

    def ignore_selected_wordform(self):
        selected_iid, token_index = self.get_selected_item_details()
        if selected_iid is None: return
        token_text = self.analyzed_doc[token_index].text if self.analyzed_doc and token_index < len(
            self.analyzed_doc) else ""
        confirm = messagebox.askyesno("Confirm Ignore", f"Mark token {token_index} ('{token_text}') as ignored?",
                                      parent=self.root)
        if confirm:
            print(f"Marking token {token_index} as deleted.")
            override = self.analysis_overrides.get(token_index, {})
            override["deleted"] = True
            self.analysis_overrides[token_index] = override
            self._update_treeview_row(token_index)

    def export_selected_wordform(self):
        """Exports analysis (including WordNet info) of the selected token to JSON."""
        selected_iid, token_index = self.get_selected_item_details()
        if selected_iid is None: return
        if not self.analyzed_doc or token_index >= len(self.analyzed_doc):
            messagebox.showerror("Error", "Analysis data missing.")
            return

        token = self.analyzed_doc[token_index]
        override = self.analysis_overrides.get(token_index, {})

        if override.get("deleted", False):
            messagebox.showinfo("Info", f"Token {token_index} is ignored, not exported.")
            return

        wordnet_info = {"synonyms": "N/A", "antonyms": "N/A", "definition": "N/A"}
        try:
            lookup_lemma = override.get("lemma", token.lemma_)
            original_spacy_pos = token.pos_
            if original_spacy_pos in ['NOUN', 'VERB', 'ADJ', 'ADV']:
                wordnet_info = self._get_wordnet_info(lookup_lemma, original_spacy_pos)
        except Exception as e:
            print(f"Warning: WordNet lookup failed during export for '{lookup_lemma}'. Error: {e}")

        export_entry_data = {
            "original_wordform": token.text,
            "lemma": override.get("lemma", token.lemma_),
            "pos": override.get("pos", POS_TAG_TRANSLATIONS.get(token.pos_, token.pos_)),
            "morph": override.get("morph", beautiful_morph(token.morph.to_dict())),
            "dep": override.get("dep", token.dep_),
            "synonyms": wordnet_info["synonyms"],
            "antonyms": wordnet_info["antonyms"],
            "definition": wordnet_info["definition"],
            "source_doc": os.path.basename(self.current_html_path) if self.current_html_path else "N/A"
        }

        export_key = f"token_{token_index}"
        export_data = {export_key: export_entry_data}

        file_path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON files", "*.json")],
                                                 title="Save Token Analysis As...",
                                                 initialfile=f"token_{token_index}_{clean_token(token.text)}.json")
        if not file_path: return
        existing_data = {}
        file_exists = os.path.exists(file_path)
        try:
            if file_exists:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        existing_data = json.load(f)
                    if not isinstance(existing_data, dict): existing_data = {}
                except (json.JSONDecodeError, IOError):
                    existing_data = {}
                if export_key in existing_data:
                    if not messagebox.askyesno("Overwrite?",
                                               f"Entry '{export_key}' already exists in the file. Overwrite?",
                                               parent=self.root):
                        return
            existing_data[export_key] = export_entry_data
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(existing_data, f, indent=4, ensure_ascii=False)
            messagebox.showinfo("Success", f"Data for '{export_key}' saved to {os.path.basename(file_path)}.")
        except Exception as e:
            messagebox.showerror("Export Error", f"Could not save data:\n{e}")

    def import_wordform_overrides(self):
        if not self.analyzed_doc:
            messagebox.showwarning("No Data", "Analyze text first before importing overrides.")
            return
        file_path = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")],
                                               title="Select JSON File with Overrides")
        if not file_path:
            return
        print(f"Importing overrides from: {file_path}")
        imported_count = 0
        skipped_count = 0
        error_count = 0
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data_to_import = json.load(f)
            if not isinstance(data_to_import, dict):
                messagebox.showerror("Format Error", "JSON file must contain a dictionary.")
                return
            num_entries = len(data_to_import)
            if num_entries == 0:
                messagebox.showinfo("Info", "The selected JSON file is empty.")
                return
            if not messagebox.askyesno("Confirm Import",
                                       f"Found {num_entries} potential overrides in the file.\nApply them to the current session?",
                                       parent=self.root):
                return

            applied_indices = set()
            for key, override_data in data_to_import.items():
                if not key.startswith("token_") or not isinstance(override_data, dict):
                    print(f"Skipping invalid key or data format: {key}")
                    skipped_count += 1
                    continue
                try:
                    token_index = int(key.split("_")[1])
                except (IndexError, ValueError):
                    print(f"Skipping invalid key format (cannot extract index): {key}")
                    skipped_count += 1
                    continue
                if token_index < 0 or token_index >= len(self.analyzed_doc):
                    print(f"Skipping out-of-bounds token index {token_index} from key {key}.")
                    skipped_count += 1
                    continue

                current_override = self.analysis_overrides.get(token_index, {}).copy()
                applied_change_for_token = False
                for field, value in override_data.items():
                    if field in ["lemma", "pos", "morph", "dep", "deleted"]:
                        if value is not None:
                            current_override[field] = str(value).strip()
                            applied_change_for_token = True
                        else:
                            print(f"Warning: Skipping null value for field '{field}' in token {token_index}")

                if applied_change_for_token:
                    self.analysis_overrides[token_index] = current_override
                    applied_indices.add(token_index)
                    imported_count += 1
                else:
                    print(f"Skipping entry {key}, no applicable override fields found.")
                    skipped_count += 1

            print(f"Updating {len(applied_indices)} rows in the analysis table...")
            for index in applied_indices:
                self._update_treeview_row(index)
            print("Table update complete.")

            summary = f"Import finished.\n\nOverrides applied/updated: {imported_count}\nEntries skipped: {skipped_count}"
            messagebox.showinfo("Import Complete", summary)
            print(summary.replace('\n\n', ' // '))

        except FileNotFoundError:
            messagebox.showerror("File Error", f"File not found:\n{file_path}")
        except json.JSONDecodeError as e:
            messagebox.showerror("JSON Error", f"Error decoding JSON file:\n{e}")
        except Exception as e:
            messagebox.showerror("Import Error", f"An unexpected error occurred during import:\n{e}")
            print(f"!!! Import error: {e}")

    def _update_treeview_row(self, token_index):
        """Updates a single row in the Treeview based on current data and overrides."""
        iid = f"token_{token_index}"
        if not self.analysis_tree.exists(iid): return
        if not self.analyzed_doc or token_index >= len(self.analyzed_doc): return

        token = self.analyzed_doc[token_index]
        override = self.analysis_overrides.get(token_index, {})

        if override.get("deleted", False):
            try:
                self.analysis_tree.delete(iid);
                print(f"Removed ignored token {token_index} from view.")
            except tk.TclError:
                pass
            return

        # Get core data
        wordform = token.text.replace("\n", " ")
        lemma = override.get("lemma", token.lemma_).replace("\n", " ")
        pos_tag = override.get("pos", POS_TAG_TRANSLATIONS.get(token.pos_, token.pos_)).replace("\n", " ")
        morph_str = override.get("morph", beautiful_morph(token.morph.to_dict())).replace("\n", " ")
        dep_rel = override.get("dep", token.dep_).replace("\n", " ")

        # Re-fetch WordNet data for the updated row
        wordnet_info = {"synonyms": "N/A", "antonyms": "N/A", "definition": "N/A"}
        try:
            lookup_lemma = override.get("lemma", token.lemma_)
            original_spacy_pos = token.pos_
            if original_spacy_pos in ['NOUN', 'VERB', 'ADJ', 'ADV']:
                wordnet_info = self._get_wordnet_info(lookup_lemma, original_spacy_pos)
        except Exception as e:
            print(f"Warning: WordNet lookup failed during row update for '{lookup_lemma}'. Error: {e}")

        # Prepare values tuple including WordNet data
        values = (
            token_index, wordform, lemma, pos_tag, morph_str, dep_rel,
            wordnet_info["synonyms"], wordnet_info["antonyms"], wordnet_info["definition"]
        )
        try:
            self.analysis_tree.item(iid, values=values)
        except tk.TclError as e:
            print(f"Error updating Treeview item {iid}: {e}")

    def on_closing(self):
        if messagebox.askokcancel("Quit", "Are you sure you want to quit?\nAll unsaved analysis data will be lost."):
            print("Closing application.")
            self.root.destroy()

    def _map_spacy_pos_to_wordnet(self, spacy_pos_tag):
        """Maps spaCy POS tags to WordNet POS tags."""
        if spacy_pos_tag.startswith('NOUN'):
            return wn.NOUN
        elif spacy_pos_tag.startswith('VERB'):
            return wn.VERB
        elif spacy_pos_tag.startswith('ADJ'):
            return wn.ADJ
        elif spacy_pos_tag.startswith('ADV'):
            return wn.ADV
        else:
            return None

    def _get_wordnet_info(self, lemma, spacy_pos_tag):
        wn_pos = self._map_spacy_pos_to_wordnet(spacy_pos_tag)
        if not wn_pos:
            return {"synonyms": "N/A", "antonyms": "N/A", "definition": "N/A"}

        synsets = wn.synsets(lemma, pos=wn_pos)
        if not synsets:
            return {"synonyms": "N/A", "antonyms": "N/A", "definition": "N/A"}

        first_synset = synsets[0]

        definition = first_synset.definition() or "N/A"

        synonyms = set()
        limit = 5
        for lem in first_synset.lemmas():
            syn_name = lem.name().replace('_', ' ')
            if syn_name.lower() != lemma.lower():
                synonyms.add(syn_name)
            if len(synonyms) >= limit: break
        synonyms_str = ", ".join(sorted(list(synonyms))) if synonyms else "N/A"

        antonyms = set()
        limit = 5
        first_lemma_in_synset = first_synset.lemmas()[0] if first_synset.lemmas() else None
        if first_lemma_in_synset:
            for ant in first_lemma_in_synset.antonyms():
                antonyms.add(ant.name().replace('_', ' '))
                if len(antonyms) >= limit: break
        antonyms_str = ", ".join(sorted(list(antonyms))) if antonyms else "N/A"

        return {
            "synonyms": synonyms_str,
            "antonyms": antonyms_str,
            "definition": definition
        }


if __name__ == "__main__":
    root = tk.Tk()
    app = SessionAnalysisApp(root)
    root.mainloop()
