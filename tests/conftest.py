import os
import tempfile

# webapp.core.config raises at import time if JWT_SECRET_KEY is unset, so
# this must happen before anything imports webapp/server. Using a fixed
# test-only secret keeps these tests independent of the developer's real .env.
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-pytest-only-do-not-use-in-prod")
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
# Force (not setdefault) -- uploaded test files must never land in the real
# LOCAL_STORAGE_DIR a developer's .env might point at.
os.environ["LOCAL_STORAGE_DIR"] = tempfile.mkdtemp(prefix="clearmed_test_uploads_")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from server.api import app
from webapp.core.database import Base, get_db

# Auth tests run against an isolated in-memory SQLite DB via dependency
# override -- they never touch the real Postgres application DB, and they
# never touch clearmed.db / the medical-terms DAL either.
_engine = create_engine(
	"sqlite:///:memory:",
	connect_args={"check_same_thread": False},
	poolclass=StaticPool,
)
_TestingSessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False)


def _override_get_db():
	db = _TestingSessionLocal()
	try:
		yield db
	finally:
		db.close()


app.dependency_overrides[get_db] = _override_get_db


@pytest.fixture(autouse=True)
def _reset_db():
	Base.metadata.create_all(bind=_engine)
	yield
	Base.metadata.drop_all(bind=_engine)


@pytest.fixture
def client():
	# No `with` block: the lifespan (medical-term trie build) is irrelevant
	# to auth and is intentionally not exercised here.
	return TestClient(app)


@pytest.fixture
def second_client():
	# A second, independent TestClient (own cookie jar) sharing the same app
	# and the same overridden in-memory DB -- used for cross-user isolation
	# tests, so two "logged in" identities can exist side by side.
	return TestClient(app)


def register_and_login(client: TestClient, email: str, password: str = "supersecret123") -> dict:
	register_resp = client.post("/auth/register", json={"email": email, "password": password})
	assert register_resp.status_code == 201, register_resp.text
	login_resp = client.post("/auth/login", json={"email": email, "password": password})
	assert login_resp.status_code == 200, login_resp.text
	return login_resp.json()
