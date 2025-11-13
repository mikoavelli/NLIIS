import spacy
from collections import Counter
from utils import clean_token, POS_TAG_TRANSLATIONS_EN, POS_TAG_TRANSLATIONS_RU, beautiful_morph


class TextAnalyzer:
    """Handles linguistic analysis, including spaCy processing and data preparation."""

    def __init__(self):
        """Initializes the analyzer with loaded spaCy models."""
        self.nlp_models = {'en': None, 'ru': None}
        self._load_spacy_model('en_core_web_sm', 'en')
        self._load_spacy_model('ru_core_news_sm', 'ru')

    def _load_spacy_model(self, model_name: str, lang_code: str):
        """Loads a spaCy model into memory."""
        if self.nlp_models.get(lang_code):
            return True
        try:
            print(f"Loading spaCy model '{model_name}'...")
            self.nlp_models[lang_code] = spacy.load(model_name)
            print(f"SpaCy model '{model_name}' loaded successfully.")
            return True
        except OSError:
            print(
                f"ERROR: SpaCy model '{model_name}' not found.\n"
                f"Linguistic analysis for language '{lang_code}' will not work.\n"
                f"Please download the model: python -m spacy download {model_name}"
            )
            self.nlp_models[lang_code] = None
            return False

    @staticmethod
    def prepare_analysis_table_data(doc, word_translations, lang_code):
        """Prepares data structured for the detailed analysis table."""
        table_data = []
        pos_map = POS_TAG_TRANSLATIONS_EN if lang_code == 'en' else POS_TAG_TRANSLATIONS_RU

        for i, token in enumerate(doc):
            if token.is_space:
                continue

            cleaned_lower = clean_token(token.text.lower())
            translation = word_translations.get(cleaned_lower, "-")
            pos_tag = pos_map.get(token.pos_, token.pos_)
            morph_str = beautiful_morph(token.morph.to_dict())

            row = (i, token.text, translation, token.lemma_, pos_tag, morph_str)
            table_data.append(row)
        return table_data

    def prepare_frequency_table_data(self, tokens, word_translations, doc, lang_code):
        """Prepares data structured for the word frequency table."""
        table_data = []
        word_freq = Counter(tokens)

        token_info_map = {}
        pos_map = POS_TAG_TRANSLATIONS_EN if lang_code == 'en' else POS_TAG_TRANSLATIONS_RU
        for token in doc:
            cleaned_lower = clean_token(token.text.lower())
            if cleaned_lower and cleaned_lower not in token_info_map:
                pos_tag = pos_map.get(token.pos_, token.pos_)
                morph_str = beautiful_morph(token.morph.to_dict())
                token_info_map[cleaned_lower] = {
                    "lemma": token.lemma_,
                    "gramm_info": f"POS: {pos_tag}, Morph: {morph_str}"
                }

        sorted_words = sorted(word_freq.items(), key=lambda item: item[1], reverse=True)

        for word, freq in sorted_words:
            if not word:
                continue
            translation = word_translations.get(word, "-")
            info = token_info_map.get(word, {"lemma": "-", "gramm_info": "-"})

            row = (word, translation, freq, info["lemma"], info["gramm_info"])
            table_data.append(row)
        return table_data
