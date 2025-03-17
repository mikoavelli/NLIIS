import nltk

import regex as re
import tkinter as tk
from tkinter import ttk, messagebox
from nltk.stem import WordNetLemmatizer
from nltk.tokenize import word_tokenize
from striprtf.striprtf import rtf_to_text


def read_text_file(filepath: str):
    if filepath.endswith('.txt'):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            return content
        except FileNotFoundError:
            print(f"Error: File '{filepath}' not found.")
            return None
        except Exception as e:
            print(f"Error reading file '{filepath}': {e}")
            return None
    elif filepath.endswith('.rtf'):
        try:
            with open(filepath) as f:
                content = rtf_to_text(f.read())
            return content
        except FileNotFoundError:
            print(f"Error: File '{filepath}' not found.")
            return None
        except Exception as e:
            print(f"Error reading file '{filepath}': {e}")
            return None
    else:
        raise "Unsupported file type."


def preprocess_text(text: str):
    if text is None:
        return []

    tokens = word_tokenize(text)
    tokens = [token.lower() for token in tokens]
    tokens = [token for token in tokens if token.isalpha()]
    tokens = [token for token in tokens if token]

    return tokens


def lemmatize_tokens(tokens: list):
    lemmatizer = WordNetLemmatizer()

    def get_wordnet_pos(word):
        tag = nltk.pos_tag([word])[0][1][0].upper()
        tag_dict = {"J": nltk.corpus.wordnet.ADJ,
                    "N": nltk.corpus.wordnet.NOUN,
                    "V": nltk.corpus.wordnet.VERB,
                    "R": nltk.corpus.wordnet.ADV}

        return tag_dict.get(tag, nltk.corpus.wordnet.NOUN)

    lemmatized_tokens = [lemmatizer.lemmatize(token, get_wordnet_pos(token)) for token in tokens]
    return lemmatized_tokens


def create_word_data(tokens: list):
    word_data = {}
    for token in tokens:
        lemma = lemmatize_tokens([token])[0]
        if lemma not in word_data:
            word_data[lemma] = {
                "word_forms": {token: 1},
                "morphology": {
                    "part_of_speech": nltk.pos_tag([token])[0][1],
                    "user_defined": {}
                }
            }
        else:
            if token not in word_data[lemma]["word_forms"]:
                word_data[lemma]["word_forms"][token] = 1
            else:
                word_data[lemma]["word_forms"][token] += 1
    return word_data


def create_gui(word_data):
    root = tk.Tk()
    root.title("Word Data Editor")

    lemma_listbox = tk.Listbox(root, width=20)
    lemma_listbox.pack(side=tk.LEFT, fill=tk.Y)

    for lemma in sorted(word_data.keys()):
        lemma_listbox.insert(tk.END, lemma)

    details_frame = tk.Frame(root)
    details_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    lemma_label = tk.Label(details_frame, text="Lemma:")
    lemma_label.pack()
    lemma_value = tk.StringVar()
    lemma_display = tk.Label(details_frame, textvariable=lemma_value)
    lemma_display.pack()

    word_forms_label = tk.Label(details_frame, text="Word Forms:")
    word_forms_label.pack()
    word_forms_text = tk.Text(details_frame, height=5, width=30)
    word_forms_text.pack()

    pos_label = tk.Label(details_frame, text="Part of Speech:")
    pos_label.pack()
    pos_choices = ["NN", "VB", "JJ", "RB", "DT", "IN", "CC", "PRP"]
    pos_value = tk.StringVar()
    pos_combobox = ttk.Combobox(details_frame, textvariable=pos_value, values=pos_choices)
    pos_combobox.pack()

    def populate_details(event):
        selected_lemma_index = lemma_listbox.curselection()
        if selected_lemma_index:
            selected_lemma = lemma_listbox.get(selected_lemma_index[0])
            lemma_value.set(selected_lemma)

            word_forms_text.delete("1.0", tk.END)
            word_forms = word_data[selected_lemma]["word_forms"]
            word_forms_string = "\n".join([f"{form}: {freq}" for form, freq in word_forms.items()])
            word_forms_text.insert(tk.END, word_forms_string)

            pos_value.set(word_data[selected_lemma]["morphology"]["part_of_speech"])

    def save_changes():
        selected_lemma_index = lemma_listbox.curselection()
        if selected_lemma_index:
            selected_lemma = lemma_listbox.get(selected_lemma_index[0])
            new_pos = pos_value.get()

            word_data[selected_lemma]["morphology"]["part_of_speech"] = new_pos

            messagebox.showinfo("Info", "Changes saved!")
        else:
            messagebox.showerror("Error", "No lemma selected.")

    lemma_listbox.bind("<<ListboxSelect>>", populate_details)

    save_button = tk.Button(details_frame, text="Save", command=save_changes)
    save_button.pack()

    return root, word_data


def main():
    text = read_text_file("main.txt")
    tokens = preprocess_text(text)

    print(create_word_data(lemmatize_tokens(tokens)))


if __name__ == '__main__':
    main()
