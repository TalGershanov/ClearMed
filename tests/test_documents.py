import os
from unittest.mock import patch

from tests.conftest import register_and_login

PDF_BYTES = b"%PDF-1.4\n%mock pdf content for testing purposes only\n%%EOF"
JPEG_BYTES = bytes([0xFF, 0xD8, 0xFF, 0xE0]) + b"mock jpeg content for testing"
PNG_BYTES = bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A]) + b"mock png content for testing"
UNSUPPORTED_BYTES = b"just some plain text, not a real document"


def _first_root_folder_id(client) -> int:
	resp = client.get("/folders")
	assert resp.status_code == 200, resp.text
	return resp.json()[0]["id"]


def _upload(client, folder_id, content, filename, content_type, name=None):
	data = {"folder_id": str(folder_id)}
	if name is not None:
		data["name"] = name
	return client.post("/documents", data=data, files={"file": (filename, content, content_type)})


def _document_row(document_id: int):
	"""Reaches into the overridden test DB session directly -- same pattern as
	tests/test_auth.py::test_password_is_never_stored_in_plaintext -- to
	inspect fields (like storage_key) that the API response deliberately
	never exposes."""
	from server.api import app
	from webapp.core.database import get_db
	from webapp.documents.models import Document

	db_gen = app.dependency_overrides[get_db]()
	db = next(db_gen)
	try:
		return db.get(Document, document_id)
	finally:
		db_gen.close()


# --- Upload validation -------------------------------------------------------

def test_upload_valid_pdf(client):
	register_and_login(client, "docs_pdf@example.com")
	folder_id = _first_root_folder_id(client)
	resp = _upload(client, folder_id, PDF_BYTES, "report.pdf", "application/pdf", name="My PDF")
	assert resp.status_code == 201, resp.text
	body = resp.json()
	assert body["name"] == "My PDF"
	assert body["mime_type"] == "application/pdf"
	assert body["original_filename"] == "report.pdf"
	assert body["folder_id"] == folder_id
	assert body["file_size"] == len(PDF_BYTES)
	assert "storage_key" not in body
	assert "user_id" not in body


def test_upload_valid_jpeg(client):
	register_and_login(client, "docs_jpeg@example.com")
	folder_id = _first_root_folder_id(client)
	# Upload now runs OCR synchronously on any image (see webapp/extraction/) --
	# mocked here since this test only cares about the upload itself, not
	# extraction, and must never depend on GEMINI_API_KEY being configured.
	with patch("webapp.extraction.ocr.extract_text_from_image", side_effect=ValueError("no text")):
		resp = _upload(client, folder_id, JPEG_BYTES, "photo.jpg", "image/jpeg")
	assert resp.status_code == 201, resp.text
	assert resp.json()["mime_type"] == "image/jpeg"


def test_upload_valid_png(client):
	register_and_login(client, "docs_png@example.com")
	folder_id = _first_root_folder_id(client)
	with patch("webapp.extraction.ocr.extract_text_from_image", side_effect=ValueError("no text")):
		resp = _upload(client, folder_id, PNG_BYTES, "scan.png", "image/png")
	assert resp.status_code == 201, resp.text
	assert resp.json()["mime_type"] == "image/png"


def test_upload_defaults_name_to_filename_when_omitted(client):
	register_and_login(client, "docs_defaultname@example.com")
	folder_id = _first_root_folder_id(client)
	resp = _upload(client, folder_id, PDF_BYTES, "unnamed.pdf", "application/pdf")
	assert resp.status_code == 201, resp.text
	assert resp.json()["name"] == "unnamed.pdf"


def test_upload_rejects_unsupported_file_type(client):
	register_and_login(client, "docs_unsupported@example.com")
	folder_id = _first_root_folder_id(client)
	# Declares an image Content-Type but the bytes don't match any known
	# magic header -- proves the server sniffs content, not the client's claim.
	resp = _upload(client, folder_id, UNSUPPORTED_BYTES, "notes.txt", "image/png")
	assert resp.status_code == 415


def test_upload_rejects_oversized_file(client):
	register_and_login(client, "docs_oversized@example.com")
	folder_id = _first_root_folder_id(client)
	oversized = b"%PDF-1.4\n" + b"0" * (21 * 1024 * 1024)
	resp = _upload(client, folder_id, oversized, "big.pdf", "application/pdf")
	assert resp.status_code == 413


def test_upload_rejects_empty_file(client):
	register_and_login(client, "docs_empty@example.com")
	folder_id = _first_root_folder_id(client)
	resp = _upload(client, folder_id, b"", "empty.pdf", "application/pdf")
	assert resp.status_code == 400


def test_upload_into_nonexistent_folder_rejected(client):
	register_and_login(client, "docs_badfolder@example.com")
	resp = _upload(client, 999999, PDF_BYTES, "x.pdf", "application/pdf")
	assert resp.status_code == 404


def test_upload_requires_authentication(client):
	resp = _upload(client, 1, PDF_BYTES, "x.pdf", "application/pdf")
	assert resp.status_code == 401


# --- Ownership ----------------------------------------------------------------

def test_cannot_upload_into_another_users_folder(client, second_client):
	register_and_login(client, "docs_usera@example.com")
	register_and_login(second_client, "docs_userb@example.com")
	b_folder_id = _first_root_folder_id(second_client)
	resp = _upload(client, b_folder_id, PDF_BYTES, "x.pdf", "application/pdf")
	assert resp.status_code == 404


def test_document_belongs_to_authenticated_user(client):
	register_and_login(client, "docs_owner@example.com")
	folder_id = _first_root_folder_id(client)
	doc = _upload(client, folder_id, PDF_BYTES, "x.pdf", "application/pdf").json()
	row = _document_row(doc["id"])
	me = client.get("/auth/me").json()
	assert row.user_id == me["id"]


def test_get_own_document(client):
	register_and_login(client, "docs_get@example.com")
	folder_id = _first_root_folder_id(client)
	doc_id = _upload(client, folder_id, PDF_BYTES, "x.pdf", "application/pdf").json()["id"]
	resp = client.get(f"/documents/{doc_id}")
	assert resp.status_code == 200
	assert resp.json()["id"] == doc_id


def test_cannot_get_another_users_document(client, second_client):
	register_and_login(client, "docs_a2@example.com")
	register_and_login(second_client, "docs_b2@example.com")
	folder_id = _first_root_folder_id(client)
	doc_id = _upload(client, folder_id, PDF_BYTES, "x.pdf", "application/pdf").json()["id"]
	resp = second_client.get(f"/documents/{doc_id}")
	assert resp.status_code == 404


def test_delete_own_document(client):
	register_and_login(client, "docs_del@example.com")
	folder_id = _first_root_folder_id(client)
	doc_id = _upload(client, folder_id, PDF_BYTES, "x.pdf", "application/pdf").json()["id"]
	resp = client.delete(f"/documents/{doc_id}")
	assert resp.status_code == 204
	assert client.get(f"/documents/{doc_id}").status_code == 404


def test_cannot_delete_another_users_document(client, second_client):
	register_and_login(client, "docs_a3@example.com")
	register_and_login(second_client, "docs_b3@example.com")
	folder_id = _first_root_folder_id(client)
	doc_id = _upload(client, folder_id, PDF_BYTES, "x.pdf", "application/pdf").json()["id"]
	resp = second_client.delete(f"/documents/{doc_id}")
	assert resp.status_code == 404
	assert client.get(f"/documents/{doc_id}").status_code == 200


def test_another_users_documents_do_not_leak_through_folder_response(client, second_client):
	register_and_login(client, "docs_a4@example.com")
	register_and_login(second_client, "docs_b4@example.com")
	a_folder_id = _first_root_folder_id(client)
	_upload(client, a_folder_id, PDF_BYTES, "a-secret.pdf", "application/pdf")

	b_folder_id = _first_root_folder_id(second_client)
	b_view = second_client.get(f"/folders/{b_folder_id}").json()
	assert b_view["documents"] == []
	# and B can't even read A's folder to see its documents
	assert second_client.get(f"/folders/{a_folder_id}").status_code == 404


# --- File lifecycle -------------------------------------------------------

def test_deleting_document_removes_stored_file(client):
	from webapp.core import config

	register_and_login(client, "docs_file@example.com")
	folder_id = _first_root_folder_id(client)
	doc_id = _upload(client, folder_id, PDF_BYTES, "x.pdf", "application/pdf").json()["id"]

	storage_key = _document_row(doc_id).storage_key
	file_path = os.path.join(config.LOCAL_STORAGE_DIR, storage_key)
	assert os.path.exists(file_path)

	client.delete(f"/documents/{doc_id}")
	assert not os.path.exists(file_path)


def test_filename_cannot_control_storage_path(client):
	from webapp.core import config

	register_and_login(client, "docs_traversal@example.com")
	folder_id = _first_root_folder_id(client)
	malicious_name = "../../../../etc/passwd"
	resp = _upload(client, folder_id, PDF_BYTES, malicious_name, "application/pdf")
	assert resp.status_code == 201, resp.text
	body = resp.json()
	# the raw attacker-controlled filename is preserved only as harmless metadata
	assert body["original_filename"] == malicious_name

	storage_key = _document_row(body["id"]).storage_key
	# the actual on-disk key is a server-generated UUID -- no traversal sequences
	assert "/" not in storage_key
	assert "\\" not in storage_key
	assert ".." not in storage_key
	# and the file lives exactly inside the configured storage directory
	resolved = os.path.realpath(os.path.join(config.LOCAL_STORAGE_DIR, storage_key))
	assert resolved.startswith(os.path.realpath(config.LOCAL_STORAGE_DIR) + os.sep)


# --- Folder integration ---------------------------------------------------

def test_folder_response_includes_its_documents(client):
	register_and_login(client, "docs_folderview@example.com")
	folder_id = _first_root_folder_id(client)
	doc_id = _upload(client, folder_id, PDF_BYTES, "x.pdf", "application/pdf", name="Visible Doc").json()["id"]

	resp = client.get(f"/folders/{folder_id}")
	assert resp.status_code == 200
	doc_ids = [d["id"] for d in resp.json()["documents"]]
	assert doc_id in doc_ids


def test_nested_folder_documents_do_not_leak_into_parent(client):
	register_and_login(client, "docs_nested@example.com")
	parent_id = _first_root_folder_id(client)
	child_id = client.post("/folders", json={"name": "Child", "parent_folder_id": parent_id}).json()["id"]
	doc_id = _upload(client, child_id, PDF_BYTES, "nested.pdf", "application/pdf").json()["id"]

	parent_view = client.get(f"/folders/{parent_id}").json()
	assert doc_id not in [d["id"] for d in parent_view["documents"]]

	child_view = client.get(f"/folders/{child_id}").json()
	assert doc_id in [d["id"] for d in child_view["documents"]]


def test_folder_containing_a_document_cannot_be_deleted(client):
	register_and_login(client, "docs_blockdelete@example.com")
	folder_id = _first_root_folder_id(client)
	_upload(client, folder_id, PDF_BYTES, "x.pdf", "application/pdf")

	resp = client.delete(f"/folders/{folder_id}")
	assert resp.status_code == 409
	assert client.get(f"/folders/{folder_id}").status_code == 200
