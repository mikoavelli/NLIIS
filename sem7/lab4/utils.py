import re

# English POS tag translations for spaCy models
POS_TAG_TRANSLATIONS_EN = {
    'ADJ': 'adjective', 'ADP': 'adposition', 'ADV': 'adverb', 'AUX': 'auxiliary',
    'CCONJ': 'coordinating conjunction', 'DET': 'determiner', 'INTJ': 'interjection',
    'NOUN': 'noun', 'NUM': 'numeral', 'PART': 'particle', 'PRON': 'pronoun',
    'PROPN': 'proper noun', 'PUNCT': 'punctuation', 'SCONJ': 'subordinating conjunction',
    'SYM': 'symbol', 'VERB': 'verb', 'X': 'other', 'SPACE': 'space'
}

# A simple mapping for Russian POS tags to English for consistency in display
POS_TAG_TRANSLATIONS_RU = {
    'ADJ': 'adjective', 'ADP': 'adposition', 'ADV': 'adverb', 'AUX': 'auxiliary',
    'CCONJ': 'coordinating conjunction', 'DET': 'determiner', 'INTJ': 'interjection',
    'NOUN': 'noun', 'NUM': 'numeral', 'PART': 'particle', 'PRON': 'pronoun',
    'PROPN': 'proper noun', 'PUNCT': 'punctuation', 'SCONJ': 'subordinating conjunction',
    'SYM': 'symbol', 'VERB': 'verb', 'X': 'other', 'SPACE': 'space'
}


def beautiful_morph(data: dict):
    """Formats a morphology dictionary into a human-readable string."""
    if not isinstance(data, dict) or not data:
        return "None"
    return ", ".join([f"{k}={v}" for k, v in data.items()])


def clean_token(text: str) -> str:
    """Removes leading/trailing punctuation and whitespace from a token."""
    return re.sub(r"^[^\w\s]+|[^\w\s]+$", "", text.strip())
