import nltk
import re
import json
from nltk.stem import WordNetLemmatizer
from nltk.tag import pos_tag

# nltk.download('averaged_perceptron_tagger')
# nltk.download('wordnet')

lemmatizer = WordNetLemmatizer()


def get_wordnet_pos(treebank_tag):
    if treebank_tag.startswith('J'):
        return 'a'  # Adjective
    elif treebank_tag.startswith('V'):
        return 'v'  # Verb
    elif treebank_tag.startswith('N'):
        return 'n'  # Noun
    elif treebank_tag.startswith('R'):
        return 'r'  # Adverb
    else:
        return 'n'  # Default to noun if mapping not found


def lemmatize_word(word: str, pos_tag: str) -> str:
    wordnet_pos = get_wordnet_pos(pos_tag)
    return lemmatizer.lemmatize(word, pos=wordnet_pos)


def tokenize_text(text: str) -> list[str]:
    """
    Tokenizes the given text into words.
    Removes punctuation, digits, and converts to lowercase.
    """
    text = re.sub(r'[^\w\s]\d+', '', text).lower()
    text = re.sub(r'\d+', '', text)  # Remove digits
    tokens = nltk.word_tokenize(text)
    return tokens


def read_text_file(filepath: str) -> str | None:
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
        print("Error: Unsupported file type.")
        return None


def create_dictionary_from_text(text: str) -> dict:
    """Creates a dictionary from the given text, including part of speech and morphological information."""
    dictionary = {}
    tokens = tokenize_text(text)
    tagged_words = pos_tag(tokens)  # Use pos_tag to get parts of speech

    for token, tag in tagged_words:  # Changed variable name to `tag`
        lemma = lemmatize_word(token, tag)  # Pass POS tag to lemmatize_word
        if lemma in dictionary:
            dictionary[lemma]['frequency'] += 1
        else:
            dictionary[lemma] = {
                'frequency': 1,
                'part_of_speech': tag,
                'morphological_info': get_morphological_info(tag)
            }
    return dictionary


def get_morphological_info(pos_tag: str) -> str:
    """Provides basic morphological information based on the POS tag."""
    if pos_tag.startswith('N'):
        return "Noun"
    elif pos_tag.startswith('V'):
        return "Verb"
    elif pos_tag.startswith('J'):
        return "Adjective"
    elif pos_tag.startswith('R'):
        return "Adverb"
    else:
        return "Other"


def load_dictionary(filepath: str) -> dict:
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            dictionary = json.load(f)
        return dictionary
    except FileNotFoundError:
        print(f"Warning: Dictionary file '{filepath}' not found. Returning empty dictionary.")
        return {}
    except json.JSONDecodeError:
        print(f"Warning: Invalid JSON format in '{filepath}'. Returning empty dictionary.")
        return {}
    except Exception as e:
        print(f"Error loading dictionary from '{filepath}': {e}. Returning empty dictionary.")
        return {}


def save_dictionary(filepath: str, dictionary: dict):
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(dictionary, f, indent=4, ensure_ascii=False)  # Added ensure_ascii=False
        print(f"Dictionary saved to '{filepath}'")
    except Exception as e:
        print(f"Error saving dictionary to '{filepath}': {e}")


def add_word_to_dictionary(dictionary: dict, word: str):
    """Adds a new word to the dictionary."""
    # POS tagging new word
    tagged_word = pos_tag([word])[0]
    tag = tagged_word[1]
    lemma = lemmatize_word(word, tag)  # Lemmatize the token
    if lemma in dictionary:
        print(f"Word '{lemma}' already exists in the dictionary.")
        return dictionary
    dictionary[lemma] = {
        'frequency': 0,
        'part_of_speech': tag,
        'morphological_info': get_morphological_info(tag)
    }
    return dictionary


def remove_word_from_dictionary(dictionary: dict, word: str):
    """Removes a word from the dictionary."""
    # POS tagging new word
    tagged_word = pos_tag([word])[0]
    tag = tagged_word[1]
    lemma = lemmatize_word(word, tag)  # Lemmatize the token
    if lemma not in dictionary:
        print(f"Word '{lemma}' does not exist in the dictionary.")
        return dictionary
    del dictionary[lemma]
    return dictionary


def search_word(dictionary: dict, word: str) -> dict | None:
    """Searches for a word in the dictionary."""
    # POS tagging new word
    tagged_word = pos_tag([word])[0]
    tag = tagged_word[1]
    lemma = lemmatize_word(word, tag)  # Lemmatize the token
    if lemma in dictionary:
        return dictionary[lemma]
    else:
        print(f"Word '{lemma}' not found in the dictionary.")
        return None


def filter_by_frequency(dictionary: dict, min_frequency: int = 0) -> dict:
    """Filters the dictionary to include only words with a frequency greater than or equal to min_frequency."""
    filtered_dictionary = {word: info for word, info in dictionary.items() if info['frequency'] >= min_frequency}
    return filtered_dictionary


def save_words_to_file(filepath: str, words: list[str], dictionary: dict):
    """Appends words and their information to the specified file."""
    try:
        with open(filepath, 'a', encoding='utf-8') as f:
            for word in words:
                # POS tagging new word
                tagged_word = pos_tag([word])[0]
                tag = tagged_word[1]
                lemma = lemmatize_word(word, tag)  # Lemmatize the token
                if lemma in dictionary:
                    word_info = dictionary[lemma]
                    f.write(f"{lemma}: {json.dumps(word_info, ensure_ascii=False)}\n")  # Save as JSON
                else:
                    f.write(f"{lemma}: Not found in dictionary\n")
        print(f"Words saved to '{filepath}'")
    except Exception as e:
        print(f"Error saving words to file: {e}")


def main() -> None:
    content = read_text_file('main.txt')
    print(content)
    dictionary = create_dictionary_from_text(content)
    print(dictionary)
    save_dictionary('example.json', dictionary)


if __name__ == '__main__':
    main()
