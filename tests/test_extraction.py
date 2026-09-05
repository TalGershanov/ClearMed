import io

from tests.conftest import register_and_login
from tests.test_documents import JPEG_BYTES, PNG_BYTES, _first_root_folder_id, _upload

# --- Minimal hand-built PDFs for testing ------------------------------------
# No PDF-writing library is installed (pypdf only reads), so these are built
# directly from raw PDF syntax: a Catalog/Pages/Page/Contents object graph
# with a real BT...Tj...ET text-showing operator against the standard
# (non-embedded) Helvetica font. This round-trips through pypdf exactly like
# a real text-based PDF would -- verified interactively before writing these
# tests. The xref table is present but not byte-exact; pypdf tolerates that
# via its recovery path, same as real-world PDFs with minor xref drift.


def _build_pdf(page_texts: list) -> bytes:
	n_pages = len(page_texts)
	font_obj_num = 3 + n_pages * 2

	page_objs = []
	content_objs = []
	for i, text in enumerate(page_texts):
		content_num = 3 + n_pages + i
		page_objs.append(
			f"<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 {font_obj_num} 0 R >> >> "
			f"/MediaBox [0 0 300 300] /Contents {content_num} 0 R >>".encode()
		)
		stream = f"BT /F1 12 Tf 10 200 Td ({text}) Tj ET".encode()
		content_objs.append(b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream")

	kids = " ".join(f"{3 + i} 0 R" for i in range(n_pages))
	catalog = b"<< /Type /Catalog /Pages 2 0 R >>"
	pages = f"<< /Type /Pages /Kids [{kids}] /Count {n_pages} >>".encode()
	font_obj = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"

	all_objs = [catalog, pages] + page_objs + content_objs + [font_obj]

	out = io.BytesIO()
	out.write(b"%PDF-1.4\n")
	offsets = []
	for idx, obj in enumerate(all_objs, start=1):
		offsets.append(out.tell())
		out.write(f"{idx} 0 obj\n".encode())
		out.write(obj)
		out.write(b"\nendobj\n")
	xref_offset = out.tell()
	total = len(all_objs) + 1
	out.write(f"xref\n0 {total}\n".encode())
	out.write(b"0000000000 65535 f \n")
	for off in offsets:
		out.write(f"{off:010d} 00000 n \n".encode())
	out.write(f"trailer\n<< /Size {total} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF".encode())
	return out.getvalue()


def _build_textless_pdf() -> bytes:
	"""A structurally valid single-page PDF whose content stream draws
	nothing -- stands in for a scanned page with no text layer, without
	needing to embed an actual image."""
	catalog = b"<< /Type /Catalog /Pages 2 0 R >>"
	pages = b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>"
	page_obj = b"<< /Type /Page /Parent 2 0 R /Resources << >> /MediaBox [0 0 300 300] /Contents 4 0 R >>"
	content_obj = b"<< /Length 0 >>\nstream\n\nendstream"
	all_objs = [catalog, pages, page_obj, content_obj]

	out = io.BytesIO()
	out.write(b"%PDF-1.4\n")
	offsets = []
	for idx, obj in enumerate(all_objs, start=1):
		offsets.append(out.tell())
		out.write(f"{idx} 0 obj\n".encode())
		out.write(obj)
		out.write(b"\nendobj\n")
	xref_offset = out.tell()
	total = len(all_objs) + 1
	out.write(f"xref\n0 {total}\n".encode())
	out.write(b"0000000000 65535 f \n")
	for off in offsets:
		out.write(f"{off:010d} 00000 n \n".encode())
	out.write(f"trailer\n<< /Size {total} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF".encode())
	return out.getvalue()


MALFORMED_PDF_BYTES = b"%PDF-1.4\nthis is not a real pdf body at all, just garbage bytes\n%%EOF"


# --- Tests -------------------------------------------------------------------

def test_text_based_pdf_extracts_text(client):
	register_and_login(client, "extract_basic@example.com")
	folder_id = _first_root_folder_id(client)
	pdf_bytes = _build_pdf(["Patient blood test results are within normal range."])
	resp = _upload(client, folder_id, pdf_bytes, "report.pdf", "application/pdf")
	assert resp.status_code == 201, resp.text
	doc_id = resp.json()["id"]

	detail = client.get(f"/documents/{doc_id}").json()
	assert detail["extraction_status"] == "extracted"
	assert "Patient blood test results are within normal range." in detail["original_text"]


def test_multi_page_pdf_extracted_in_order(client):
	register_and_login(client, "extract_multipage@example.com")
	folder_id = _first_root_folder_id(client)
	pdf_bytes = _build_pdf(["First page content alpha bravo", "Second page content charlie delta"])
	doc_id = _upload(client, folder_id, pdf_bytes, "multi.pdf", "application/pdf").json()["id"]

	detail = client.get(f"/documents/{doc_id}").json()
	text = detail["original_text"]
	assert text.index("First page content alpha bravo") < text.index("Second page content charlie delta")


def test_extracted_text_is_persisted_in_postgres(client):
	"""Uses the real DB session (SQLite in tests, same ORM path as Postgres)
	to confirm the value actually lands in the row, not just in the response."""
	from server.api import app
	from webapp.core.database import get_db
	from webapp.documents.models import Document

	register_and_login(client, "extract_persist@example.com")
	folder_id = _first_root_folder_id(client)
	pdf_bytes = _build_pdf(["Persisted extraction check content here"])
	doc_id = _upload(client, folder_id, pdf_bytes, "p.pdf", "application/pdf").json()["id"]

	db_gen = app.dependency_overrides[get_db]()
	db = next(db_gen)
	try:
		row = db.get(Document, doc_id)
		assert row.extraction_status == "extracted"
		assert "Persisted extraction check content here" in row.original_text
	finally:
		db_gen.close()


def test_owner_can_get_original_text(client):
	register_and_login(client, "extract_owner@example.com")
	folder_id = _first_root_folder_id(client)
	pdf_bytes = _build_pdf(["Owner-visible extracted text content"])
	doc_id = _upload(client, folder_id, pdf_bytes, "p.pdf", "application/pdf").json()["id"]

	resp = client.get(f"/documents/{doc_id}")
	assert resp.status_code == 200
	assert "Owner-visible extracted text content" in resp.json()["original_text"]


def test_another_user_cannot_get_original_text(client, second_client):
	register_and_login(client, "extract_a@example.com")
	register_and_login(second_client, "extract_b@example.com")
	folder_id = _first_root_folder_id(client)
	pdf_bytes = _build_pdf(["Secret content only A should see"])
	doc_id = _upload(client, folder_id, pdf_bytes, "p.pdf", "application/pdf").json()["id"]

	resp = second_client.get(f"/documents/{doc_id}")
	assert resp.status_code == 404


def test_folder_listing_never_includes_original_text(client):
	register_and_login(client, "extract_folderleak@example.com")
	folder_id = _first_root_folder_id(client)
	pdf_bytes = _build_pdf(["Text that must not appear in the folder listing"])
	_upload(client, folder_id, pdf_bytes, "p.pdf", "application/pdf")

	folder_view = client.get(f"/folders/{folder_id}").json()
	for doc in folder_view["documents"]:
		assert "original_text" not in doc


def test_textless_pdf_marked_no_text_found_without_fabricating_content(client):
	register_and_login(client, "extract_scanned@example.com")
	folder_id = _first_root_folder_id(client)
	pdf_bytes = _build_textless_pdf()
	doc_id = _upload(client, folder_id, pdf_bytes, "scanned.pdf", "application/pdf").json()["id"]

	detail = client.get(f"/documents/{doc_id}").json()
	assert detail["extraction_status"] == "no_text_found"
	assert detail["original_text"] is None


def test_malformed_pdf_extraction_failure_preserves_the_document(client):
	register_and_login(client, "extract_malformed@example.com")
	folder_id = _first_root_folder_id(client)
	resp = _upload(client, folder_id, MALFORMED_PDF_BYTES, "broken.pdf", "application/pdf")
	# Upload still succeeds -- a text-extraction problem must not delete or
	# reject an otherwise validly-typed uploaded document.
	assert resp.status_code == 201, resp.text
	doc_id = resp.json()["id"]

	detail = client.get(f"/documents/{doc_id}").json()
	assert detail["extraction_status"] == "failed"
	assert detail["original_text"] is None

	# and it's still a normal, retrievable, deletable document
	assert client.delete(f"/documents/{doc_id}").status_code == 204


def test_jpeg_upload_remains_valid_but_not_falsely_extracted(client):
	register_and_login(client, "extract_jpeg@example.com")
	folder_id = _first_root_folder_id(client)
	doc_id = _upload(client, folder_id, JPEG_BYTES, "photo.jpg", "image/jpeg").json()["id"]

	detail = client.get(f"/documents/{doc_id}").json()
	assert detail["mime_type"] == "image/jpeg"
	assert detail["extraction_status"] == "pending"
	assert detail["original_text"] is None


def test_png_upload_remains_valid_but_not_falsely_extracted(client):
	register_and_login(client, "extract_png@example.com")
	folder_id = _first_root_folder_id(client)
	doc_id = _upload(client, folder_id, PNG_BYTES, "scan.png", "image/png").json()["id"]

	detail = client.get(f"/documents/{doc_id}").json()
	assert detail["mime_type"] == "image/png"
	assert detail["extraction_status"] == "pending"
	assert detail["original_text"] is None
