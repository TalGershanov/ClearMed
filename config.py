import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

JSON_FILE = os.path.join(BASE_DIR, "server_init", "data", "clearmed_terms_english.json")
HEBREW_JSON_FILE = os.path.join(BASE_DIR, "server_init", "data", "clearmed_terms_hebrew.json")
DB_FILE = os.path.join(BASE_DIR, "clearmed.db")
XML_FILE = os.path.join(BASE_DIR, "data_preparation", "health_topics.xml")

PRIMARY_LANGUAGE_CODE = "en"

SUPPORTED_LANGUAGES = {
	"en": JSON_FILE,
	"he": HEBREW_JSON_FILE,
}

# DeepL target-language codes for language_code values that don't reduce
# cleanly to .upper() of our internal code (e.g. DeepL sometimes requires a
# regional variant such as "EN-US"/"PT-BR"/"ZH-HANS"). Add an override here
# per-language as new languages are added; anything absent falls back to
# .upper().
DEEPL_TARGET_LANG_OVERRIDES = {}

def get_deepl_target_lang(language_code):
	return DEEPL_TARGET_LANG_OVERRIDES.get(language_code, language_code.upper())
