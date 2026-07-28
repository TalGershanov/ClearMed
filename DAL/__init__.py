from DAL.interface import DatabaseInterface
from DAL.db import SQLiteDatabase


def get_dal() -> DatabaseInterface:
	return SQLiteDatabase()
