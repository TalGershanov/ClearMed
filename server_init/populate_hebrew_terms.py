import json
import logging
import sqlite3

import bootstrap
_ = bootstrap  # side-effect import: puts the repo root on sys.path (see server_init/bootstrap.py)
from config import DB_FILE, HEBREW_JSON_FILE
from hebrew_terms import ENGLISH_LANG, upsert_hebrew_explanation

logger = logging.getLogger("clearmed.server_init.populate_hebrew_terms")


def purge_umls_hebrew_data(connection):
	# Only 'HEB' (the old MRCONSO/populate_umls.py tag) is legacy data to
	# retire. 'he' is this pipeline's own current output.
	before_aliases = connection.execute("SELECT COUNT(*) FROM term_aliases WHERE language_code = 'HEB'").fetchone()[0]
	with connection:
		connection.execute("DELETE FROM term_aliases WHERE language_code = 'HEB'")
		connection.execute("""
			DELETE FROM concepts
			WHERE concept_id NOT IN (SELECT concept_id FROM term_aliases)
			  AND concept_id NOT IN (SELECT concept_id FROM explanations)
		""")
	after_concepts = connection.execute("SELECT COUNT(*) FROM concepts").fetchone()[0]
	logger.info("Purged %d UMLS Hebrew alias row(s); %d concept(s) remain", before_aliases, after_concepts)


def populate_hebrew_terms():
	connection = sqlite3.connect(DB_FILE)
	connection.execute("PRAGMA foreign_keys = ON")
	purge_umls_hebrew_data(connection)

	with open(HEBREW_JSON_FILE, "r", encoding="utf-8") as f:
		data = json.load(f)
	terms = data["terms"]

	inserted = skipped = 0
	for term in terms:
		concept_id = term["concept_id"]
		exists = connection.execute(
			"SELECT 1 FROM explanations WHERE concept_id = ? AND language_code = ?",
			(concept_id, ENGLISH_LANG),
		).fetchone()
		if exists is None:
			logger.warning(
				"Skipping Hebrew term for concept_id=%r: no matching English concept in the current DB "
				"(the English source JSON may have changed since this Hebrew JSON was captured)",
				concept_id,
			)
			skipped += 1
			continue
		upsert_hebrew_explanation(
			connection, concept_id, term["short_explanation"],
			term["hebrew_names"], term["english_names"], term["simple_explanation"],
		)
		inserted += 1

	connection.close()
	print(f"Hebrew terms read from {HEBREW_JSON_FILE}: {len(terms)}")
	print(f"Inserted: {inserted}")
	print(f"Skipped (no matching English concept in current DB): {skipped}")


if __name__ == "__main__":
	from log_config import setup_logging
	setup_logging()
	populate_hebrew_terms()
