import logging
import sqlite3

from config import DB_FILE
from DAL.db import SQLiteDatabase

logger = logging.getLogger("clearmed.server_init.db_operations")

def get_connection():
	return SQLiteDatabase()._get_connection()

def create_concept_tables(cursor):
	cursor.execute("""
		CREATE TABLE IF NOT EXISTS concepts (
			concept_id TEXT PRIMARY KEY,
			categories TEXT
		)
	""")
	cursor.execute("""
		CREATE TABLE IF NOT EXISTS explanations (
			explanation_id INTEGER PRIMARY KEY AUTOINCREMENT,
			concept_id TEXT NOT NULL REFERENCES concepts (concept_id),
			language_code TEXT NOT NULL,
			term_name TEXT NOT NULL,
			simple_explanation TEXT,
			short_explanation TEXT,
			UNIQUE (concept_id, language_code)
		)
	""")
	cursor.execute("""
		CREATE TABLE IF NOT EXISTS term_aliases (
			alias_text TEXT PRIMARY KEY,
			concept_id TEXT NOT NULL REFERENCES concepts (concept_id),
			language_code TEXT
		)
	""")
	cursor.execute("""
		CREATE INDEX IF NOT EXISTS idx_term_aliases_concept_id
		ON term_aliases (concept_id)
	""")

def reset_and_create_schema():
	connection = sqlite3.connect(DB_FILE)
	cursor = connection.cursor()
	# Retire the old flat schema and (re)build the normalized one -- a fresh
	# rebuild lands directly in the current concepts/explanations/term_aliases
	# shape, so no separate migration step is ever needed after this runs.
	cursor.execute("DROP TABLE IF EXISTS medical_terms")
	cursor.execute("DROP TABLE IF EXISTS term_aliases")
	cursor.execute("DROP TABLE IF EXISTS explanations")
	cursor.execute("DROP TABLE IF EXISTS concepts")
	create_concept_tables(cursor)
	connection.commit()
	connection.close()

def concept_exists(connection, concept_id, language_code):
	exists = connection.execute(
		"SELECT 1 FROM explanations WHERE concept_id = ? AND language_code = ?",
		(concept_id, language_code),
	).fetchone()
	return exists is not None

def get_short_explanation(connection, concept_id, language_code):
	row = connection.execute(
		"SELECT short_explanation FROM explanations WHERE concept_id = ? AND language_code = ?",
		(concept_id, language_code),
	).fetchone()
	return row[0] if row is not None else None

def upsert_explanation(connection, concept_id, language_code, term_name, simple_explanation, short_explanation, aliases):
	"""Generic version of the former _upsert_hebrew_explanation. `aliases` is a
	list of (alias_text, alias_language_code) tuples."""
	with connection:
		connection.execute(
			"""
			INSERT INTO explanations (concept_id, language_code, term_name, simple_explanation, short_explanation)
			VALUES (?, ?, ?, ?, ?)
			ON CONFLICT(concept_id, language_code) DO UPDATE SET
				term_name = excluded.term_name,
				simple_explanation = excluded.simple_explanation,
				short_explanation = COALESCE(excluded.short_explanation, explanations.short_explanation)
			""",
			(
				concept_id,
				language_code,
				term_name,
				simple_explanation,
				short_explanation,
			),
		)
		# One row at a time (not executemany) so a dropped INSERT OR IGNORE
		# -- alias_text is a table-wide primary key, so this happens whenever
		# two different concepts share an alias string -- gets logged instead
		# of silently vanishing.
		for alias_text, alias_language_code in aliases:
			cursor = connection.execute(
				"INSERT OR IGNORE INTO term_aliases (alias_text, concept_id, language_code) VALUES (?, ?, ?)",
				(alias_text, concept_id, alias_language_code),
			)
			if cursor.rowcount == 0:
				logger.warning(
					"Alias %r not inserted for concept_id=%r (language_code=%r) -- "
					"alias_text already claimed by a different concept",
					alias_text, concept_id, alias_language_code,
				)

def run_smoke_check(first_term):
	# Smoke check: verify the DAL read path agrees with what this script just
	# wrote. Catches write/read schema drift (e.g. a reordered SELECT or
	# CREATE TABLE) immediately at seed time instead of silently corrupting
	# data in production.
	dal = SQLiteDatabase()
	fetched = dal.get_term_details(first_term["source_id"], "en")
	if fetched is None:
		raise AssertionError(
			f"Smoke check failed: DAL could not find seeded concept {first_term['source_id']!r}"
		)
	if fetched["short_explanation"] is not None and not isinstance(fetched["short_explanation"], str):
		raise AssertionError(
			"Smoke check failed: short_explanation has unexpected type -- check DAL/db.py column mapping"
		)
	for field, expected in (
		("term_name", first_term["term"]),
		("simple_explanation", first_term.get("simple_explanation")),
		("categories", first_term.get("categories", [])),
	):
		if fetched[field] != expected:
			raise AssertionError(
				f"Smoke check failed: {field} mismatch ({fetched[field]!r} != {expected!r})"
			)
	print(f"Smoke check passed: DAL read back concept {first_term['source_id']!r} correctly")
