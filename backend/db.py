import sqlite3

DB_FILE = "clearmed.db"

def get_connection():
    connection = sqlite3.connect(DB_FILE)
    connection.row_factory = sqlite3.Row
    return connection

def close_connection(cursor, connection):
    cursor.close()
    connection.close()

    