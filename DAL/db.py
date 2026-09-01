import os
import sqlite3
import json
import logging
from typing import Optional

from config import DB_FILE
from DAL.interface import DatabaseInterface

logger = logging.getLogger("clearmed.dal.db")


class SQLiteDatabase(DatabaseInterface):
	def _get_connection(self):
		if not os.path.exists(DB_FILE):
			logger.error(f"{DB_FILE} not found")
			raise FileNotFoundError(
				f"{DB_FILE} not found. Run 'python server_init/bootstrap.py' "
				f"from the repo root to build it."
			)
		try:
			connection = sqlite3.connect(DB_FILE)
			logger.debug(f"Opened connection to {DB_FILE}")
			return connection
		except sqlite3.Error:
			logger.exception(f"Failed to open connection to {DB_FILE}")
			raise

	def _row_to_dict(self, row):
		return {
			"term": row[0],
			"short_explanation": row[1],
			"simple_explanation": row[2],
			"synonyms": json.loads(row[3]) if row[3] is not None else [],
			"categories": json.loads(row[4]) if row[4] is not None else [],
		}

	def get_term_by_name(self, term: str) -> Optional[dict]:
		connection = self._get_connection()
		try:
			cursor = connection.cursor()
			cursor.execute("""
				SELECT term, short_explanation, simple_explanation, synonyms, categories
				FROM medical_terms
				WHERE LOWER(term) = LOWER(?)
			""", (term,))
			row = cursor.fetchone()
		finally:
			connection.close()
		if row is None:
			logger.debug(f"No DB entry found for term '{term}'")
			return None
		return self._row_to_dict(row)

	def get_all_terms(self) -> list[dict]:
		connection = self._get_connection()
		try:
			cursor = connection.cursor()
			cursor.execute("""
				SELECT term, synonyms
				FROM medical_terms
			""")
			rows = cursor.fetchall()
		finally:
			connection.close()
		return [
			{
				"term": row[0],
				"short_explanation": None,
				"simple_explanation": None,
				"synonyms": json.loads(row[1]) if row[1] is not None else [],
				"categories": [],
			}
			for row in rows
		]
