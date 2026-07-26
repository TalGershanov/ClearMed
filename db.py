import sqlite3
import logging

logger = logging.getLogger("clearmed.db")
DB_FILE = "clearmed.db"

def get_connection():
	try:
		connection = sqlite3.connect(DB_FILE)
		logger.debug(f"Opened connection to {DB_FILE}")
		return connection
	except sqlite3.Error:
		logger.exception(f"Failed to open connection to {DB_FILE}")
		raise
