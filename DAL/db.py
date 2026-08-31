import os
import sqlite3
import json
import logging

from config import DB_FILE
from DAL.interface import DatabaseInterface

logger = logging.getLogger("clearmed.dal.db")


class SQLiteDatabase(DatabaseInterface):
	# Single source of truth for the dict shape DatabaseInterface guarantees.
	# Adding a column (e.g. a future `lang` field) is a one-line change here.
	_TERM_FIELDS = ("term", "short_explanation", "simple_explanation", "synonyms", "categories")
	_JSON_FIELDS = {"synonyms", "categories"}

	def _get_connection(self):
		if not os.path.exists(DB_FILE):
			logger.error(f"{DB_FILE} not found")
			raise FileNotFoundError(
				f"{DB_FILE} not found. Run 'python server_init/bootstrap.py' "
				f"from the repo root to build it."
			)
		try:
			connection = sqlite3.connect(DB_FILE)
			connection.row_factory = sqlite3.Row
			logger.debug(f"Opened connection to {DB_FILE}")
			return connection
		except sqlite3.Error:
			logger.exception(f"Failed to open connection to {DB_FILE}")
			raise

	def _row_to_dict(self, row):
		"""Map a fetched row to a dict by column name (via sqlite3.Row),
		not position, so a reordered SELECT or CREATE TABLE can't silently
		swap field values."""
		raw = dict(row)
		result = {}
		for field in self._TERM_FIELDS:
			if field not in raw:
				result[field] = [] if field in self._JSON_FIELDS else None
				continue
			value = raw[field]
			if field in self._JSON_FIELDS:
				result[field] = json.loads(value) if value is not None else []
			else:
				result[field] = value
		return result

	def get_term_by_name(self, term: str) -> dict | None:
		connection = self._get_connection()
		try:
			cursor = connection.cursor()
			cursor.execute("""
				SELECT term, short_explanation, simple_explanation, synonyms, categories
				FROM medical_terms
				WHERE LOWER(term) = LOWER(?)
			""", (term,))
			row = cursor.fetchone()
			result = self._row_to_dict(row) if row is not None else None
		finally:
			connection.close()
		if result is None:
			logger.debug(f"No DB entry found for term '{term}'")
		return result

	def get_all_terms(self) -> list[dict]:
		connection = self._get_connection()
		try:
			cursor = connection.cursor()
			cursor.execute("""
				SELECT term, synonyms
				FROM medical_terms
			""")
			rows = cursor.fetchall()
			results = [self._row_to_dict(row) for row in rows]
		finally:
			connection.close()
		return results
