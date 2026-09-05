"""
Standalone, manual-only tool: refresh the short_explanation of every existing
'he'-language explanations row (from the infomed.co.il scrape -- see
populate_hebrew_terms.py/hebrew_terms.py) using
create_clearmed_db.populate_hebrew_translations() -- the exact same function
the normal bootstrap pipeline's Hebrew stage calls, so there is exactly one
implementation of this loop to maintain.

Use this when you want to re-translate to Hebrew without re-running V7,
re-scraping infomed.co.il, or rebuilding the database from source data.

Guarantees (enforced by populate_hebrew_translations() itself):
  - Never calls V7 / select_short_explanation_ai -- only reads the matched
    English concept's already-stored short_explanation.
  - Never modifies term_name, simple_explanation, or any 'en'-language row --
    the only SQL statement that touches a row is
    `UPDATE explanations SET short_explanation = ? WHERE explanation_id = ?`,
    scoped to the 'he' row itself.
  - Never touches the Trie, the DAL layer, or table schema.
  - If translation fails for a row, that row's existing short_explanation
    (the English-copy placeholder, or a previously valid translation) is
    left untouched.
  - Does NOT run automatically anywhere except as the last step of
    server_init/bootstrap.py. Can also be invoked standalone at any time:
        python server_init/retranslate_hebrew.py

Usage:
    python server_init/retranslate_hebrew.py
"""

import os

import create_clearmed_db as cdb


if __name__ == "__main__":
	if not os.environ.get("OPENAI_API_KEY"):
		print("OPENAI_API_KEY is not set in the environment. Stopping.")
		raise SystemExit(1)
	from log_config import setup_logging
	setup_logging()

	result = cdb.populate_hebrew_translations()

	print(f"Rows read: {result['total']}")
	print(f"  updated (new Hebrew translation stored): {result['updated']}")
	print(f"  skipped (no English short_explanation to translate from): {result['skipped_no_source']}")
	print(f"  failed (existing short_explanation, if any, preserved): {result['failed']}")
