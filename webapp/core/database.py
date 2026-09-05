from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from webapp.core import config

# Independent engine/session/Base for the application database. This must
# never be shared with DAL/db.py, which talks to the read-only clearmed.db
# medical-terms SQLite database via its own sqlite3 connections.
engine = create_engine(config.DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
	pass


def get_db():
	db = SessionLocal()
	try:
		yield db
	finally:
		db.close()
