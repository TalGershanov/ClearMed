import io
from unittest.mock import patch

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
	"""pypdf finds nothing (see _build_textless_pdf), so the OCR fallback
	(webapp/extraction/ocr.py::ocr_pdf_pages) runs against the rendered page
	image too -- mocked here to also find nothing, since a blank page
	legitimately has no readable text either way."""
	register_and_login(client, "extract_scanned@example.com")
	folder_id = _first_root_folder_id(client)
	pdf_bytes = _build_textless_pdf()
	with patch("webapp.extraction.ocr.extract_text_from_image", side_effect=ValueError("no text")):
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


def test_jpeg_with_no_readable_text_does_not_falsely_extract(client):
	"""JPEG_BYTES is a magic-byte fixture, not a real photo -- OCR is mocked
	to report no readable text (an honest simulation of that), confirming
	images now run through real OCR instead of always sitting at PENDING."""
	register_and_login(client, "extract_jpeg@example.com")
	folder_id = _first_root_folder_id(client)
	with patch("webapp.extraction.ocr.extract_text_from_image", side_effect=ValueError("no text")):
		doc_id = _upload(client, folder_id, JPEG_BYTES, "photo.jpg", "image/jpeg").json()["id"]

	detail = client.get(f"/documents/{doc_id}").json()
	assert detail["mime_type"] == "image/jpeg"
	assert detail["extraction_status"] == "no_text_found"
	assert detail["original_text"] is None


def test_png_with_no_readable_text_does_not_falsely_extract(client):
	register_and_login(client, "extract_png@example.com")
	folder_id = _first_root_folder_id(client)
	with patch("webapp.extraction.ocr.extract_text_from_image", side_effect=ValueError("no text")):
		doc_id = _upload(client, folder_id, PNG_BYTES, "scan.png", "image/png").json()["id"]

	detail = client.get(f"/documents/{doc_id}").json()
	assert detail["mime_type"] == "image/png"
	assert detail["extraction_status"] == "no_text_found"
	assert detail["original_text"] is None


def test_jpeg_with_readable_text_is_extracted_via_ocr(client):
	register_and_login(client, "extract_jpeg_ocr@example.com")
	folder_id = _first_root_folder_id(client)
	with patch("webapp.extraction.ocr.extract_text_from_image", return_value="Patient notes: blood pressure 120/80.") as mock_ocr:
		doc_id = _upload(client, folder_id, JPEG_BYTES, "photo.jpg", "image/jpeg").json()["id"]
	mock_ocr.assert_called_once_with(JPEG_BYTES, "image/jpeg")

	detail = client.get(f"/documents/{doc_id}").json()
	assert detail["extraction_status"] == "extracted"
	assert detail["original_text"] == "Patient notes: blood pressure 120/80."


def test_png_with_readable_text_is_extracted_via_ocr(client):
	register_and_login(client, "extract_png_ocr@example.com")
	folder_id = _first_root_folder_id(client)
	with patch("webapp.extraction.ocr.extract_text_from_image", return_value="Prescription: Metformin 500mg twice daily.") as mock_ocr:
		doc_id = _upload(client, folder_id, PNG_BYTES, "scan.png", "image/png").json()["id"]
	mock_ocr.assert_called_once_with(PNG_BYTES, "image/png")

	detail = client.get(f"/documents/{doc_id}").json()
	assert detail["extraction_status"] == "extracted"
	assert detail["original_text"] == "Prescription: Metformin 500mg twice daily."


def test_ocr_service_failure_marks_document_failed_and_stays_retryable(client):
	"""A hard OCR-service problem (e.g. missing GEMINI_API_KEY, surfaced as a
	RuntimeError by logic/ocr.py) must land on FAILED, not NO_TEXT_FOUND --
	this is a service/config issue, not "genuinely no text in the image"."""
	register_and_login(client, "extract_ocr_failure@example.com")
	folder_id = _first_root_folder_id(client)
	with patch("webapp.extraction.ocr.extract_text_from_image", side_effect=RuntimeError("GEMINI_API_KEY is not configured")):
		doc_id = _upload(client, folder_id, JPEG_BYTES, "photo.jpg", "image/jpeg").json()["id"]

	detail = client.get(f"/documents/{doc_id}").json()
	assert detail["extraction_status"] == "failed"
	assert detail["original_text"] is None

	# Retryable via the normal document lifecycle -- still a real, deletable
	# document, same guarantee as a malformed-PDF failure.
	assert client.delete(f"/documents/{doc_id}").status_code == 204


def test_scanned_pdf_ocr_fallback_extracts_text_and_persists_it(client):
	"""pypdf finds nothing (blank content stream), so the OCR fallback runs
	against the rendered page image and its result is what gets persisted."""
	register_and_login(client, "extract_scanned_ocr@example.com")
	folder_id = _first_root_folder_id(client)
	pdf_bytes = _build_textless_pdf()
	ocr_text = "Lab results: A1C is 6.2 percent, within the expected range for this patient."
	with patch("webapp.extraction.ocr.extract_text_from_image", return_value=ocr_text) as mock_ocr:
		doc_id = _upload(client, folder_id, pdf_bytes, "scanned.pdf", "application/pdf").json()["id"]
	mock_ocr.assert_called_once()
	assert mock_ocr.call_args.args[1] == "image/png"

	detail = client.get(f"/documents/{doc_id}").json()
	assert detail["extraction_status"] == "extracted"
	assert detail["original_text"] == ocr_text


def _build_multi_page_textless_pdf(n_pages: int) -> bytes:
	"""Same shape as _build_textless_pdf, generalized to N pages, each with
	an empty content stream -- a structurally valid multi-page PDF that
	pypdf will correctly find zero text in on every page."""
	page_obj_nums = list(range(3, 3 + n_pages))
	content_obj_nums = list(range(3 + n_pages, 3 + 2 * n_pages))

	catalog = b"<< /Type /Catalog /Pages 2 0 R >>"
	kids = " ".join(f"{n} 0 R" for n in page_obj_nums)
	pages = f"<< /Type /Pages /Kids [{kids}] /Count {n_pages} >>".encode()
	page_objs = [
		f"<< /Type /Page /Parent 2 0 R /Resources << >> /MediaBox [0 0 300 300] /Contents {content_obj_nums[i]} 0 R >>".encode()
		for i in range(n_pages)
	]
	content_objs = [b"<< /Length 0 >>\nstream\n\nendstream" for _ in range(n_pages)]
	all_objs = [catalog, pages] + page_objs + content_objs

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


def test_multi_page_scanned_pdf_joins_page_text_in_order(client):
	register_and_login(client, "extract_multipage_ocr@example.com")
	folder_id = _first_root_folder_id(client)
	pdf_bytes = _build_multi_page_textless_pdf(2)
	with patch(
		"webapp.extraction.ocr.extract_text_from_image",
		side_effect=["First page content alpha.", "Second page content beta."],
	) as mock_ocr:
		doc_id = _upload(client, folder_id, pdf_bytes, "scanned.pdf", "application/pdf").json()["id"]
	assert mock_ocr.call_count == 2

	text = client.get(f"/documents/{doc_id}").json()["original_text"]
	assert text.index("First page content alpha.") < text.index("Second page content beta.")


def test_one_unreadable_page_does_not_sink_the_rest(client):
	"""A single blank/unreadable page among several must not fail the whole
	document -- ocr_pdf_pages skips it and keeps the pages that did OCR."""
	register_and_login(client, "extract_multipage_partial@example.com")
	folder_id = _first_root_folder_id(client)
	pdf_bytes = _build_multi_page_textless_pdf(2)
	second_page_text = "This second page has perfectly readable content in it."
	with patch(
		"webapp.extraction.ocr.extract_text_from_image",
		side_effect=[ValueError("no text on this page"), second_page_text],
	):
		doc_id = _upload(client, folder_id, pdf_bytes, "scanned.pdf", "application/pdf").json()["id"]

	detail = client.get(f"/documents/{doc_id}").json()
	assert detail["extraction_status"] == "extracted"
	assert detail["original_text"] == second_page_text


def test_another_user_cannot_get_ocr_extracted_text(client, second_client):
	"""Ownership enforcement (get_owned_document_or_404) doesn't know or care
	how a document's text was produced -- confirms OCR-derived text is
	protected exactly like pypdf-derived text (see test_another_user_cannot_get_original_text)."""
	register_and_login(client, "extract_ocr_owner_a@example.com")
	register_and_login(second_client, "extract_ocr_owner_b@example.com")
	folder_id = _first_root_folder_id(client)
	with patch("webapp.extraction.ocr.extract_text_from_image", return_value="Secret OCR content only A should see."):
		doc_id = _upload(client, folder_id, JPEG_BYTES, "photo.jpg", "image/jpeg").json()["id"]

	resp = second_client.get(f"/documents/{doc_id}")
	assert resp.status_code == 404
