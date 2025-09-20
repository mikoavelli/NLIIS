import io
import os
import nltk
import json
import spacy
import cairosvg
import requests
import tkinter as tk
from PIL import Image, ImageTk
from idlelib.tooltip import Hovertip
from nltk.corpus import wordnet as wn
from tkinter import ttk, messagebox, filedialog, scrolledtext
from utils import POS_TAG_TRANSLATIONS, beautiful_morph, clean_token

nltk.download('wordnet', quiet=True)
nltk.download('omw-1.4', quiet=True)
wn.synsets('test', pos=wn.NOUN)

SPACY_MODEL_NAME = 'en_core_web_sm'
NLP = spacy.load(SPACY_MODEL_NAME)
OLLAMA_URL = 'http://localhost:11434/api/generate'
MODEL_NAME = "llama3"
RESPONSE_TIMEOUT = 120


# noinspection PyTypeChecker,PyUnresolvedReferences,PyUnboundLocalVariable,PyShadowingNames,PyUnusedLocal,PyAttributeOutsideInit,PyPep8Naming,DuplicatedCode,SpellCheckingInspection
class SessionDialogAnalyzerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Dialog System with NLP Analysis (Session) - Cinematography")
        self.root.geometry("2000x900")

        self.dialog_history = []
        self.last_analyzed_doc = None
        self.analysis_overrides = {}
        self.tree_token_map = {}

        self._load_spacy_model()
        self._setup_styles()
        self._create_widgets()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self._add_to_history("system", "Hello! Let's talk about movies. What's on your mind?")

    @staticmethod
    def _load_spacy_model():
        print(f"Loading spaCy model '{SPACY_MODEL_NAME}'...")
        try:

            print("spaCy model loaded successfully.")
        except OSError:
            messagebox.showerror(
                "spaCy Error",
                f"Model '{SPACY_MODEL_NAME}' not found.\nPlease download it: python -m spacy download {SPACY_MODEL_NAME}"
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
        style.configure("Treeview", rowheight=25, font=('TkDefaultFont', 10))
        style.configure("Treeview.Heading", font=('TkDefaultFont', 11, 'bold'))
        style.configure("TLabel", font=('TkDefaultFont', 10))
        style.configure("TButton", font=('TkDefaultFont', 10), padding=5)
        style.configure("TEntry", font=('TkDefaultFont', 10), padding=5)
        style.configure("TLabelframe.Label", font=('TkDefaultFont', 10, 'bold'))

    def _create_widgets(self):
        main_pane = ttk.PanedWindow(self.root, orient=tk.VERTICAL)
        main_pane.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        top_frame = ttk.Frame(main_pane, padding=0)
        main_pane.add(top_frame, weight=3)

        top_pane_inner = ttk.PanedWindow(top_frame, orient=tk.HORIZONTAL)
        top_pane_inner.pack(fill=tk.BOTH, expand=True)

        history_frame = ttk.LabelFrame(top_pane_inner, text="Dialog History", padding="10")
        top_pane_inner.add(history_frame, weight=1)

        self.history_text = scrolledtext.ScrolledText(history_frame,
                                                      wrap=tk.WORD,
                                                      height=15,
                                                      font=('TkDefaultFont', 11),
                                                      state='disabled',
                                                      relief="sunken",
                                                      borderwidth=1)
        self.history_text.pack(fill="both", expand=True)
        Hovertip(self.history_text, "Conversation history.")
        self.history_text.tag_configure("user_tag", foreground="blue", font=('TkDefaultFont', 11, 'bold'))
        self.history_text.tag_configure("system_tag", foreground="green", font=('TkDefaultFont', 11, 'italic'))
        self.history_text.tag_configure("message_tag", lmargin1=20, lmargin2=20)

        results_frame = ttk.LabelFrame(top_pane_inner, text="Last Message Analysis (Editable)", padding="10")
        top_pane_inner.add(results_frame, weight=2)

        cols = ("ID", "Token", "Lemma", "POS", "Morphology", "Dependency", "Synonyms", "Antonyms", "Definition")
        self.analysis_tree = ttk.Treeview(results_frame, columns=cols, show="headings", height=15)
        col_widths = {"ID": 40,
                      "Token": 100,
                      "Lemma": 100,
                      "POS": 90,
                      "Morphology": 150,
                      "Dependency": 120,
                      "Synonyms": 120,
                      "Antonyms": 120,
                      "Definition": 200}
        for col in cols:
            self.analysis_tree.heading(col, text=col, anchor='w')
            stretch = tk.NO if col == "ID" else tk.YES
            self.analysis_tree.column(col, width=col_widths[col], minwidth=40, anchor='w', stretch=stretch)

        vsb = ttk.Scrollbar(results_frame, orient="vertical", command=self.analysis_tree.yview)
        hsb = ttk.Scrollbar(results_frame, orient="horizontal", command=self.analysis_tree.xview)
        self.analysis_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side="right", fill="y")
        hsb.pack(side="bottom", fill="x")
        self.analysis_tree.pack(side="top", fill="both", expand=True)
        Hovertip(self.analysis_tree,
                 "Detailed analysis of the last user message.\nDouble-click a row to edit core fields.")
        self.analysis_tree.bind("<Double-1>", self.open_wordform_edit_window)

        analysis_buttons_frame = ttk.Frame(results_frame)
        analysis_buttons_frame.pack(fill="x", pady=(5, 0))
        btn_export = ttk.Button(analysis_buttons_frame, text="Export Selected Token",
                                command=self.export_selected_wordform, width=20)
        btn_export.pack(side="left", padx=5)
        Hovertip(btn_export, "Export analysis of the selected token from the table to JSON.")
        btn_import = ttk.Button(analysis_buttons_frame, text="Import Token Overrides",
                                command=self.import_wordform_overrides, width=20)
        btn_import.pack(side="left", padx=5)
        Hovertip(btn_import, "Import analysis overrides from JSON for the currently analyzed message.")
        btn_ignore = ttk.Button(analysis_buttons_frame, text="Ignore Selected Token",
                                command=self.ignore_selected_wordform, width=20)
        btn_ignore.pack(side="left", padx=5)
        Hovertip(btn_ignore, "Mark selected token as ignored in the current analysis.")
        btn_show_tree = ttk.Button(analysis_buttons_frame, text="Show Dependency Tree",
                                   command=self.show_dependency_tree_window, width=20)
        btn_show_tree.pack(side="left", padx=5)
        Hovertip(btn_show_tree, "Show the dependency parse tree for the selected sentence in a new window.")

        bottom_frame = ttk.Frame(main_pane, padding=0)
        main_pane.add(bottom_frame, weight=1)

        input_frame = ttk.LabelFrame(bottom_frame, text="Your Message", padding="10")
        input_frame.pack(padx=0, pady=(5, 5), fill="x")
        self.user_input_var = tk.StringVar()
        entry_user_input = ttk.Entry(input_frame, textvariable=self.user_input_var, font=('TkDefaultFont', 11))
        entry_user_input.pack(side="left", fill="x", expand=True, padx=(0, 10))
        Hovertip(entry_user_input, "Type your message here and press Enter or click Send.")
        entry_user_input.bind("<Return>", self._process_user_input)
        btn_send = ttk.Button(input_frame, text="Send", command=self._process_user_input)
        btn_send.pack(side="right")
        Hovertip(btn_send, "Send your message to the system.")

        history_controls_frame = ttk.LabelFrame(bottom_frame, text="Dialog Management", padding="10")
        history_controls_frame.pack(padx=0, pady=5, fill="x")
        btn_export_hist = ttk.Button(history_controls_frame, text="Export History", command=self.export_history)
        btn_export_hist.pack(side="left", padx=5)
        Hovertip(btn_export_hist, "Export the current dialog history to a JSON file.")
        btn_import_hist = ttk.Button(history_controls_frame, text="Import History", command=self.import_history)
        btn_import_hist.pack(side="left", padx=5)
        Hovertip(btn_import_hist, "Import dialog history from a JSON file (replaces current history).")
        btn_clear_hist = ttk.Button(history_controls_frame, text="Clear History", command=self.clear_history)
        btn_clear_hist.pack(side="left", padx=5)
        Hovertip(btn_clear_hist, "Clear the current dialog history display.")

    def _add_to_history(self, speaker, message):
        message = message.strip()
        if not message:
            return

        self.dialog_history.append((speaker, message))

        self.history_text.config(state='normal')
        if self.history_text.index('end-1c') != "1.0":
            self.history_text.insert('end', "\n")

        speaker_tag = "user_tag" if speaker == "user" else "system_tag"
        speaker_prefix = "You: " if speaker == "user" else "System: "
        self.history_text.insert('end', speaker_prefix, (speaker_tag,))
        self.history_text.insert('end', message, ("message_tag",))
        self.history_text.see('end')
        self.history_text.config(state='disabled')

    def clear_history(self):
        if messagebox.askyesno("Confirm Clear", "Are you sure you want to clear the entire dialog history?"):
            self.dialog_history = []
            self.last_analyzed_doc = None
            self.analysis_overrides = {}
            self.tree_token_map = {}
            self.history_text.config(state='normal')
            self.history_text.delete('1.0', tk.END)
            self.history_text.config(state='disabled')
            self.analysis_tree.delete(*self.analysis_tree.get_children())
            self._add_to_history("system", "History cleared. Let's start over. How can I help with movies?")
            print("Dialog history cleared.")

    def export_history(self):
        if not self.dialog_history:
            messagebox.showinfo("Info", "Dialog history is empty, nothing to export.")
            return
        filepath = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Save Dialog History As..."
        )
        if not filepath:
            return
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(self.dialog_history, f, indent=2, ensure_ascii=False)
            messagebox.showinfo("Success", f"Dialog history exported to {os.path.basename(filepath)}.")
            print(f"History exported to {filepath}")
        except Exception as e:
            messagebox.showerror("Export Error", f"Could not save history:\n{e}")
            print(f"Error exporting history: {e}")

    def import_history(self):
        filepath = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Select JSON File to Import Dialog History"
        )
        if not filepath:
            return

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                imported_data = json.load(f)

            if not isinstance(imported_data, list) or \
                    not all(isinstance(item, (list, tuple)) and len(item) == 2 for item in imported_data):
                messagebox.showerror("Format Error",
                                     "Invalid history format. Expected a list of [speaker, message] pairs.")
                return

            if messagebox.askyesno("Confirm Import", "This will replace the current dialog history. Proceed?"):
                self.dialog_history = []
                self.last_analyzed_doc = None
                self.analysis_overrides = {}
                self.tree_token_map = {}
                self.history_text.config(state='normal')
                self.history_text.delete('1.0', tk.END)
                self.analysis_tree.delete(*self.analysis_tree.get_children())

                for speaker, message in imported_data:
                    speaker_clean = "user" if str(speaker).lower() == "user" else "system"
                    message_clean = str(message)
                    self._add_to_history(speaker_clean, message_clean)

                self.history_text.config(state='disabled')
                messagebox.showinfo("Success", "Dialog history imported successfully.")
                print(f"History imported from {filepath}")

        except FileNotFoundError:
            messagebox.showerror("File Error", f"File not found:\n{filepath}")
        except json.JSONDecodeError as e:
            messagebox.showerror("JSON Error", f"Error decoding JSON file:\n{e}")
        except Exception as e:
            messagebox.showerror("Import Error", f"An unexpected error occurred during import:\n{e}")
            print(f"Error importing history: {e}")

    def _process_user_input(self, event=None):
        user_message = self.user_input_var.get().strip()
        if not user_message:
            return

        self.user_input_var.set("")
        self._add_to_history("user", user_message)

        self.last_analyzed_doc = None
        self.analysis_overrides = {}
        self.tree_token_map = {}
        self.analysis_tree.delete(*self.analysis_tree.get_children())
        try:
            print(f"Analyzing user message: '{user_message}'")
            self.last_analyzed_doc = NLP(user_message)
            self._populate_analysis_table()
        except Exception as e:
            print(f"Error analyzing user message: {e}")
            messagebox.showwarning("Analysis Error", f"Could not analyze the message:\n{e}")

        system_response = self._generate_response(self.last_analyzed_doc, user_message)
        self._add_to_history("system", system_response)

    def _generate_response(self, user_doc, user_message_raw):
        history_context = ""
        max_history = 3
        relevant_history = self.dialog_history[-(max_history * 2):-1]

        for speaker, message in relevant_history:
            prefix = "User" if speaker == "user" else "Assistant"
            history_context += f"{prefix}: {message}\n"

        prompt = (
            f"You are a helpful assistant discussing cinematography.\n"
            f"Continue the conversation based on the history below and the new user message.\n\n"
            f"--- History ---\n"
            f"{history_context.strip()}\n"
            f"--- End History ---\n\n"
            f"User: {user_message_raw}\n"
            f"Assistant:"
        )
        payload = {
            "model": MODEL_NAME,
            "prompt": prompt,
            "stream": False
        }
        print(f"APP: Sending prompt to Llama 3: '{prompt[:100]}...'")

        try:
            global RESPONSE_TIMEOUT
            response = requests.post(OLLAMA_URL, json=payload, timeout=RESPONSE_TIMEOUT)
            response.raise_for_status()
            response_data = response.json()
            llama_response = response_data.get('response', '').strip()

            if not llama_response:
                print("APP: Warning - Llama 3 returned an empty response.")
                return "I'm not sure how to respond to that right now."
            else:
                print(f"APP: Received Llama 3 response: '{llama_response[:100]}...'")
                return llama_response
        except requests.exceptions.ConnectionError:
            error_msg = f"Error: Could not connect to the Llama 3 API. Is Ollama running at {OLLAMA_URL}?"
            print(f"APP: {error_msg}")
            return "Sorry, I'm having trouble connecting to my brain right now. Please ensure the backend service is running."
        except requests.exceptions.Timeout:
            error_msg = "Error: The request to the Llama 3 API timed out."
            print(f"APP: {error_msg}")
            return "Sorry, my response is taking too long to generate."
        except requests.exceptions.RequestException as e:
            error_msg = f"Error calling Llama 3 API: {e}"
            print(f"APP: {error_msg}")

            try:
                error_detail = response.json()
                error_msg += f"\nDetails: {error_detail.get('error', 'N/A')}"
            except (AttributeError, ValueError):
                pass
            return f"Sorry, an error occurred while generating the response. ({response.status_code})"
        except json.JSONDecodeError:
            error_msg = "Error: Could not decode the JSON response from Llama 3 API."
            print(f"APP: {error_msg}\nRaw response: {response.text[:200]}")
            return "Sorry, I received an unexpected response format."
        except Exception as e:
            error_msg = f"An unexpected error occurred during response generation: {e}"
            print(f"APP: {error_msg}")
            import traceback
            traceback.print_exc()
            return "An unexpected error occurred."

    def _populate_analysis_table(self):
        self.analysis_tree.delete(*self.analysis_tree.get_children())
        self.tree_token_map.clear()
        if not self.last_analyzed_doc:
            return

        print("Populating analysis table for the last message (including WordNet)...")
        visible_token_count = 0
        wordnet_errors = 0

        for i, token in enumerate(self.last_analyzed_doc):
            cleaned = clean_token(token.text)
            if not cleaned or token.is_space:
                continue

            override = self.analysis_overrides.get(i, {})
            if override.get("deleted", False):
                continue

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
                i, wordform, lemma, pos_tag, morph_str, dep_rel,
                wordnet_info["synonyms"], wordnet_info["antonyms"], wordnet_info["definition"]
            )
            self.analysis_tree.insert("", "end", values=values, iid=iid)
            visible_token_count += 1

        print(f"Analysis table populated. Displayed tokens: {visible_token_count}. WordNet errors: {wordnet_errors}")

    @staticmethod
    def _map_spacy_pos_to_wordnet(spacy_pos_tag):
        if spacy_pos_tag in ['NOUN', 'PROPN']:
            return wn.NOUN
        if spacy_pos_tag == 'VERB':
            return wn.VERB
        if spacy_pos_tag == 'ADJ':
            return wn.ADJ
        if spacy_pos_tag == 'ADV':
            return wn.ADV
        return None

    def _get_wordnet_info(self, lemma, spacy_pos_tag):
        wn_pos = self._map_spacy_pos_to_wordnet(spacy_pos_tag)
        results = {"synonyms": "N/A", "antonyms": "N/A", "definition": "N/A"}
        if not wn_pos:
            return results

        synsets = wn.synsets(lemma, pos=wn_pos)
        if not synsets:
            return results

        first_synset = synsets[0]
        results["definition"] = first_synset.definition() or "N/A"

        synonyms = set()
        limit = 5
        for lem in first_synset.lemmas():
            syn_name = lem.name().replace('_', ' ')
            if syn_name.lower() != lemma.lower():
                synonyms.add(syn_name)
            if len(synonyms) >= limit:
                break
        results["synonyms"] = ", ".join(sorted(list(synonyms))) if synonyms else "N/A"

        antonyms = set()
        first_lemma_in_synset = first_synset.lemmas()[0] if first_synset.lemmas() else None
        if first_lemma_in_synset:
            for ant in first_lemma_in_synset.antonyms():
                antonyms.add(ant.name().replace('_', ' '))
                if len(antonyms) >= limit:
                    break
        results["antonyms"] = ", ".join(sorted(list(antonyms))) if antonyms else "N/A"

        return results

    def _render_dependency_tree(self, target_label_widget, sentence_index=0):
        target_label_widget.image_tk = None
        if not self.last_analyzed_doc:
            message = "No message analyzed yet."
            target_label_widget.config(image="", text=message)
            print(message)
            return False

        try:
            sentences = list(self.last_analyzed_doc.sents)
            if not sentences or sentence_index < 0 or sentence_index >= len(sentences):
                message = f"Sentence index {sentence_index} out of bounds (0-{len(sentences) - 1})."
                target_label_widget.config(image="", text=message)
                print(message)
                return False

            sentence_to_render = sentences[sentence_index]
            print(f"Rendering tree for sentence {sentence_index}...")

            svg_options = {"compact": False, "font": "Arial", "bg": "#fafafa", "color": "#000000", "word_spacing": 45,
                           "arrow_spacing": 20}
            render_dpi = 100

            svg_code = spacy.displacy.render(sentence_to_render, style="dep", jupyter=False, options=svg_options)
            png_bytes = None

            try:
                png_bytes = cairosvg.svg2png(bytestring=svg_code.encode('utf-8'), dpi=render_dpi)
            except Exception as e:
                print(f"cairosvg error: {e}")

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
        if not self.last_analyzed_doc:
            messagebox.showwarning("No Analysis", "Please analyze a message first (send a message).")
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
        Hovertip(sent_index_entry, "Enter sentence index (starts from 0) of the last analyzed message.")
        canvas_widget, tree_label_widget = self._create_scrolled_image_widget(popup)
        btn_update_tree = ttk.Button(control_frame,
                                     text="Update Tree",
                                     command=lambda: self._update_tree_in_popup(popup, canvas_widget,
                                                                                tree_label_widget))
        btn_update_tree.pack(side="left", padx=5)
        Hovertip(btn_update_tree, "Render tree for the specified sentence index.")
        self._update_tree_in_popup(popup, canvas_widget, tree_label_widget)

    @staticmethod
    def _create_scrolled_image_widget(parent_widget):
        frame = ttk.Frame(parent_widget, relief="sunken", borderwidth=1)
        frame.pack(fill="both", expand=True, padx=5, pady=5)
        canvas = tk.Canvas(frame, bg='white')
        h_scroll = ttk.Scrollbar(frame, orient=tk.HORIZONTAL, command=canvas.xview)
        v_scroll = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(xscrollcommand=h_scroll.set, yscrollcommand=v_scroll.set)
        h_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        image_label = ttk.Label(canvas, anchor="nw", background="white")
        canvas.create_window((0, 0), window=image_label, anchor="nw")
        image_label.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        return canvas, image_label

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
                print("Could not get bbox after rendering.")
                target_canvas.configure(scrollregion=(0, 0, 100, 100))
            target_canvas.xview_moveto(0)
            target_canvas.yview_moveto(0)

    def get_selected_item_details(self):
        selected_items = self.analysis_tree.selection()
        if not selected_items:
            messagebox.showwarning("No Selection", "Please select an entry in the analysis table first.")
            return None, None
        selected_iid = selected_items[0]
        token_index = self.tree_token_map.get(selected_iid)
        if token_index is None:
            messagebox.showerror("Error", "Could not map selected table row to token data.")
            return None, None
        return selected_iid, token_index

    def open_wordform_edit_window(self, event):
        selected_iid, token_index = self.get_selected_item_details()
        if selected_iid is None:
            return
        if not self.last_analyzed_doc or token_index >= len(self.last_analyzed_doc):
            messagebox.showerror("Error", "Analysis data is missing or index is out of bounds for the last message.")
            return

        token = self.last_analyzed_doc[token_index]
        current_override = self.analysis_overrides.get(token_index, {})
        print(f"DEBUG: Opening edit window for token {token_index}. Overrides: {current_override}")

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
        ttk.Label(form_frame, text=current_data["wordform"], relief="sunken", padding=3, anchor="w").grid(row=0,
                                                                                                          column=1,
                                                                                                          padx=5,
                                                                                                          pady=8,
                                                                                                          sticky="ew")

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
        if not self.last_analyzed_doc or token_index >= len(self.last_analyzed_doc):
            print("Error: Cannot save edit, analysis data missing.")
            popup_window.destroy()
            return

        new_override = self.analysis_overrides.get(token_index, {}).copy()
        updated = False
        original_token = self.last_analyzed_doc[token_index]

        for field, var in entries.items():
            new_value = var.get().strip()
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

        is_override_empty = not any(f != 'deleted' for f in new_override)

        if is_override_empty:
            if token_index in self.analysis_overrides:
                if "deleted" in self.analysis_overrides[token_index] and len(new_override) == 0:
                    self.analysis_overrides[token_index] = {"deleted": True}
                    updated = True
                else:
                    del self.analysis_overrides[token_index]
                    updated = True
        elif updated:
            self.analysis_overrides[token_index] = new_override

        popup_window.destroy()

        if updated:
            print(f"Overrides for token {token_index} updated in session.")
            self._update_treeview_row(token_index)
        else:
            print(f"No effective changes made for token {token_index}.")

    def ignore_selected_wordform(self):
        selected_iid, token_index = self.get_selected_item_details()
        if selected_iid is None:
            return
        token_text = ""
        if self.last_analyzed_doc and token_index < len(self.last_analyzed_doc):
            token_text = self.last_analyzed_doc[token_index].text

        confirm = messagebox.askyesno("Confirm Ignore",
                                      f"Mark token {token_index} ('{token_text}') as ignored?\nIt will be hidden from the table.",
                                      parent=self.root)
        if confirm:
            print(f"Marking token {token_index} as ignored.")
            override = self.analysis_overrides.get(token_index, {})
            override["deleted"] = True
            self.analysis_overrides[token_index] = override
            self._update_treeview_row(token_index)

    def export_selected_wordform(self):
        selected_iid, token_index = self.get_selected_item_details()
        if selected_iid is None:
            return
        if not self.last_analyzed_doc or token_index >= len(self.last_analyzed_doc):
            messagebox.showerror("Error", "Analysis data missing for the last message.")
            return

        token = self.last_analyzed_doc[token_index]
        override = self.analysis_overrides.get(token_index, {})

        if override.get("deleted", False):
            messagebox.showinfo("Info", f"Token {token_index} is ignored, cannot export.", parent=self.root)
            return

        wordnet_info = {"synonyms": "N/A", "antonyms": "N/A", "definition": "N/A"}
        try:
            lookup_lemma = override.get("lemma", token.lemma_)
            original_spacy_pos = token.pos_
            if original_spacy_pos in ['NOUN', 'VERB', 'ADJ', 'ADV']:
                wordnet_info = self._get_wordnet_info(lookup_lemma, original_spacy_pos)
        except Exception as e:
            print(f"Warning: WordNet lookup failed during export: {e}")

        export_entry_data = {
            "original_wordform": token.text,
            "lemma": override.get("lemma", token.lemma_),
            "pos": override.get("pos", POS_TAG_TRANSLATIONS.get(token.pos_, token.pos_)),
            "morph": override.get("morph", beautiful_morph(token.morph.to_dict())),
            "dep": override.get("dep", token.dep_),
            "synonyms": wordnet_info["synonyms"],
            "antonyms": wordnet_info["antonyms"],
            "definition": wordnet_info["definition"],
        }

        export_key = f"token_{token_index}"
        export_data = {export_key: export_entry_data}

        file_path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON files", "*.json")],
                                                 title="Save Token Override Data As...",
                                                 initialfile=f"override_token_{token_index}_{clean_token(token.text)}.json")
        if not file_path:
            return
        existing_data = {}
        file_exists = os.path.exists(file_path)
        try:
            if file_exists:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        existing_data = json.load(f)
                    if not isinstance(existing_data, dict):
                        existing_data = {}
                except (json.JSONDecodeError, IOError):
                    existing_data = {}
                if export_key in existing_data:
                    if not messagebox.askyesno("Overwrite?", f"Entry '{export_key}' already exists. Overwrite?",
                                               parent=self.root):
                        return
            existing_data[export_key] = export_entry_data
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(existing_data, f, indent=4, ensure_ascii=False)
            messagebox.showinfo("Success", f"Override data for '{export_key}' saved to {os.path.basename(file_path)}.")
        except Exception as e:
            messagebox.showerror("Export Error", f"Could not save override data:\n{e}")

    def import_wordform_overrides(self):
        if not self.last_analyzed_doc:
            messagebox.showwarning("No Analysis", "Analyze a message first before importing overrides.")
            return
        file_path = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")],
                                               title="Select JSON File with Overrides")
        if not file_path:
            return

        print(f"Importing overrides from: {file_path}")
        imported_count = 0
        skipped_count = 0
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data_to_import = json.load(f)
            if not isinstance(data_to_import, dict):
                messagebox.showerror("Format Error", "JSON file must be a dictionary.")
                return
            num_entries = len(data_to_import)
            if num_entries == 0:
                messagebox.showinfo("Info", "JSON file is empty.")
                return
            if not messagebox.askyesno("Confirm Import",
                                       f"Found {num_entries} potential overrides.\nApply them to the current analysis session?",
                                       parent=self.root):
                return

            applied_indices = set()
            for key, override_data in data_to_import.items():
                if not key.startswith("token_") or not isinstance(override_data, dict):
                    skipped_count += 1
                    continue
                try:
                    token_index = int(key.split("_")[1])
                except (IndexError, ValueError):
                    skipped_count += 1
                    continue
                if token_index < 0 or token_index >= len(self.last_analyzed_doc):
                    skipped_count += 1
                    continue

                current_override = self.analysis_overrides.get(token_index, {}).copy()
                applied_change = False
                for field in ["lemma", "pos", "morph", "dep", "deleted"]:
                    if field in override_data and override_data[field] is not None:
                        current_override[field] = str(override_data[field]).strip()
                        applied_change = True

                if applied_change:
                    self.analysis_overrides[token_index] = current_override
                    applied_indices.add(token_index)
                    imported_count += 1
                else:
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
        iid = f"token_{token_index}"
        if not self.analysis_tree.exists(iid):
            return
        if not self.last_analyzed_doc or token_index >= len(self.last_analyzed_doc):
            return

        token = self.last_analyzed_doc[token_index]
        override = self.analysis_overrides.get(token_index, {})

        if override.get("deleted", False):
            try:
                self.analysis_tree.delete(iid)
                print(f"Removed ignored token {token_index} from view.")
            except tk.TclError:
                pass
            return

        wordform = token.text.replace("\n", " ")
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
            print(f"Warning: WordNet lookup failed during row update: {e}")

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


if __name__ == "__main__":
    root = tk.Tk()
    app = SessionDialogAnalyzerApp(root)
    root.mainloop()

# --- END OF FILE session_dialog_analyzer.py ---
