import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

JSON_FILE = os.path.join(BASE_DIR, "output", "clearmed_terms_english.json")
HEBREW_JSON_FILE = os.path.join(BASE_DIR, "output", "clearmed_terms_hebrew.json")
DB_FILE = os.path.join(BASE_DIR, "clearmed.db")
XML_FILE = os.path.join(BASE_DIR, "health_topics.xml")
MRCONSO_FILE = os.path.join(BASE_DIR, "MRCONSO.RRF")
