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
				"from the repo root to build it."
			)
		try:
			connection = sqlite3.connect(DB_FILE)
			connection.row_factory = sqlite3.Row
			connection.execute("PRAGMA foreign_keys = ON")
			logger.debug(f"Opened connection to {DB_FILE}")
			return connection
		except sqlite3.Error:
			logger.exception(f"Failed to open connection to {DB_FILE}")
			raise

	def get_all_aliases(self) -> list[dict]:
		connection = self._get_connection()
		try:
			cursor = connection.cursor()
			cursor.execute("""
				SELECT alias_text, concept_id, language_code
				FROM term_aliases
			""")
			rows = cursor.fetchall()
			results = [dict(row) for row in rows]
		finally:
			connection.close()
		return results

	def insert_concept(
		self,
		concept_id: str,
		categories: list[str],
		explanations: list[dict],
		aliases: list[dict],
		connection=None,
	) -> None:
		# `connection`: pass an already-open connection to fold this insert
		# into a caller-managed transaction (e.g. a bulk seed loop that wants
		# one commit for many concepts instead of one per call); when omitted,
		# this method opens and commits/closes its own connection as before.
		owns_connection = connection is None
		if owns_connection:
			connection = self._get_connection()
		try:
			connection.execute(
				"INSERT INTO concepts (concept_id, categories) VALUES (?, ?)",
				(concept_id, json.dumps(categories, ensure_ascii=False)),
			)
			connection.executemany(
				"""
				INSERT INTO explanations (
					concept_id, language_code, term_name,
					simple_explanation, short_explanation
				) VALUES (
					:concept_id, :language_code, :term_name,
					:simple_explanation, :short_explanation
				)
				""",
				[{**e, "concept_id": concept_id} for e in explanations],
			)
			connection.executemany(
				"""
				INSERT OR IGNORE INTO term_aliases (alias_text, concept_id, language_code)
				VALUES (:alias_text, :concept_id, :language_code)
				""",
				[{**a, "concept_id": concept_id} for a in aliases],
			)
			if owns_connection:
				connection.commit()
		finally:
			if owns_connection:
				connection.close()
		logger.debug(
			f"Inserted concept {concept_id!r} with {len(explanations)} explanation(s) "
			f"and {len(aliases)} alias(es)"
		)

	def get_term_details(self, concept_id: str, language_code: str) -> dict | None:
		connection = self._get_connection()
		try:
			cursor = connection.cursor()
			cursor.execute("""
				SELECT
					c.concept_id,
					c.categories,
					e.language_code,
					e.term_name,
					e.simple_explanation,
					e.short_explanation
				FROM concepts AS c
				JOIN explanations AS e ON e.concept_id = c.concept_id
				WHERE c.concept_id = ? AND e.language_code = ?
			""", (concept_id, language_code))
			row = cursor.fetchone()
		finally:
			connection.close()
		if row is None:
			logger.debug(
				f"No explanation for concept_id={concept_id!r} language={language_code!r}"
			)
			return None
		result = dict(row)
		result["categories"] = json.loads(result["categories"]) if result["categories"] else []
		return result
