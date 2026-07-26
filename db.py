import os
import sqlite3
import logging

logger = logging.getLogger("clearmed.db")
DB_FILE = "clearmed.db"

def get_connection():
	if not os.path.exists(DB_FILE):
		logger.error(f"{DB_FILE} not found")
		raise FileNotFoundError(
			f"{DB_FILE} not found. Run 'python pipeline/build_all.py' from the repo root to build it."
		)
	try:
		connection = sqlite3.connect(DB_FILE)
		logger.debug(f"Opened connection to {DB_FILE}")
		return connection
	except sqlite3.Error:
		logger.exception(f"Failed to open connection to {DB_FILE}")
		raise
