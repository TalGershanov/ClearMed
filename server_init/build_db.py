import json
import logging
import os

import bootstrap
_ = bootstrap  # side-effect import: puts the repo root on sys.path (see server_init/bootstrap.py)
from config import DB_FILE, PRIMARY_LANGUAGE_CODE, SUPPORTED_LANGUAGES, get_deepl_target_lang
from DAL.db import SQLiteDatabase
# ai_services (imported next) calls load_dotenv() at module load time, so the
# env is populated before translation_service reads DEEPL_API_KEY below --
# no separate load_dotenv() call needed here.
from ai_services import select_short_explanation_ai
from translation_service import translate_short_explanation
from db_operations import (
	get_connection,
	reset_and_create_schema,
	concept_exists,
	get_short_explanation,
	upsert_explanation,
	run_smoke_check,
)

logger = logging.getLogger("clearmed.server_init.build_db")

def _load_terms(json_file_path):
	with open(json_file_path, "r", encoding="utf-8") as f:
		data = json.load(f)
	return data["terms"]

def _populate_primary_language(json_file_path):
	# Writes through DAL.insert_concept() rather than raw sqlite3: the
	# interface already declares exactly this write primitive (one concept +
	# its explanations + aliases in one transaction), so there's no reason
	# for this script to hand-roll a second copy of that INSERT logic. One
	# connection is opened for the whole run and passed to every call so the
	# ~1000-term seed is one transaction/commit, not one per concept.
	terms = _load_terms(json_file_path)

	dal = SQLiteDatabase()
	connection = dal._get_connection()
	total = len(terms)
	try:
		with connection:
			for index, item in enumerate(terms, start=1):
				simple_explanation = item.get("simple_explanation")
				# OpenAI hook (English): this is where the English short_explanation
				# is generated today. If you're improving this algorithm, change it
				# here -- select_short_explanation_ai() in ai_services.py.
				short_explanation = select_short_explanation_ai(simple_explanation, term=item.get("term"))
				if index % 50 == 0:
					logger.info("Processed %d/%d terms", index, total)
				term = item.get("term")
				synonyms = item.get("synonyms", [])
				dal.insert_concept(
					concept_id=item.get("source_id"),
					categories=item.get("categories", []),
					explanations=[{
						"language_code": PRIMARY_LANGUAGE_CODE,
						"term_name": term,
						"simple_explanation": simple_explanation,
						"short_explanation": short_explanation,
					}],
					aliases=[
						{"alias_text": term, "language_code": PRIMARY_LANGUAGE_CODE},
						*({"alias_text": synonym, "language_code": PRIMARY_LANGUAGE_CODE} for synonym in synonyms),
					],
					connection=connection,
				)
	finally:
		connection.close()

	print(f"Database created: {DB_FILE}")
	print(f"Inserted concepts: {len(terms)}")
	run_smoke_check(terms[0])

def _populate_secondary_language(language_code, json_file_path):
	"""Handles every non-primary language configured in SUPPORTED_LANGUAGES.
	Assumes the language's JSON is a translation-of-primary-language corpus
	matched to existing primary-language concept_ids (concept_id/target_names/
	english_names/simple_explanation, per clearmed_terms_hebrew.json's shape) --
	a language sourced independently of the primary language would need a
	different population function, not just a new SUPPORTED_LANGUAGES entry."""
	connection = get_connection()

	terms = _load_terms(json_file_path)
	source_lang = get_deepl_target_lang(PRIMARY_LANGUAGE_CODE)
	deepl_target_lang = get_deepl_target_lang(language_code)

	inserted = skipped = translation_failures = 0
	for term in terms:
		concept_id = term["concept_id"]
		if not concept_exists(connection, concept_id, PRIMARY_LANGUAGE_CODE):
			logger.warning(
				"Skipping %s term for concept_id=%r: no matching %s concept in the current DB "
				"(the %s source JSON may have changed since this %s JSON was captured)",
				language_code, concept_id, PRIMARY_LANGUAGE_CODE, PRIMARY_LANGUAGE_CODE, language_code,
			)
			skipped += 1
			continue

		# Translate the primary language's current short_explanation as just
		# written to the DB (by _populate_primary_language, in this same
		# build), not the target-language JSON's own short_explanation field
		# -- that field is only a scrape-time snapshot and can drift from
		# whatever select_short_explanation_ai() picks today.
		short_explanation_source = get_short_explanation(connection, concept_id, PRIMARY_LANGUAGE_CODE)
		translated_short_explanation = translate_short_explanation(
			short_explanation_source, source_lang=source_lang, target_lang=deepl_target_lang,
		)
		if translated_short_explanation is None and short_explanation_source:
			# Only a real translation failure when there was source text to
			# translate in the first place; write NULL and continue rather
			# than skipping the whole row (term_name/simple_explanation/aliases
			# are still valid and get written).
			logger.warning(
				"Translation failed for concept_id=%r (language_code=%r); writing short_explanation=NULL",
				concept_id, language_code,
			)
			translation_failures += 1

		target_names = term["target_names"]
		english_names = term["english_names"]
		aliases = (
			[(name, language_code) for name in target_names]
			+ [(name, PRIMARY_LANGUAGE_CODE) for name in english_names]
		)
		upsert_explanation(
			connection, concept_id, language_code,
			term_name=target_names[0],
			simple_explanation=term["simple_explanation"],
			short_explanation=translated_short_explanation,
			aliases=aliases,
		)
		inserted += 1

	connection.close()
	print(f"{language_code} terms read from {json_file_path}: {len(terms)}")
	print(f"Inserted: {inserted}")
	print(f"Skipped (no matching {PRIMARY_LANGUAGE_CODE} concept in current DB): {skipped}")
	print(f"Translation failures (short_explanation written as NULL): {translation_failures}")

def populate_terms(language_code, json_file_path):
	if language_code == PRIMARY_LANGUAGE_CODE:
		return _populate_primary_language(json_file_path)
	return _populate_secondary_language(language_code, json_file_path)

def build_database():
	"""Builds the full database in one straight line: reset the schema, seed
	the primary language, then seed+translate every other configured language.
	The single definition of this sequence -- bootstrap.py and this module's
	own __main__ both call it instead of each writing the steps out separately."""
	if not os.environ.get("DEEPL_API_KEY"):
		raise SystemExit(
			"DEEPL_API_KEY is not set in the environment. Stopping before the "
			"English seed so a bootstrap run is never left with untranslated "
			"terms in other languages."
		)

	reset_and_create_schema()

	# The primary language is always populated first, explicitly (not by
	# relying on dict order) -- every other language matches its rows against
	# already-existing primary-language concept_ids.
	populate_terms(PRIMARY_LANGUAGE_CODE, SUPPORTED_LANGUAGES[PRIMARY_LANGUAGE_CODE])

	for language_code, json_file_path in SUPPORTED_LANGUAGES.items():
		if language_code == PRIMARY_LANGUAGE_CODE:
			continue
		populate_terms(language_code, json_file_path)
