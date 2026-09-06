from webapp.core import config


def _register(client, email="patient@example.com", password="supersecret123"):
	return client.post("/auth/register", json={"email": email, "password": password})


def test_register_creates_user_with_normalized_email(client):
	resp = _register(client, email="Patient@Example.com")
	assert resp.status_code == 201
	body = resp.json()
	assert body["email"] == "patient@example.com"
	assert "id" in body
	assert "created_at" in body
	assert "password" not in body
	assert "password_hash" not in body


def test_register_rejects_duplicate_email_case_insensitive(client):
	assert _register(client, email="dup@example.com").status_code == 201
	resp = _register(client, email="DUP@example.com")
	assert resp.status_code == 409


def test_register_rejects_short_password(client):
	resp = client.post("/auth/register", json={"email": "short@example.com", "password": "abc123"})
	assert resp.status_code == 422


def test_register_rejects_invalid_email(client):
	resp = client.post("/auth/register", json={"email": "not-an-email", "password": "supersecret123"})
	assert resp.status_code == 422


def test_login_fails_with_wrong_password(client):
	_register(client, email="user@example.com", password="correcthorse123")
	resp = client.post("/auth/login", json={"email": "user@example.com", "password": "wrongpassword"})
	assert resp.status_code == 401
	assert config.COOKIE_NAME not in resp.cookies


def test_login_fails_for_unknown_user(client):
	resp = client.post("/auth/login", json={"email": "ghost@example.com", "password": "whatever123"})
	assert resp.status_code == 401


def test_login_sets_httponly_cookie_and_me_reflects_identity(client):
	_register(client, email="user@example.com", password="correcthorse123")

	login_resp = client.post("/auth/login", json={"email": "User@Example.com", "password": "correcthorse123"})
	assert login_resp.status_code == 200
	assert config.COOKIE_NAME in login_resp.cookies

	set_cookie_header = login_resp.headers.get("set-cookie", "")
	assert "HttpOnly" in set_cookie_header
	assert "Secure" not in set_cookie_header  # dev config: COOKIE_SECURE=False

	me_resp = client.get("/auth/me")
	assert me_resp.status_code == 200
	assert me_resp.json()["email"] == "user@example.com"


def test_me_requires_authentication(client):
	resp = client.get("/auth/me")
	assert resp.status_code == 401


def test_me_rejects_tampered_cookie(client):
	client.cookies.set(config.COOKIE_NAME, "not-a-real-jwt")
	resp = client.get("/auth/me")
	assert resp.status_code == 401


def test_logout_clears_cookie_and_revokes_session(client):
	_register(client, email="user@example.com", password="correcthorse123")
	client.post("/auth/login", json={"email": "user@example.com", "password": "correcthorse123"})
	assert client.get("/auth/me").status_code == 200

	logout_resp = client.post("/auth/logout")
	assert logout_resp.status_code == 200

	assert client.get("/auth/me").status_code == 401


def test_password_is_never_stored_in_plaintext(client):
	from server.api import app
	from webapp.core.database import get_db
	from webapp.users.models import User

	_register(client, email="user@example.com", password="correcthorse123")

	db_gen = app.dependency_overrides[get_db]()
	db = next(db_gen)
	try:
		user = db.query(User).filter(User.email == "user@example.com").first()
		assert user is not None
		assert user.password_hash != "correcthorse123"
		assert user.password_hash.startswith("$argon2id$")
	finally:
		db_gen.close()
