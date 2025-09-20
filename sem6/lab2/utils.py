POS_TAG_TRANSLATIONS = {
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
    'SPACE': 'space'
}


def beautiful_morph(data: dict):
    if not isinstance(data, dict):
        return "None"
    filtered_data = {k: v for k, v in data.items() if v}
    return ", ".join([f"{k}: {v}" for k, v in filtered_data.items()]) if filtered_data else "None"


def clean_token(text: str) -> str:
    return text.strip().strip(",@.'\"")
