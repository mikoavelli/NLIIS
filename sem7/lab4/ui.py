import tkinter as tk
import threading
import cairosvg
import spacy

from tkinter import ttk, messagebox, filedialog, scrolledtext
from queue import Queue

from translator import OllamaTranslator
from analyzer import TextAnalyzer

SVG_RENDERER = 'cairosvg'


class MachineTranslationApp:
    """The main GUI application class."""

    def __init__(self, root):
        self.root = root
        self.root.title("Lab Work #4: Automatic Machine Translation")
        self.root.geometry("1600x900")

        self.translator = OllamaTranslator()
        self.analyzer = TextAnalyzer()
        self.analyzed_doc = None

        self._setup_styles()
        self._create_widgets()

    @staticmethod
    def _setup_styles():
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", rowheight=25, font=('TkDefaultFont', 10))
        style.configure("Treeview.Heading", font=('TkDefaultFont', 10, 'bold'))
        style.configure("TLabel", font=('TkDefaultFont', 10))
        style.configure("TButton", font=('TkDefaultFont', 10), padding=5)
        style.configure("TLabelframe.Label", font=('TkDefaultFont', 11, 'bold'))

    def _create_widgets(self):
        main_pane = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_pane.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        io_frame = ttk.Frame(main_pane, padding=10)
        main_pane.add(io_frame, weight=1)

        controls_frame = ttk.LabelFrame(io_frame, text="Translation Parameters")
        controls_frame.pack(fill=tk.X, pady=(0, 10))
        self.direction_var = tk.StringVar(value="en_ru")
        ttk.Radiobutton(controls_frame, text="English -> Russian", variable=self.direction_var, value="en_ru").pack(
            side=tk.LEFT, padx=10, pady=5)
        ttk.Radiobutton(controls_frame, text="Russian -> English", variable=self.direction_var, value="ru_en").pack(
            side=tk.LEFT, padx=10, pady=5)

        self.translate_button = ttk.Button(controls_frame, text="Translate and Analyze",
                                           command=self.start_translation_task)
        self.translate_button.pack(side=tk.RIGHT, padx=10, pady=5)
        ttk.Button(controls_frame, text="Save Report", command=self.save_report).pack(side=tk.RIGHT, padx=5, pady=5)

        text_io_pane = ttk.PanedWindow(io_frame, orient=tk.VERTICAL)
        text_io_pane.pack(fill=tk.BOTH, expand=True)

        source_frame = ttk.LabelFrame(text_io_pane, text="Source Text")
        text_io_pane.add(source_frame, weight=1)
        self.source_text = scrolledtext.ScrolledText(source_frame, wrap=tk.WORD, height=15, font=('TkDefaultFont', 11))
        self.source_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.source_status = ttk.Label(source_frame, text="Words: 0")
        self.source_status.pack(side=tk.RIGHT, padx=5)

        target_frame = ttk.Frame(text_io_pane)
        text_io_pane.add(target_frame, weight=2)

        model1_frame = ttk.LabelFrame(target_frame, text="Translation (model: llama3.1:8b)")
        model1_frame.pack(fill=tk.BOTH, expand=True, pady=(5, 5))
        self.target_text1 = scrolledtext.ScrolledText(model1_frame, wrap=tk.WORD, height=10, font=('TkDefaultFont', 11))
        self.target_text1.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.target_status1 = ttk.Label(model1_frame, text="Words: 0")
        self.target_status1.pack(side=tk.RIGHT, padx=5)

        model2_frame = ttk.LabelFrame(target_frame, text="Translation (model: llama3.2:1b)")
        model2_frame.pack(fill=tk.BOTH, expand=True, pady=(5, 0))
        self.target_text2 = scrolledtext.ScrolledText(model2_frame, wrap=tk.WORD, height=10, font=('TkDefaultFont', 11))
        self.target_text2.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.target_status2 = ttk.Label(model2_frame, text="Words: 0")
        self.target_status2.pack(side=tk.RIGHT, padx=5)

        results_frame = ttk.Frame(main_pane, padding=10)
        main_pane.add(results_frame, weight=1)

        notebook = ttk.Notebook(results_frame)
        notebook.pack(fill=tk.BOTH, expand=True)

        analysis_tab = ttk.Frame(notebook)
        notebook.add(analysis_tab, text="Detailed Analysis")

        analysis_controls_frame = ttk.Frame(analysis_tab)
        analysis_controls_frame.pack(fill=tk.X, pady=5)
        ttk.Button(analysis_controls_frame, text="Show Dependency Tree", command=self.show_dependency_tree_window).pack(
            side=tk.LEFT)
        ttk.Button(analysis_controls_frame, text="Correct Selected Translation",
                   command=self.open_correction_window).pack(side=tk.LEFT, padx=10)

        cols_analysis = ("ID", "Token", "Translation", "Lemma", "Part of Speech", "Morphology")
        self.analysis_tree = ttk.Treeview(analysis_tab, columns=cols_analysis, show="headings")
        for col in cols_analysis: self.analysis_tree.heading(col, text=col)
        self.analysis_tree.column("ID", width=40, stretch=tk.NO)
        self.analysis_tree.pack(fill=tk.BOTH, expand=True)

        frequency_tab = ttk.Frame(notebook)
        notebook.add(frequency_tab, text="Frequency List")

        cols_freq = ("Word", "Translation", "Frequency", "Lemma", "Grammatical Info")
        self.frequency_tree = ttk.Treeview(frequency_tab, columns=cols_freq, show="headings")
        for col in cols_freq: self.frequency_tree.heading(col, text=col)
        self.frequency_tree.column("Frequency", width=80, stretch=tk.NO)
        self.frequency_tree.pack(fill=tk.BOTH, expand=True)

        status_bar_frame = ttk.Frame(self.root)
        status_bar_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=5)
        self.status_label = ttk.Label(status_bar_frame, text="Ready")
        self.status_label.pack(side=tk.LEFT)
        self.progress_bar = ttk.Progressbar(status_bar_frame, orient='horizontal', mode='determinate')
        self.progress_bar.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=10)

    def open_correction_window(self):
        selected_items = self.analysis_tree.selection()
        if not selected_items:
            messagebox.showwarning("No Selection",
                                   "Please select a token in the 'Detailed Analysis' table to correct its translation.")
            return

        selected_item = selected_items[0]
        item_values = self.analysis_tree.item(selected_item, 'values')

        token = item_values[1]
        current_translation = item_values[2]

        popup = tk.Toplevel(self.root)
        popup.title("Correct Translation")
        popup.transient(self.root)
        popup.grab_set()

        ttk.Label(popup, text="Original Token:").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        ttk.Label(popup, text=token, font=('TkDefaultFont', 10, 'bold')).grid(row=0, column=1, padx=10, pady=10,
                                                                              sticky="w")

        ttk.Label(popup, text="Translation:").grid(row=1, column=0, padx=10, pady=5, sticky="w")
        translation_var = tk.StringVar(value=current_translation)
        translation_entry = ttk.Entry(popup, textvariable=translation_var, width=40)
        translation_entry.grid(row=1, column=1, padx=10, pady=5, sticky="ew")
        translation_entry.focus()

        def on_save():
            new_translation = translation_var.get().strip()
            if not new_translation or new_translation == '-':
                messagebox.showerror("Error", "Translation cannot be empty.", parent=popup)
                return

            self.translator.save_correction(token, new_translation)
            self.analysis_tree.set(selected_item, "Translation", new_translation)

            messagebox.showinfo("Saved", f"Correction for '{token}' saved successfully.", parent=self.root)
            popup.destroy()

        save_button = ttk.Button(popup, text="Save Correction", command=on_save)
        save_button.grid(row=2, column=0, columnspan=2, pady=10)
        popup.bind("<Return>", lambda event: on_save())

    def show_dependency_tree_window(self):
        if not self.analyzed_doc:
            messagebox.showwarning("No Analysis", "Please analyze some text first.")
            return
        if not SVG_RENDERER:
            messagebox.showerror("Error", "SVG rendering library not found (cairosvg or svglib).")
            return

        sentences = list(self.analyzed_doc.sents)
        if not sentences:
            messagebox.showinfo("Info", "No sentences found in the text.")
            return

        popup = tk.Toplevel(self.root)
        popup.title("Dependency Parse Tree")
        popup.geometry("900x600")

        control_frame = ttk.Frame(popup)
        control_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(control_frame, text="Select Sentence (index):").pack(side=tk.LEFT)

        self.sent_index_var = tk.IntVar(value=0)
        sentence_spinbox = ttk.Spinbox(
            control_frame,
            from_=0,
            to=len(sentences) - 1,
            textvariable=self.sent_index_var,
            width=5,
            wrap=True
        )
        sentence_spinbox.pack(side=tk.LEFT, padx=5)

        canvas_frame = ttk.Frame(popup, relief=tk.SUNKEN, borderwidth=1)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        canvas = tk.Canvas(canvas_frame, bg='white')
        v_scroll = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=canvas.yview)
        h_scroll = ttk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL, command=canvas.xview)
        canvas.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        h_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        image_label = ttk.Label(canvas, background='white')
        canvas.create_window((0, 0), window=image_label, anchor="nw")

        def _update_tree():
            try:
                sent_index = self.sent_index_var.get()
                if not (0 <= sent_index < len(sentences)):
                    raise ValueError("Index out of range")
            except (tk.TclError, ValueError):
                messagebox.showerror("Invalid Input", "Please enter a valid sentence index.", parent=popup)
                return

            try:
                sentence_to_render = sentences[sent_index]
                svg_code = spacy.displacy.render(sentence_to_render, style="dep", jupyter=False)
                png_bytes = cairosvg.svg2png(bytestring=svg_code.encode('utf-8'),
                                             dpi=120)

                if png_bytes:
                    image = tk.PhotoImage(data=png_bytes)
                    image_label.config(image=image)
                    image_label.image = image

                    canvas.update_idletasks()
                    canvas.config(scrollregion=canvas.bbox("all"))

            except Exception as e:
                image_label.config(image=None, text=f"Error rendering tree: {e}")
                print(f"Error rendering dependency tree: {e}")

        update_button = ttk.Button(control_frame, text="Update Tree", command=_update_tree)
        update_button.pack(side=tk.LEFT, padx=5)

        _update_tree()

    def start_translation_task(self):
        source_text = self.source_text.get('1.0', tk.END).strip()
        if not source_text:
            messagebox.showwarning("Warning", "Please enter text to translate.")
            return

        self.translate_button.config(state="disabled")
        self.clear_previous_results()

        self.task_queue = Queue()
        thread = threading.Thread(target=self.translation_and_analysis_worker, args=(source_text,), daemon=True)
        thread.start()
        self.root.after(100, self.process_queue)

    def process_queue(self):
        try:
            message = self.task_queue.get_nowait()
            msg_type, data = message

            if msg_type == "progress":
                self.progress_bar['value'] = data
            elif msg_type == "status":
                self.status_label.config(text=data)
            elif msg_type == "translation1":
                self.target_text1.insert('1.0', data)
            elif msg_type == "translation2":
                self.target_text2.insert('1.0', data)
            elif msg_type == "word_counts":
                self.source_status.config(text=f"Words: {data['source']}")
                self.target_status1.config(text=f"Words: {data['target1']}")
                self.target_status2.config(text=f"Words: {data['target2']}")
            elif msg_type == "analysis_data":
                self._populate_table(self.analysis_tree, data)
            elif msg_type == "frequency_data":
                self._populate_table(self.frequency_tree, data)
            elif msg_type == "task_complete":
                self.translate_button.config(state="normal")
                self.status_label.config(text="Ready")
                messagebox.showinfo("Complete", "Translation and analysis finished successfully.")

            self.root.after(100, self.process_queue)
        except Exception:
            self.root.after(100, self.process_queue)

    def translation_and_analysis_worker(self, source_text):
        q = self.task_queue
        direction = self.direction_var.get()
        source_lang_code, target_lang_code = direction.split('_')
        source_lang_full = "English" if source_lang_code == 'en' else "Russian"
        target_lang_full = "Russian" if target_lang_code == 'ru' else "English"

        q.put(("status", "Translating with model 1..."))
        q.put(("progress", 10))
        translation1 = self.translator.translate(source_text, 'llama3.1:8b', source_lang_full, target_lang_full)
        q.put(("translation1", translation1))

        q.put(("status", "Translating with model 2..."))
        q.put(("progress", 25))
        translation2 = self.translator.translate(source_text, 'llama3.2:1b', source_lang_full, target_lang_full)
        q.put(("translation2", translation2))
        q.put(("word_counts", {"source": len(source_text.split()), "target1": len(translation1.split()),
                               "target2": len(translation2.split())}))
        q.put(("status", "Performing linguistic analysis..."))
        q.put(("progress", 40))

        nlp = self.analyzer.nlp_models[source_lang_code]
        if not nlp:
            q.put(("status", f"Error: spaCy model for '{source_lang_code}' not loaded."))
            q.put(("task_complete", True))
            return

        self.analyzed_doc = nlp(source_text)
        from utils import clean_token
        tokens = [clean_token(t.text.lower()) for t in self.analyzed_doc if t.is_alpha]
        unique_tokens = sorted(list(set(tokens)))

        word_translations = {}
        for i, token in enumerate(unique_tokens):
            if not token: continue
            q.put(("status", f"Translating unique words: {i + 1}/{len(unique_tokens)}"))
            progress_val = 40 + int((i / len(unique_tokens)) * 50)
            q.put(("progress", progress_val))
            translation = self.translator.translate(token, 'llama3.1:8b', source_lang_full, target_lang_full)
            word_translations[token] = translation

        q.put(("progress", 95))
        q.put(("status", "Populating results tables..."))

        analysis_data = self.analyzer.prepare_analysis_table_data(self.analyzed_doc, word_translations,
                                                                  source_lang_code)
        q.put(("analysis_data", analysis_data))

        frequency_data = self.analyzer.prepare_frequency_table_data(tokens, word_translations, self.analyzed_doc,
                                                                    source_lang_code)
        q.put(("frequency_data", frequency_data))

        q.put(("progress", 100))
        q.put(("status", "Finished"))
        q.put(("task_complete", True))

    @staticmethod
    def _populate_table(treeview, data):
        """Generic function to populate a Treeview widget."""
        treeview.delete(*treeview.get_children())
        for row_data in data:
            treeview.insert("", "end", values=row_data)

    def clear_previous_results(self):
        self.status_label.config(text="Processing...")
        self.progress_bar['value'] = 0
        self.target_text1.delete('1.0', tk.END)
        self.target_text2.delete('1.0', tk.END)
        self.analysis_tree.delete(*self.analysis_tree.get_children())
        self.frequency_tree.delete(*self.frequency_tree.get_children())
        self.analyzed_doc = None

    def save_report(self):
        filepath = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text Files", "*.txt")])
        if not filepath: return
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write("=" * 80 + "\nMACHINE TRANSLATION REPORT\n" + "=" * 80 + "\n\n")
                f.write("--- SOURCE TEXT ---\n" + self.source_text.get('1.0', tk.END).strip() + "\n\n")
                f.write("--- TRANSLATION (llama3.1:8b) ---\n" + self.target_text1.get('1.0', tk.END).strip() + "\n\n")
                f.write("--- TRANSLATION (llama3.2:1b) ---\n" + self.target_text2.get('1.0', tk.END).strip() + "\n\n")
                f.write("=" * 80 + "\nWORD FREQUENCY LIST\n" + "=" * 80 + "\n\n")
                header = "{:<20} | {:<20} | {:<10} | {:<20} | {}\n".format(
                    *[self.frequency_tree.heading(c)["text"] for c in self.frequency_tree["columns"]])
                f.write(header)
                f.write("-" * (len(header) + 5) + "\n")
                for item_id in self.frequency_tree.get_children():
                    values = self.frequency_tree.item(item_id, 'values')
                    f.write("{:<20} | {:<20} | {:<10} | {:<20} | {}\n".format(*values))
            messagebox.showinfo("Success", f"Report saved to:\n{filepath}")
        except Exception as e:
            messagebox.showerror("Save Error", f"Could not save the file:\n{e}")
