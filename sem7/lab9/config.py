import os
import json
import glob
import alsaaudio

LANGUAGES_JSON_PATH = 'languages.json'
LANGUAGE_CHOICE_FILE = 'lang.conf'

VOSK_RATE = 16000
ALSA_CHANNELS = 1
ALSA_FORMAT = alsaaudio.PCM_FORMAT_S16_LE
ALSA_PERIOD_SIZE = 1024
ALSA_DEVICE = 'default'
COLOR_PARTIAL_TEXT = "gray"
COLOR_FINAL_TEXT = "black"


def _load_all_lang_data():
    """Loads the entire language configuration from the JSON file."""
    try:
        with open(LANGUAGES_JSON_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _find_available_languages(all_lang_data):
    """Scans for model directories and returns a list of verified languages."""
    langs = []
    for path in glob.glob('model_*'):
        if os.path.isdir(path):
            lang_code = path.split('_')[-1]
            if lang_code in all_lang_data:
                langs.append(lang_code)
    return sorted(langs)


def _load_language_setting(available_langs):
    """Loads the chosen language from the config file, with a fallback."""
    try:
        with open(LANGUAGE_CHOICE_FILE, 'r') as f:
            lang = f.read().strip()
            if lang in available_langs:
                return lang
    except FileNotFoundError:
        pass
    return available_langs[0] if available_langs else None


ALL_LANG_DATA = _load_all_lang_data()
AVAILABLE_LANGS = _find_available_languages(ALL_LANG_DATA)
MODELS_FOUND = bool(AVAILABLE_LANGS)

if MODELS_FOUND:
    CURRENT_LANG = _load_language_setting(AVAILABLE_LANGS)
    CONFIG = ALL_LANG_DATA[CURRENT_LANG]
else:
    CURRENT_LANG = 'en'
    CONFIG = ALL_LANG_DATA.get('en', {
        'messages': {'error_no_models': 'No Vosk models found.'}
    })
