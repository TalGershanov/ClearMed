# Shared between scrape_infomed_to_json.py (website -> JSON, run rarely) and
# populate_hebrew_terms.py (JSON -> DB, run on every rebuild): the DB-write
# primitive and the "is this concept already done" check are identical in
# both, so they live here once instead of being duplicated.

import logging

logger = logging.getLogger("clearmed.server_init.hebrew_terms")

HEBREW_LANG = "he"
ENGLISH_LANG = "en"


def upsert_hebrew_explanation(connection, concept_id, short_explanation, hebrew_names, english_names, body_text):
	with connection:
		connection.execute(
			"""
			INSERT OR IGNORE INTO explanations (concept_id, language_code, term_name, simple_explanation, short_explanation)
			VALUES (?, ?, ?, ?, ?)
			""",
			(
				concept_id,
				HEBREW_LANG,
				hebrew_names[0],
				body_text,
				# PLACEHOLDER: copied verbatim from the matched English
				# concept at scrape time, not translated. To generate a real
				# Hebrew short explanation via OpenAI instead (e.g. once an
				# improved selection/translation prompt exists), change what
				# gets written into output/clearmed_terms_hebrew.json for
				# this field, mirroring select_short_explanation_ai() in
				# server_init/create_clearmed_db.py.
				short_explanation,
			),
		)
		alias_rows = [(name, concept_id, HEBREW_LANG) for name in hebrew_names] + \
			[(name, concept_id, ENGLISH_LANG) for name in english_names]
		# One row at a time (not executemany) so a dropped INSERT OR IGNORE
		# -- alias_text is a table-wide primary key, so this happens whenever
		# two different concepts share an alias string -- gets logged instead
		# of silently vanishing.
		for alias_text, alias_concept_id, language_code in alias_rows:
			cursor = connection.execute(
				"INSERT OR IGNORE INTO term_aliases (alias_text, concept_id, language_code) VALUES (?, ?, ?)",
				(alias_text, alias_concept_id, language_code),
			)
			if cursor.rowcount == 0:
				logger.warning(
					"Alias %r not inserted for concept_id=%r (language_code=%r) -- "
					"alias_text already claimed by a different concept",
					alias_text, alias_concept_id, language_code,
				)


def already_scraped(connection, concept_id):
	row = connection.execute(
		"SELECT 1 FROM explanations WHERE concept_id = ? AND language_code = ?",
		(concept_id, HEBREW_LANG),
	).fetchone()
	return row is not None
