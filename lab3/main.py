# --- START OF FILE manager_session.py ---

import io
import os
import json
import spacy
import tkinter as tk
from bs4 import BeautifulSoup  # Для парсинга HTML
from PIL import Image, ImageTk
from idlelib.tooltip import Hovertip
from tkinter import ttk, messagebox, filedialog, scrolledtext

# Попытка импорта рендереров SVG
SVG_RENDERER = None
try:
    import cairosvg

    SVG_RENDERER = 'cairosvg'
    print("Найден рендерер SVG: cairosvg")
except ImportError:
    try:
        from svglib.svglib import svg2rlg
        from reportlab.graphics import renderPM

        SVG_RENDERER = 'svglib'
        print("Найден рендерер SVG: svglib/reportlab")
    except ImportError:
        print("--- ПРЕДУПРЕЖДЕНИЕ: Рендерер SVG (cairosvg или svglib) не найден. ---")
        print("Деревья зависимостей не будут отображаться.")
        print("Рекомендуется установить: pip install cairosvg")
        print("-" * 60)

# Импорт утилит (убедитесь, что utils.py существует)
try:
    from utils import POS_TAG_TRANSLATIONS, beautiful_morph, clean_token
except ImportError:
    print("Ошибка: Не найден файл utils.py. Пожалуйста, создайте его.")
    # Предоставим заглушки, если utils.py нет
    POS_TAG_TRANSLATIONS = {}


    def beautiful_morph(d):
        return str(d) if d else "None"


    def clean_token(t):
        return t.strip()

# --- Глобальные переменные и константы ---
SPACY_MODEL_NAME = 'en_core_web_sm'
NLP = None  # Глобальный объект модели spaCy


# --- Основной класс приложения ---
class SessionAnalysisApp:
    def __init__(self, root):
        self.root = root
        self.root.title("HTML Text Analyzer (Session)")
        self.root.geometry("1500x1600")

        # --- Сеансовые данные ---
        self.current_html_path = ""
        self.original_text = ""  # Текст, извлеченный из HTML
        self.analyzed_doc = None  # Результат обработки spaCy (объект Doc)
        self.analysis_overrides = {}  # Словарь для хранения ручных правок {token_index: {field: new_value}}
        self.tree_token_map = {}  # Словарь для связи iid Treeview с индексом токена

        # --- Загрузка модели spaCy ---
        self._load_spacy_model()

        # --- Стили ttk ---
        self._setup_styles()

        # --- Создание основного интерфейса ---
        self._create_widgets()

        # --- Обработчик закрытия окна ---
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    @staticmethod
    def _load_spacy_model():
        """Загружает модель spaCy один раз при старте."""
        global NLP
        if NLP is None:
            print(f"Загрузка модели spaCy '{SPACY_MODEL_NAME}'...")
            try:
                NLP = spacy.load(SPACY_MODEL_NAME)
                print("Модель spaCy успешно загружена.")
            except OSError:
                messagebox.showerror(
                    "Ошибка spaCy",
                    f"Модель '{SPACY_MODEL_NAME}' не найдена.\n"
                    f"Анализ текста не будет работать.\n"
                    f"Скачайте модель: python -m spacy download {SPACY_MODEL_NAME}"
                )
                print(f"!!! Ошибка: Модель '{SPACY_MODEL_NAME}' не найдена. Установите её.")
            except Exception as e:
                messagebox.showerror("Ошибка spaCy", f"Не удалось загрузить модель spaCy:\n{e}")
                print(f"!!! Ошибка загрузки spaCy: {e}")

    @staticmethod
    def _setup_styles():
        """Настройка стилей ttk."""
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            style.theme_use("default")
        style.configure("Treeview", rowheight=30, font=('TkDefaultFont', 10))  # Используем 30
        style.configure("Treeview.Heading", font=('TkDefaultFont', 11, 'bold'))
        style.configure("TLabel", font=('TkDefaultFont', 10))
        style.configure("TButton", font=('TkDefaultFont', 10), padding=5)
        style.configure("TEntry", font=('TkDefaultFont', 10), padding=5)
        style.configure("TLabelframe.Label", font=('TkDefaultFont', 10, 'bold'))

    def _create_widgets(self):
        """Создает все виджеты интерфейса."""

        # --- Фрейм 1: Загрузка файла и управление текстом ---
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

        # --- Фрейм 2: Редактирование текста ---
        text_frame = ttk.LabelFrame(self.root, text="Text Content (Editable)", padding="10")
        text_frame.pack(padx=10, pady=5, fill="x", expand=False)  # expand=False
        self.text_edit_widget = scrolledtext.ScrolledText(text_frame, wrap=tk.WORD, height=10,
                                                          font=('TkDefaultFont', 10),
                                                          undo=True)
        self.text_edit_widget.pack(fill="both", expand=True, pady=(0, 5))
        Hovertip(self.text_edit_widget, "Edit text here. Use 'Re-analyze' after modification.")
        btn_reanalyze = ttk.Button(text_frame, text="Re-analyze Edited Text", command=self.reanalyze_edited_text)
        btn_reanalyze.pack(side="bottom", pady=(5, 0))
        Hovertip(btn_reanalyze, "Re-run analysis on modified text. This resets manual overrides.")

        # --- Фрейм 3: Таблица Результатов анализа ---
        results_frame = ttk.LabelFrame(self.root, text="Analysis Results (Editable)", padding="10")
        results_frame.pack(padx=10, pady=5, fill="both", expand=True)  # Таблица занимает основное место

        cols = ("ID", "Token", "Lemma", "POS", "Morphology", "Dependency")
        self.analysis_tree = ttk.Treeview(results_frame, columns=cols, show="headings", height=15)
        col_widths = {"ID": 50, "Token": 120, "Lemma": 120, "POS": 100, "Morphology": 200, "Dependency": 100}
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
        Hovertip(self.analysis_tree, "Linguistic analysis results.\nDouble-click a row to edit. Use buttons below.")
        self.analysis_tree.bind("<Double-1>", self.open_wordform_edit_window)

        # --- Фрейм 4: Кнопки управления под таблицей ---
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

    # --- Методы Обработчики ---

    def load_html_file(self):
        filepath = filedialog.askopenfilename(
            title="Select HTML File",
            filetypes=[("HTML files", "*.htm *.html"), ("All files", "*.*")]
        )
        if not filepath: return
        print(f"Загрузка HTML: {filepath}")
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
                print(f"Извлечено символов: {len(self.original_text)}")
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
        print("Начало анализа текста...")
        self.root.config(cursor="watch")
        self.root.update_idletasks()
        try:
            self.analyzed_doc = NLP(self.original_text)
            print(f"Анализ завершен. Токенов: {len(self.analyzed_doc)}")
            self._populate_analysis_table()
        except Exception as e:
            messagebox.showerror("Analysis Error", f"Error during analysis:\n{e}")
            print(f"!!! Ошибка анализа spaCy: {e}")
            self.analyzed_doc = None
            self.analysis_tree.delete(*self.analysis_tree.get_children())
        finally:
            self.root.config(cursor="")

    def reanalyze_edited_text(self):
        print("Переанализ текста из редактора...")
        self.analyze_text()

    def _populate_analysis_table(self):
        self.analysis_tree.delete(*self.analysis_tree.get_children())
        self.tree_token_map.clear()
        if not self.analyzed_doc: return
        visible_token_count = 0
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
            iid = f"token_{i}"
            self.tree_token_map[iid] = i
            values = (i, wordform, lemma, pos_tag, morph_str, dep_rel)
            self.analysis_tree.insert("", "end", values=values, iid=iid)
            visible_token_count += 1
        print(f"Таблица анализа заполнена. Отображено токенов: {visible_token_count}")

    def _render_dependency_tree(self, target_label_widget, sentence_index=0):
        global SVG_RENDERER
        target_label_widget.image_tk = None
        if not self.analyzed_doc or not SVG_RENDERER:
            message = "Analysis needed or SVG renderer missing."
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
        print(f"Рендеринг дерева для предложения {sentence_index}...")
        svg_options = {"compact": False, "font": "Arial", "bg": "#fafafa", "color": "#000000", "word_spacing": 15,
                       "arrow_spacing": 20}
        render_dpi = 120
        try:
            svg_code = spacy.displacy.render(sentence_to_render, style="dep", jupyter=False, options=svg_options)
            png_bytes = None
            if SVG_RENDERER == 'cairosvg':
                try:
                    png_bytes = cairosvg.svg2png(bytestring=svg_code.encode('utf-8'), dpi=render_dpi)
                except Exception as e:
                    print(f"Ошибка cairosvg: {e}")
            elif SVG_RENDERER == 'svglib':
                try:
                    drawing = svg2rlg(io.BytesIO(svg_code.encode('utf-8')))
                    if drawing:
                        png_bytes_io = io.BytesIO()
                        renderPM.drawToFile(drawing, png_bytes_io, fmt="PNG")
                        png_bytes = png_bytes_io.getvalue()
                    else:
                        print("svglib не смог создать drawing.")
                except Exception as e:
                    print(f"Ошибка svglib/reportlab: {e}")
            if png_bytes:
                img = Image.open(io.BytesIO(png_bytes))
                image_tk = ImageTk.PhotoImage(img)
                target_label_widget.image_tk = image_tk  # Сохраняем ссылку
                target_label_widget.config(image=image_tk, text="")
                print("Дерево зависимостей отрендерено.")
                return True
            else:
                message = "Failed to convert SVG to PNG."
                target_label_widget.config(image="", text=message)
                print(message)
                return False
        except Exception as e:
            message = f"Error rendering tree:\n{e}"
            target_label_widget.config(image="", text=message)
            print(f"Ошибка при рендеринге дерева: {e}")
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
            target_canvas.update_idletasks()  # Даем время обновиться
            scroll_bbox = target_canvas.bbox("all")
            if scroll_bbox:
                target_canvas.configure(scrollregion=scroll_bbox)
                print(f"Scrollregion обновлен: {scroll_bbox}")
            else:
                print("Не удалось получить bbox.")
            target_canvas.xview_moveto(0)
            target_canvas.yview_moveto(0)  # Сброс прокрутки

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
            messagebox.showerror("Error", "Analysis data missing.")
            return

        # --- ИЗМЕНЕНИЕ: Проверяем видимость окна перед grab_set ---
        # Создаем окно, но пока не делаем grab_set
        popup = tk.Toplevel(self.root)
        popup.title(f"Edit Token {token_index} ('{self.analyzed_doc[token_index].text}')")
        popup.transient(self.root)
        popup.resizable(False, False)

        # ... (остальной код создания виджетов окна редактирования как раньше) ...
        token = self.analyzed_doc[token_index]
        current_override = self.analysis_overrides.get(token_index, {})
        current_data = {"wordform": token.text, "lemma": current_override.get("lemma", token.lemma_),
                        "pos": current_override.get("pos", POS_TAG_TRANSLATIONS.get(token.pos_, token.pos_)),
                        "morph": current_override.get("morph", beautiful_morph(token.morph.to_dict())),
                        "dep": current_override.get("dep", token.dep_)}
        form_frame = ttk.Frame(popup, padding="15")
        form_frame.pack(expand=True, fill="both")
        entries = {}
        fields_to_edit = ['lemma', 'pos', 'morph', 'dep']
        labels = {'lemma': 'Lemma:', 'pos': 'POS Tag:', 'morph': 'Morphology:', 'dep': 'Dependency:'}
        ttk.Label(form_frame, text="Original Token:").grid(row=0, column=0, padx=5, pady=8, sticky="w")
        ttk.Label(form_frame, text=current_data["wordform"], relief="sunken", padding=3).grid(row=0, column=1, padx=5,
                                                                                              pady=8, sticky="ew")
        for i, field in enumerate(fields_to_edit):
            ttk.Label(form_frame, text=labels[field]).grid(row=i + 1, column=0, padx=5, pady=8, sticky="w")
            var = tk.StringVar(
                value=current_data[field])
            entry = ttk.Entry(form_frame, textvariable=var, width=50)
            entry.grid(row=i + 1, column=1, padx=5, pady=8, sticky="ew")
        entries[field] = var
        form_frame.columnconfigure(1, weight=1)
        button_frame = ttk.Frame(popup, padding=(10, 10, 10, 15))
        button_frame.pack(fill="x", side="bottom")
        save_button = ttk.Button(button_frame, text="Save Changes",
                                 command=lambda: self.save_wordform_edit(token_index, entries, popup))
        save_button.pack(side="right", padx=(10, 0))
        cancel_button = ttk.Button(button_frame, text="Cancel", command=popup.destroy)
        cancel_button.pack(side="right", padx=(0, 5))
        popup.update_idletasks()
        first_entry_widget = None
        if fields_to_edit:
            first_entry_widget = form_frame.grid_slaves(row=1, column=1)[0]
        if first_entry_widget:
            first_entry_widget.focus_set()
        parent_x = self.root.winfo_x()
        parent_y = self.root.winfo_y()
        parent_w = self.root.winfo_width()
        parent_h = self.root.winfo_height()
        popup_w = popup.winfo_width()
        popup_h = popup.winfo_height()
        x = parent_x + (parent_w // 2) - (popup_w // 2)
        y = parent_y + (parent_h // 2) - (popup_h // 2)
        popup.geometry(f'+{x}+{y}')

        # --- ИЗМЕНЕНИЕ: Вызываем grab_set ПОСЛЕ того, как окно стало видимым ---
        # Даем Tkinter время отрисовать окно перед захватом
        popup.update_idletasks()
        try:
            # Проверяем, видимо ли окно перед захватом
            if popup.winfo_viewable():
                popup.grab_set()
                print("Grab set successfully.")
            else:
                print("Warning: Popup window not viewable, grab_set skipped.")
        except tk.TclError as e:
            # Ловим ошибку на всякий случай, если проверка не сработала
            print(f"Error during grab_set (window might not be ready): {e}")
            # Можно просто продолжить без grab_set или показать ошибку

    def save_wordform_edit(self, token_index, entries, popup_window):
        print(f"Сохранение переопределений для токена {token_index}")
        new_override = self.analysis_overrides.get(token_index, {}).copy()
        updated = False
        for field, var in entries.items():
            new_value = var.get().strip()
            original_token = self.analyzed_doc[token_index]
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
                if new_value == original_value:
                    if field in new_override:
                        del new_override[field]
                        updated = True
                else:
                    new_override[field] = new_value
                    updated = True
        is_empty_override = not any(f != 'deleted' for f in new_override)
        if is_empty_override or not new_override:
            if token_index in self.analysis_overrides:
                is_deleted = "deleted" in self.analysis_overrides[token_index]
                if is_deleted and len(self.analysis_overrides[token_index]) == 1:
                    del self.analysis_overrides[token_index]
                elif is_deleted:
                    self.analysis_overrides[token_index] = {"deleted": True}
                else:
                    del self.analysis_overrides[token_index]
                updated = True
        elif updated:
            self.analysis_overrides[token_index] = new_override
        popup_window.destroy()
        if updated:
            print(f"Переопределения для токена {token_index} обновлены")
            self._update_treeview_row(token_index)
        else:
            print(f"Изменений для токена {token_index} не внесено.")

    def ignore_selected_wordform(self):
        selected_iid, token_index = self.get_selected_item_details()
        if selected_iid is None: return
        token_text = self.analyzed_doc[token_index].text if self.analyzed_doc and token_index < len(
            self.analyzed_doc) else ""
        confirm = messagebox.askyesno("Confirm Ignore", f"Mark token {token_index} ('{token_text}') as ignored?",
                                      parent=self.root)
        if confirm:
            print(f"Пометка токена {token_index} как удаленного.")
            override = self.analysis_overrides.get(
                token_index, {})
            override["deleted"] = True
            self.analysis_overrides[
                token_index] = override
            self._update_treeview_row(token_index)

    def export_selected_wordform(self):
        selected_iid, token_index = self.get_selected_item_details()
        if selected_iid is None: return
        if not self.analyzed_doc or token_index >= len(self.analyzed_doc):
            messagebox.showerror("Error", "Analysis data missing.")
            return
        token = self.analyzed_doc[token_index]
        override = self.analysis_overrides.get(token_index, {})
        if override.get("deleted", False):
            messagebox.showinfo("Info", f"Token {token_index} ignored.")
            return
        export_entry_data = {"original_wordform": token.text, "lemma": override.get("lemma", token.lemma_),
                             "pos": override.get("pos", POS_TAG_TRANSLATIONS.get(token.pos_, token.pos_)),
                             "morph": override.get("morph", beautiful_morph(token.morph.to_dict())),
                             "dep": override.get("dep", token.dep_),
                             "source_doc": os.path.basename(
                                 self.current_html_path) if self.current_html_path else "N/A"}
        export_key = f"token_{token_index}"
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
                    if not messagebox.askyesno("Overwrite?", f"Entry '{export_key}' exists. Overwrite?"): return
            existing_data[export_key] = export_entry_data
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(existing_data, f, indent=4, ensure_ascii=False)
            messagebox.showinfo("Success", f"Data for '{export_key}' saved.")
        except Exception as e:
            messagebox.showerror("Export Error", f"Could not save data:\n{e}")

    def import_wordform_overrides(self):
        if not self.analyzed_doc:
            messagebox.showwarning("No Data", "Analyze text first.")
            return
        file_path = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")],
                                               title="Select JSON File with Overrides")
        if not file_path:
            return
        print(f"Импорт переопределений из: {file_path}")
        imported_count = 0
        skipped_count = 0
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data_to_import = json.load(f)
            if not isinstance(data_to_import, dict):
                messagebox.showerror("Format Error", "JSON must be a dictionary.")
                return
            num_entries = len(data_to_import)
            if num_entries == 0:
                messagebox.showinfo("Info", "JSON file is empty.")
                return
            if not messagebox.askyesno("Confirm Import", f"Found {num_entries} overrides. Apply to current session?",
                                       parent=self.root): return
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
                if token_index < 0 or token_index >= len(self.analyzed_doc):
                    skipped_count += 1
                    continue
                current_override = self.analysis_overrides.get(token_index, {})
                applied_change = False
                for field, value in override_data.items():
                    if field in ["lemma", "pos", "morph", "dep", "deleted"]:
                        current_override[field] = value
                        applied_change = True
                if applied_change:
                    self.analysis_overrides[token_index] = current_override
                    applied_indices.add(token_index)
                    imported_count += 1
                else:
                    skipped_count += 1
            print(f"Обновление {len(applied_indices)} строк в таблице...")
            [self._update_treeview_row(index) for index in applied_indices]
            print("Обновление таблицы завершено.")
            summary = f"Import finished.\n\nApplied/Updated: {imported_count}\nSkipped: {skipped_count}"
            messagebox.showinfo("Import Complete", summary)
            print(summary.replace('\n\n', ' // '))
        except Exception as e:
            messagebox.showerror("Import Error", f"Error during import:\n{e}")
            print(f"!!! Ошибка импорта: {e}")

    def _update_treeview_row(self, token_index):
        iid = f"token_{token_index}"
        if not self.analysis_tree.exists(iid): return
        if not self.analyzed_doc or token_index >= len(self.analyzed_doc): return
        token = self.analyzed_doc[token_index]
        override = self.analysis_overrides.get(token_index, {})
        if override.get("deleted", False):
            self.analysis_tree.delete(iid)
            return
        values = (token_index, override.get("wordform", token.text).replace("\n", " "),
                  override.get("lemma", token.lemma_).replace("\n", " "),
                  override.get("pos", POS_TAG_TRANSLATIONS.get(token.pos_, token.pos_)).replace("\n", " "),
                  override.get("morph", beautiful_morph(token.morph.to_dict())).replace("\n", " "),
                  override.get("dep", token.dep_).replace("\n", " "))
        try:
            self.analysis_tree.item(iid, values=values)
        except tk.TclError as e:
            print(f"Error updating Treeview item {iid}: {e}")

    def on_closing(self):
        if messagebox.askokcancel("Quit", "Are you sure you want to quit?\nAll unsaved analysis data will be lost."):
            print("Закрытие приложения.")
            self.root.destroy()


# --- Запуск приложения ---
if __name__ == "__main__":
    root = tk.Tk()
    app = SessionAnalysisApp(root)
    root.mainloop()

# --- END OF FILE manager_session.py ---
