import os

from dotenv import load_dotenv

# Loaded here (not left to whichever module happens to import config.py
# first) so CLEARMED_DB_FILE below is read reliably regardless of import
# order -- webapp/core/config.py's own load_dotenv() runs later in
# server/api.py's import chain, which is too late for the module-level
# os.environ.get() call a few lines down.
load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

JSON_FILE = os.path.join(BASE_DIR, "server_init", "data", "clearmed_terms_english.json")
HEBREW_JSON_FILE = os.path.join(BASE_DIR, "server_init", "data", "clearmed_terms_hebrew.json")
# CLEARMED_DB_FILE lets a build write to a DB file other than the live
# clearmed.db (e.g. server_init/build_finetuned_db.py, which must never touch
# the v7-built production file) -- unset in normal/server operation, so the
# live server always resolves to clearmed.db exactly as before.
DB_FILE = os.environ.get("CLEARMED_DB_FILE", os.path.join(BASE_DIR, "clearmed.db"))
XML_FILE = os.path.join(BASE_DIR, "data_preparation", "health_topics.xml")

# Separate SQLite file for temporary, publicly-readable document shares (the
# QR-code flow) -- never the same file as DB_FILE, so this feature can never
# accidentally read/write the read-only verified-term database.
SHARES_DB_FILE = os.path.join(BASE_DIR, "shares.db")

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
