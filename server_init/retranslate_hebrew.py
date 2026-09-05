"""
Standalone, manual-only tool: refresh short_explanation_he for every existing
DB row using create_clearmed_db.populate_hebrew_translations() -- the exact
same function the normal bootstrap pipeline's Hebrew stage calls, so there is
exactly one implementation of this loop to maintain.

Use this when you want to re-translate to Hebrew without re-running V7 or
rebuilding the database from MedlinePlus source data.

Guarantees (enforced by populate_hebrew_translations() itself):
  - Never calls V7 / select_short_explanation_ai -- only reads the already-
    stored short_explanation column.
  - Never modifies short_explanation, simple_explanation, term, synonyms,
    categories, or source_id -- the only SQL statement that touches a row is
    `UPDATE medical_terms SET short_explanation_he = ? WHERE id = ?`.
  - Never touches the Trie, the DAL layer, or table schema.
  - If translation fails for a row, that row's existing short_explanation_he
    (NULL or a previously valid translation) is left untouched.
  - Does NOT run automatically anywhere (not from bootstrap.py, not from the
    server). Must be invoked explicitly:
        python server_init/retranslate_hebrew.py

Usage:
    python server_init/retranslate_hebrew.py
"""

import os
import sqlite3

import create_clearmed_db as cdb


if __name__ == "__main__":
	if not os.environ.get("OPENAI_API_KEY"):
		print("OPENAI_API_KEY is not set in the environment. Stopping.")
		raise SystemExit(1)
	from log_config import setup_logging
	setup_logging()

	connection = sqlite3.connect(cdb.DB_FILE)
	cursor = connection.cursor()
	result = cdb.populate_hebrew_translations(cursor, connection)
	connection.close()

	print(f"Rows read: {result['total']}")
	print(f"  updated (new Hebrew translation stored): {result['updated']}")
	print(f"  skipped (no short_explanation to translate from): {result['skipped_no_source']}")
	print(f"  failed (existing short_explanation_he, if any, preserved): {result['failed']}")
