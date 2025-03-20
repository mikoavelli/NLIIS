import spacy
import time
import matplotlib.pyplot as plt
import re

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


def get_morphological_info(word):
    doc = nlp(word)
    for token in doc:
        morphological_info = {
            'text': token.text,
            'lemma': token.lemma_,
            'pos': pos_tag_translations[token.pos_],
        }
        return morphological_info
    return None


def analyze_file(filepath):
    text_lengths = []
    processing_times = []
    word_counts = [i for i in range(100, 2000, 100)]
    for word_count in word_counts:

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                text = f.read().lower()
                text = re.sub(r'{\\.*?}', '', text)
                text = re.sub(r'\\[a-z]+(?:-?\d+)? ?', '', text)

                text = re.sub(r'\s+', ' ', text).strip()
            tokens = text.split()[:word_count]
        except Exception as e:
            print(f"Error reading file: {e}")
            return None, None

        start_time = time.time()
        for word in tokens:
            word = word.strip(".").strip(",").strip('"').strip("'").strip("`").strip(":").strip("?").strip("!").strip(
                '(').strip(')').strip('[').strip(']').strip('{').strip('}').strip('@').strip('#').strip('№').strip(
                '$').strip(';').strip('<').strip('>').strip('/').strip('*').strip('%').strip('^').strip('&').strip('*')
            get_morphological_info(word)

        end_time = time.time()
        processing_time = end_time - start_time

        text_lengths.append(word_count)
        processing_times.append(processing_time)
        print(f"File: {filepath}, Word Count: {word_count}, Time: {processing_time}")

    return text_lengths, processing_times


filepath_txt = 'example.txt'
filepath_rtf = 'example.rtf'

text_lengths_txt, processing_times_txt = analyze_file(filepath_txt)
text_lengths_rtf, processing_times_rtf = analyze_file(filepath_rtf)

if text_lengths_txt and processing_times_txt:
    plt.plot(text_lengths_txt, processing_times_txt, label='TXT File')
if text_lengths_rtf and processing_times_rtf:
    plt.plot(text_lengths_rtf, processing_times_rtf, label='RTF File')

plt.xlabel('Number of words')
plt.ylabel('Processing time (с)')
plt.title('Text Word Count vs Processing Time')
plt.legend()
plt.show()
