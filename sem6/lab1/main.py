import re
import tkinter as tk
from collections import Counter
from tkinter import filedialog
from tkinter import ttk
import tkinter.messagebox as messagebox
import spacy
import os
import json
from idlelib.tooltip import Hovertip
from striprtf.striprtf import rtf_to_text

nlp = spacy.load('en_core_web_sm')

pos_tag_translations = {
    'ADJ': 'adjective',
    'ADP': 'adposition',
    'ADV': 'adverb',
    'AUX': 'auxiliary',
    'CCONJ': 'coordinating conjunction',
    'DET': 'determiner',
    'INTJ': 'interjection',
    'NOUN': 'noun',
    'NUM': 'numeral',
    'PART': 'particle',
    'PRON': 'pronoun',
    'PROPN': 'proper noun',
    'PUNCT': 'punctuation',
    'SCONJ': 'subordinating conjunction',
    'SYM': 'symbol',
    'VERB': 'verb',
    'X': 'other',
}


def validate_numeric_input(input):
    pattern = r'^\d*$'
    return re.match(pattern, input) is not None


def get_lemma(word):
    doc = nlp(word)
    lemma = None
    for token in doc:
        lemma = token.lemma_
    return lemma


def get_morphological_info(word):
    doc = nlp(word)
    morphological_info = None
    for token in doc:
        morphological_info = {
            'lemma': token.lemma_,
            'pos': pos_tag_translations[token.pos_],
            'morph': token.morph.to_dict()
        }
        return morphological_info # Exit after the first token
    return {'lemma': word, 'pos': 'unknown', 'morph': None} # Handle unrecognized words


def beautiful(data: dict):
    morph_string = ", ".join([f"{k}: {v}" for k, v in data['morph'].items()]) if data['morph'] else "None"
    return f"Lemma: {data['lemma']}, Pos: {data['pos']}, Morph: {morph_string}"


class MyApp:
    def __init__(self, root, db):
        self.db = db
        self.show = db
        self.root = root
        self.columns = ("Word", "Lexeme", "Morphologic Info", "Occurrences")
        self.root.title("Text Analyzer")
        self.root.geometry("1600x1600")
        style = ttk.Style()
        # style.theme_use("clam")
        style.configure("Treeview", rowheight=40)

        self.apply_button = None

        self.file_path = tk.StringVar()
        self.file_label = ttk.Label(root, text="Selected File:")
        self.file_label.pack(pady=10)
        self.file_entry = ttk.Entry(root, textvariable=self.file_path, state='disabled', width=40)
        Hovertip(self.file_entry,
                 "This field shows the path to the file that is currently selected. To change it press `Select File` button below.")
        self.file_entry.pack(pady=10)
        self.file_button = ttk.Button(root, text="Select File", command=self.select_file)
        Hovertip(self.file_button,
                 "Press this button in order to choose a file to analyze.\nThe application supports .txt and .rtf formats.")
        self.file_button.pack(pady=10)

        self.analyze_button = ttk.Button(root, text="Analyze File", command=self.analyze_file)
        self.analyze_button.pack(pady=10)
        Hovertip(self.analyze_button,
                 "Press this button in order to start the process of analyzing the text file specified higher.\nYou will see the results lower in the table.")

        container = tk.Frame(root)
        container.pack()

        self.word_var = tk.StringVar()
        word_label = tk.Label(container, text="Word:")
        word_label.pack(side="left")
        word_entry = tk.Entry(container, textvariable=self.word_var)
        word_entry.pack(side="left")
        Hovertip(word_entry, "In this entry you can put a word or a part of a word, \n\
        and only rows where the word matches your input will be shown in the table below. \n\
        You can leave this field empty, then no filtering will be performed.")

        self.lexeme_var = tk.StringVar()
        lexeme_label = tk.Label(container, text="Lexeme:")
        lexeme_label.pack(side="left")
        lexeme_entry = tk.Entry(container, textvariable=self.lexeme_var)
        lexeme_entry.pack(side="left")
        Hovertip(lexeme_entry, "In this entry you can put a lexeme or a part of a lexeme, \n\
        and only rows where the lexeme matches your input will be shown in the table below. \n\
        You can leave this field empty, then no filtering will be performed.")

        self.info_var = tk.StringVar()
        morphologic_label = tk.Label(container, text="Morphologic Info:")
        morphologic_label.pack(side="left")
        morphologic_entry = tk.Entry(container, textvariable=self.info_var)
        morphologic_entry.pack(side="left")
        Hovertip(morphologic_entry, "In this entry you can put some text that contains morphological info, \n\
        and only rows where morphological info matches your input will be show in the table below. \n\
        You can leave this field empty, then no filtering will be performed.")

        validate_numeric = root.register(validate_numeric_input)

        occurences_label = tk.Label(container, text="Occurences:")
        occurences_label.pack(side="left")

        self.occurences_lower_var = tk.StringVar()
        occurences_lower_entry = tk.Entry(container, width=5, validate="key", validatecommand=(validate_numeric, "%P"),
                                          textvariable=self.occurences_lower_var)
        occurences_lower_entry.pack(side="left")
        Hovertip(occurences_lower_entry, "In this entry you can put a number, so only word with number of occurences \n\
        higher than your input will be shown in the table below. \n\
        You can leave this field empty, then no filtering will be performed.")

        tk.Label(container, text=" <= x <= ").pack(side="left")

        self.occurences_higher_var = tk.StringVar()
        occurences_higher_entry = tk.Entry(container, width=5, validate="key", validatecommand=(validate_numeric, "%P"),
                                           textvariable=self.occurences_higher_var)
        occurences_higher_entry.pack(side="left")
        Hovertip(occurences_higher_entry, "In this entry you can put a number, so only words with number of occurences \n\
        lower than your input will be shown in the table below. \n\
        You can leave this field empty, then no filtering will be performed.")

        self.word_var.trace_add("write", self.on_entry_change)
        self.lexeme_var.trace_add("write", self.on_entry_change)
        self.info_var.trace_add("write", self.on_entry_change)
        self.occurences_lower_var.trace_add("write", self.on_entry_change)
        self.occurences_higher_var.trace_add("write", self.on_entry_change)
        self.table_frame = ttk.Frame(root)
        self.table_frame.pack(pady=10)
        self.tree = ttk.Treeview(self.table_frame, columns=self.columns, show="headings", height=20)
        Hovertip(self.tree, "This table represents the database of the application.\n\
        The first row shows the word for which all information is shown.\n\
        The second row shows morphologic information about the word.\n\
        The third row shows number of occurences of this word in analyzed texts.")

        for col in self.columns:
            self.tree.heading(col, text=col, command=lambda c=col: self.sortby(self.tree, c, 0))
            self.tree.column(col, width=500)

        self.tree.pack(side="left")
        self.edit_button = ttk.Button(root, text="Edit Selected", command=self.edit_selected, width=20)
        Hovertip(self.edit_button, "Before pressing this button, choose a row from the table above. Pressing this button will allow you to change\n\
                 morphological information for the word, if it is incorrect or not full.")
        self.edit_button.pack(pady=10)

        self.edit_button = ttk.Button(root, text="Delete Selected", command=self.delete_selected, width=20)
        Hovertip(self.edit_button, "Delete selected element. \n.")
        self.edit_button.pack(pady=10)

        self.edit_button = ttk.Button(root, text="Import Selected", command=self.import_selected, width=20)
        Hovertip(self.edit_button, "Import selectde word to a choisen file if word already exists\n\
                         dialog will pop up.")
        self.edit_button.pack(pady=10)

        self.edit_entries = []
        for col in ("Word", "Morphologic Info"):
            entry = ttk.Entry(root, width=50)
            entry.pack()
            if col == "Word":
                entry["state"] = "disabled"
                Hovertip(entry, "This field shows the word, that you are currently editing.")
            else:
                Hovertip(entry, "This field shows morphologic information that you're editing right now.")
            self.edit_entries.append(entry)

        for item in self.tree.get_children():
            self.tree.delete(item)

        self.populate_tree()

        if len(self.db) == 0:
            messagebox.showinfo("Your first time", "Congratulations on the first time using our application.\n\
        This application will help you analyze natural-language texts,\n\
        If you're not familiar with application, check out tooltips that appear\n\
        when you hover on different parts of the application.")

    def sortby(self, tree, col, descending):
        data = [(tree.set(child, col), child) for child in tree.get_children('')]
        data.sort(reverse=descending)

        for index, item in enumerate(data):
            tree.move(item[1], '', index)

        tree.heading(col, command=lambda col=col: self.sortby(tree, col, int(not descending)))


    def populate_tree(self):
        # Sort the words alphabetically
        sorted_words = sorted(self.show.keys())

        for word in sorted_words:
            info = self.show[word]
            self.tree.insert("", "end", values=(word, get_lemma(word), beautiful(info[1]), info[0]))

    def on_entry_change(self, *args):
        word_filter = self.word_var.get()
        lexeme_filter = self.lexeme_var.get()
        info_filter = self.info_var.get()
        low_occ = self.occurences_lower_var.get()
        low_occ = None if low_occ == "" else int(low_occ)
        high_occ = self.occurences_higher_var.get()
        high_occ = None if high_occ == "" else int(high_occ)

        to_show = {}
        for key, value in self.db.items():
            lemma = get_lemma(key)
            check_word_filter = word_filter in key
            check_lexeme_filter = lexeme_filter in lemma
            check_info_filter = info_filter in beautiful(value[1])
            check_low_occ_filter = True
            if low_occ is not None:
                check_low_occ_filter = value[0] >= low_occ
            check_high_occ_filter = True
            if high_occ is not None:
                check_high_occ_filter = value[0] <= high_occ

            if check_word_filter and check_lexeme_filter and check_info_filter and check_low_occ_filter and check_high_occ_filter:
                to_show[key] = value

        self.show = to_show

        for item in self.tree.get_children():
            self.tree.delete(item)

        self.populate_tree()

    def edit_selected(self):
        selected_item = self.tree.selection()

        if not selected_item:
            messagebox.showinfo("Info", "No item was selected")
            return

        values = self.tree.item(selected_item, 'values')
        word = values[0]
        morph_info_str = values[2]

        self.edit_entries[0]["state"] = "normal"
        self.edit_entries[0].delete(0, tk.END)
        self.edit_entries[0].insert(0, word)
        self.edit_entries[0]["state"] = "disabled"

        self.edit_entries[1].delete(0, tk.END)
        self.edit_entries[1].insert(0, morph_info_str)

        if not self.apply_button:
            self.apply_button = ttk.Button(self.root, text="Apply Changes",
                                           command=lambda: self.apply_changes(selected_item, word))
            Hovertip(self.apply_button,
                     "Press this button, when you're done editing morphologic info for the word and it will be saved in the database.")
            self.apply_button.pack(pady=5)

    def delete_selected(self):
        selected_item = self.tree.selection()

        if not selected_item:
            messagebox.showinfo("Info", "No item was selected")
            return

        values = self.tree.item(selected_item, 'values')
        word = values[0]

        answer = messagebox.askyesno("Question", f"Are you sure you want to delete {word}?")
        if answer:
            del self.db[word]
            self.show = self.db.copy()

            self.tree.delete(selected_item)
            messagebox.showinfo("Info", f"Successfully deleted {word}")

    def import_selected(self):
        selected_item = self.tree.selection()

        if not selected_item:
            messagebox.showinfo("Info", "No item was selected")
            return

        values = self.tree.item(selected_item, 'values')
        word = values[0]

        file_path = filedialog.asksaveasfilename(defaultextension=".json",
                                                 filetypes=[("JSON files", "*.json"), ("All files", "*.*")])

        if file_path:
            export_data = {word: self.db[word]}

            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        try:
                            existing_data = json.load(f)
                        except json.JSONDecodeError:
                            existing_data = {}

                    if word in existing_data:
                        overwrite = messagebox.askyesno("Overwrite?",
                                                        f"The word '{word}' already exists in the file. Overwrite?")
                        if overwrite:
                            existing_data[word] = export_data[word]
                        else:
                            return

                    else:
                        existing_data.update(export_data)

                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump(existing_data, f, indent=4, ensure_ascii=False)

                    messagebox.showinfo("Success", f"Data for '{word}' appended/overwritten to {file_path}")

                except Exception as e:
                    messagebox.showerror("Error", f"Error appending data: {e}")
            else:
                try:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump(export_data, f, indent=4, ensure_ascii=False)
                    messagebox.showinfo("Success", f"Data for '{word}' exported to {file_path}")
                except Exception as e:
                    messagebox.showerror("Error", f"Error exporting data: {e}")

    def apply_changes(self, selected_item, original_word):
        new_morph_info_str = self.edit_entries[1].get()

        if original_word in self.db:
            occurrences = self.db[original_word][0]

            try:
                parts = new_morph_info_str.split(", ")
                lemma = parts[0].split(": ")[1]
                pos = parts[1].split(": ")[1]
                morph_str = parts[2].split(": ")[1]

                morph = {}
                if morph_str != "None":
                    morph_str = morph_str.strip("{}")
                    morph_pairs = morph_str.split("=")
                    if len(morph_pairs) == 2:
                        key = morph_pairs[0]
                        val = morph_pairs[1]
                        morph[key] = val

                new_morph_info = {'lemma': lemma, 'pos': pos, 'morph': morph}

                self.db[original_word] = [occurrences, new_morph_info]
            except Exception as e:
                messagebox.showerror("Error", f"Error parsing morphological info: {e}")
                return

            self.tree.item(selected_item, values=(original_word, get_lemma(original_word), new_morph_info_str, occurrences))
        else:
            messagebox.showinfo("Info", "Word not found in the database.")

        if self.apply_button:
            self.apply_button.destroy()
            self.apply_button = None

        self.edit_entries[1].delete(0, tk.END)

    def select_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("Text Files", "*.txt *.rtf"), ("All Files", "*.*")])

        if file_path:
            self.file_path.set(file_path)

    def analyze_file(self):
        path = self.file_path.get()
        if not (path.endswith(".txt") or path.endswith(".rtf")):
            messagebox.showerror("Error", "File type not supported.")
            return

        if path.endswith(".rtf"):
            with open(path) as f:
                rtf_content = f.read()
                text = rtf_to_text(rtf_content).replace("\n", " ").lower()
        elif path.endswith(".txt"):
            with open(path) as f:
                text = f.read().replace("\n", " ").lower()
        tokens = text.split(" ")

        counter = Counter(tokens)
        occurrences_map = dict(counter.items())

        if "" in occurrences_map:
            occurrences_map.pop("")

        for word, occurrences in occurrences_map.items():
            word = word.strip(".").strip(",").strip('"').strip("'").strip("`").strip(":").strip("?").strip("!").strip(
                '(').strip(')').strip('[').strip(']').strip('{').strip('}').strip('@').strip('#').strip('№').strip(
                '$').strip(';').strip('<').strip('>').strip('/').strip('*').strip('%').strip('^').strip('&').strip('*')
            if word in self.db:

                self.db[word][0] += occurrences
            else:
                self.db[word] = [occurrences, get_morphological_info(word)]

        self.show = self.db.copy()

        for item in self.tree.get_children():
            self.tree.delete(item)

        self.populate_tree()


if __name__ == "__main__":
    root = tk.Tk()
    db_path = "lab1/db.json"

    db = {}
    if os.path.exists(db_path):
        with open(db_path) as file:
            db = json.loads(file.read())

    app = MyApp(root, db)
    root.mainloop()

    with open(db_path, "w") as file:
        json.dump(app.db, file, indent=2, ensure_ascii=False)
