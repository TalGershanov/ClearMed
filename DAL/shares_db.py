import json
import logging
import sqlite3
from datetime import datetime, timezone

from config import SHARES_DB_FILE

logger = logging.getLogger("clearmed.dal.shares_db")


def _get_connection() -> sqlite3.Connection:
	connection = sqlite3.connect(SHARES_DB_FILE)
	connection.row_factory = sqlite3.Row
	logger.debug(f"Opened connection to {SHARES_DB_FILE}")
	return connection


def init_schema() -> None:
	connection = _get_connection()
	try:
		connection.execute("""
			CREATE TABLE IF NOT EXISTS shared_documents (
				id TEXT PRIMARY KEY,
				explanation_text TEXT NOT NULL,
				explained_terms_json TEXT NOT NULL,
				created_at TEXT NOT NULL,
				expires_at TEXT NOT NULL
			)
		""")
		connection.commit()
	finally:
		connection.close()


def _delete_expired(connection: sqlite3.Connection) -> None:
	# Shared documents carry sensitive medical context -- physically delete
	# expired rows rather than just filtering them out at read time, so
	# nothing lingers in shares.db past its 5-minute window.
	now = datetime.now(timezone.utc).isoformat()
	cursor = connection.execute("DELETE FROM shared_documents WHERE expires_at < ?", (now,))
	if cursor.rowcount:
		logger.debug(f"Swept {cursor.rowcount} expired share(s)")


def insert_share(share_id: str, explanation_text: str, explained_terms_list: list[str], created_at: str, expires_at: str) -> None:
	connection = _get_connection()
	try:
		_delete_expired(connection)
		connection.execute(
			"""
			INSERT INTO shared_documents (id, explanation_text, explained_terms_json, created_at, expires_at)
			VALUES (?, ?, ?, ?, ?)
			""",
			(share_id, explanation_text, json.dumps(explained_terms_list, ensure_ascii=False), created_at, expires_at),
		)
		connection.commit()
	finally:
		connection.close()


def get_share(share_id: str) -> dict | None:
	connection = _get_connection()
	try:
		# Sweeping here too means a read of an id past its expiry correctly
		# returns None (the row is gone) rather than stale content -- there's
		# no separate expires_at comparison the caller needs to make.
		_delete_expired(connection)
		connection.commit()
		cursor = connection.execute(
			"SELECT id, explanation_text, explained_terms_json, created_at, expires_at FROM shared_documents WHERE id = ?",
			(share_id,),
		)
		row = cursor.fetchone()
	finally:
		connection.close()
	if row is None:
		return None
	result = dict(row)
	result["explained_terms_list"] = json.loads(result.pop("explained_terms_json"))
	return result
