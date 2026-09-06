from unittest.mock import patch

from logic.translator import apply_translations
from tests.conftest import register_and_login
from tests.test_documents import _first_root_folder_id, _upload
from tests.test_extraction import MALFORMED_PDF_BYTES, _build_pdf, _build_textless_pdf

# Term detection is mocked throughout this file: the trie is never built in
# tests (see conftest.py). Simplification itself (apply_translations, see
# logic/translator.py) is a pure local function -- no external API call, so
# it's never mocked; tests that need an expected simplified value call it
# directly as the oracle (see _expected_simplified below). These fixtures
# mirror the true shape of logic.medical_term_detector.detect_terms_with_explanations()'s
# return value (see logic/medical_term_detector.py), keyed by concept_id
# in "main_term" -- never by term name.
A1C_TERM = {
	"matched_text": "A1C",
	"main_term": "6308",
	"term_name": "A1C",
	"start": 8,
	"end": 11,
	"short_explanation": "A blood test that shows your average blood sugar over three months.",
	"simple_explanation": "A blood sugar test.",
	"categories": ["lab test"],
	"synonyms": ["hemoglobin a1c"],
}
BP_TERM = {
	"matched_text": "hypertension",
	"main_term": "3877",
	"term_name": "Hypertension",
	"start": 20,
	"end": 32,
	"short_explanation": "High blood pressure.",
	"simple_explanation": "Your blood pressure is higher than normal.",
	"categories": ["condition"],
	"synonyms": ["high blood pressure"],
}


def _upload_extracted_pdf(client, text="Patient A1C and hypertension results.", filename="report.pdf"):
	folder_id = _first_root_folder_id(client)
	pdf_bytes = _build_pdf([text])
	resp = _upload(client, folder_id, pdf_bytes, filename, "application/pdf")
	assert resp.status_code == 201, resp.text
	return resp.json()["id"]


def _patched_detection(detected_terms):
	return (
		patch("webapp.documents.service.detect_language_code", return_value="en"),
		patch("webapp.documents.service.detect_terms_with_explanations", return_value=detected_terms),
	)


def _expected_simplified(text, detected_terms, selection):
	"""The real, deterministic apply_translations output -- used as the
	expected value instead of a mocked/hand-computed string, so these tests
	stay correct even if the splice's exact formatting ever changes."""
	translated_text, _ = apply_translations(text, detected_terms, selection, "short_explanation")
	return translated_text


# --- Analysis ----------------------------------------------------------------

def test_owner_can_analyse_document(client):
	register_and_login(client, "analyse_owner@example.com")
	doc_id = _upload_extracted_pdf(client)

	p1, p2 = _patched_detection([A1C_TERM, BP_TERM])
	with p1, p2:
		resp = client.post(f"/documents/{doc_id}/analyse")
	assert resp.status_code == 200, resp.text
	body = resp.json()
	assert body["analysis_status"] == "analysed"
	assert body["detected_terms"] == [A1C_TERM, BP_TERM]
	# ui_selection defaults every detected concept_id to approved
	assert body["term_selection"] == {"6308": True, "3877": True}


def test_analysis_persists_across_requests(client):
	register_and_login(client, "analyse_persist@example.com")
	doc_id = _upload_extracted_pdf(client)

	p1, p2 = _patched_detection([A1C_TERM])
	with p1, p2:
		client.post(f"/documents/{doc_id}/analyse")

	# A fresh GET (no mocks active) must return the persisted result, not
	# re-run detection.
	detail = client.get(f"/documents/{doc_id}").json()
	assert detail["analysis_status"] == "analysed"
	assert detail["detected_terms"] == [A1C_TERM]


def test_analyse_is_idempotent_and_does_not_rerun_detection(client):
	register_and_login(client, "analyse_idempotent@example.com")
	doc_id = _upload_extracted_pdf(client)

	p1, p2 = _patched_detection([A1C_TERM])
	with p1, p2:
		client.post(f"/documents/{doc_id}/analyse")

	# Second call: detection mocks are NOT active, so if the endpoint tried
	# to re-run detection it would hit the real (un-built) trie and raise.
	resp = client.post(f"/documents/{doc_id}/analyse")
	assert resp.status_code == 200, resp.text
	assert resp.json()["detected_terms"] == [A1C_TERM]


def test_zero_detected_terms_handled_gracefully(client):
	register_and_login(client, "analyse_zero@example.com")
	doc_id = _upload_extracted_pdf(client, text="Nothing medical in here at all.")

	p1, p2 = _patched_detection([])
	with p1, p2:
		resp = client.post(f"/documents/{doc_id}/analyse")
	assert resp.status_code == 200, resp.text
	body = resp.json()
	assert body["analysis_status"] == "analysed"
	assert body["detected_terms"] == []
	assert body["term_selection"] == {}


def test_document_without_extracted_text_cannot_be_analysed(client):
	register_and_login(client, "analyse_no_text@example.com")
	folder_id = _first_root_folder_id(client)
	# pypdf finds nothing, and the OCR fallback (mocked) finds nothing either
	# -- genuinely no usable text, not an OCR-service failure.
	with patch("webapp.extraction.ocr.extract_text_from_image", side_effect=ValueError("no text")):
		doc_id = _upload(client, folder_id, _build_textless_pdf(), "scan.pdf", "application/pdf").json()["id"]
	assert client.get(f"/documents/{doc_id}").json()["extraction_status"] == "no_text_found"

	resp = client.post(f"/documents/{doc_id}/analyse")
	assert resp.status_code == 409


def test_analysis_failure_preserves_document_and_original_text(client):
	register_and_login(client, "analyse_failure@example.com")
	doc_id = _upload_extracted_pdf(client)

	with patch("webapp.documents.service.detect_language_code", side_effect=RuntimeError("boom")):
		resp = client.post(f"/documents/{doc_id}/analyse")
	assert resp.status_code == 502

	detail = client.get(f"/documents/{doc_id}").json()
	assert detail["analysis_status"] == "failed"
	assert detail["original_text"] is not None
	assert detail["extraction_status"] == "extracted"


def test_another_user_cannot_analyse_document(client, second_client):
	register_and_login(client, "analyse_a@example.com")
	register_and_login(second_client, "analyse_b@example.com")
	doc_id = _upload_extracted_pdf(client)

	resp = second_client.post(f"/documents/{doc_id}/analyse")
	assert resp.status_code == 404


# --- Term selection ------------------------------------------------------------

def test_owner_can_update_term_selection(client):
	register_and_login(client, "selection_owner@example.com")
	doc_id = _upload_extracted_pdf(client)

	p1, p2 = _patched_detection([A1C_TERM, BP_TERM])
	with p1, p2:
		client.post(f"/documents/{doc_id}/analyse")

	resp = client.patch(f"/documents/{doc_id}/selection", json={"term_selection": {"6308": True, "3877": False}})
	assert resp.status_code == 200, resp.text
	assert resp.json()["term_selection"] == {"6308": True, "3877": False}


def test_term_selection_persists_across_requests(client):
	register_and_login(client, "selection_persist@example.com")
	doc_id = _upload_extracted_pdf(client)

	p1, p2 = _patched_detection([A1C_TERM])
	with p1, p2:
		client.post(f"/documents/{doc_id}/analyse")
	client.patch(f"/documents/{doc_id}/selection", json={"term_selection": {"6308": False}})

	detail = client.get(f"/documents/{doc_id}").json()
	assert detail["term_selection"] == {"6308": False}


def test_selection_update_requires_prior_analysis(client):
	register_and_login(client, "selection_no_analysis@example.com")
	doc_id = _upload_extracted_pdf(client)

	resp = client.patch(f"/documents/{doc_id}/selection", json={"term_selection": {"6308": True}})
	assert resp.status_code == 409


def test_another_user_cannot_update_term_selection(client, second_client):
	register_and_login(client, "selection_a@example.com")
	register_and_login(second_client, "selection_b@example.com")
	doc_id = _upload_extracted_pdf(client)

	p1, p2 = _patched_detection([A1C_TERM])
	with p1, p2:
		client.post(f"/documents/{doc_id}/analyse")

	resp = second_client.patch(f"/documents/{doc_id}/selection", json={"term_selection": {"6308": False}})
	assert resp.status_code == 404


# --- Simplification ------------------------------------------------------------

def _analyse_and_select(client, doc_id, detected_terms, selection=None):
	p1, p2 = _patched_detection(detected_terms)
	with p1, p2:
		client.post(f"/documents/{doc_id}/analyse")
	if selection is not None:
		client.patch(f"/documents/{doc_id}/selection", json={"term_selection": selection})


def test_owner_can_simplify_document(client):
	register_and_login(client, "simplify_owner@example.com")
	text = "Patient A1C and hypertension results."
	doc_id = _upload_extracted_pdf(client, text=text)
	_analyse_and_select(client, doc_id, [A1C_TERM])

	resp = client.post(f"/documents/{doc_id}/simplify")
	assert resp.status_code == 200, resp.text
	body = resp.json()
	assert body["simplification_status"] == "simplified"
	# Confirms the real apply_translations pipeline ran (the same mechanical
	# parenthesis-splice /translate uses, see logic/translator.py) -- not a
	# mocked substitute.
	assert body["simplified_text"] == _expected_simplified(text, [A1C_TERM], {"6308": True})


def test_simplify_only_uses_approved_terms(client):
	register_and_login(client, "simplify_partial@example.com")
	text = "Patient A1C and hypertension results."
	doc_id = _upload_extracted_pdf(client, text=text)
	_analyse_and_select(client, doc_id, [A1C_TERM, BP_TERM], selection={"6308": True, "3877": False})

	resp = client.post(f"/documents/{doc_id}/simplify")
	simplified_text = resp.json()["simplified_text"]
	assert A1C_TERM["short_explanation"].rstrip(".") in simplified_text
	assert BP_TERM["short_explanation"] not in simplified_text


def test_simplified_text_persists_and_shows_in_document_detail(client):
	register_and_login(client, "simplify_persist@example.com")
	text = "Patient A1C and hypertension results."
	doc_id = _upload_extracted_pdf(client, text=text)
	_analyse_and_select(client, doc_id, [A1C_TERM])

	client.post(f"/documents/{doc_id}/simplify")

	detail = client.get(f"/documents/{doc_id}").json()
	assert detail["simplification_status"] == "simplified"
	assert detail["simplified_text"] == _expected_simplified(text, [A1C_TERM], {"6308": True})
	# Original text and analysis must remain untouched by simplification.
	assert detail["analysis_status"] == "analysed"
	assert detail["original_text"] is not None


def test_simplify_requires_prior_analysis(client):
	register_and_login(client, "simplify_no_analysis@example.com")
	doc_id = _upload_extracted_pdf(client)

	resp = client.post(f"/documents/{doc_id}/simplify")
	assert resp.status_code == 409


def test_simplify_failure_preserves_analysis_and_selection(client):
	register_and_login(client, "simplify_failure@example.com")
	doc_id = _upload_extracted_pdf(client)
	_analyse_and_select(client, doc_id, [A1C_TERM], selection={"6308": True})

	with patch("webapp.documents.service.apply_translations", side_effect=RuntimeError("translation failed")):
		resp = client.post(f"/documents/{doc_id}/simplify")
	assert resp.status_code == 502

	detail = client.get(f"/documents/{doc_id}").json()
	assert detail["simplification_status"] == "failed"
	assert detail["analysis_status"] == "analysed"
	assert detail["detected_terms"] == [A1C_TERM]
	assert detail["term_selection"] == {"6308": True}


def test_simplify_can_be_retried_after_failure(client):
	register_and_login(client, "simplify_retry@example.com")
	doc_id = _upload_extracted_pdf(client)
	_analyse_and_select(client, doc_id, [A1C_TERM])

	with patch("webapp.documents.service.apply_translations", side_effect=RuntimeError("translation failed")):
		client.post(f"/documents/{doc_id}/simplify")

	with patch("webapp.documents.service.apply_translations", return_value=("Recovered simplification.", ["A1C"])):
		resp = client.post(f"/documents/{doc_id}/simplify")
	assert resp.status_code == 200
	assert resp.json()["simplification_status"] == "simplified"
	assert resp.json()["simplified_text"] == "Recovered simplification."


def test_another_user_cannot_simplify_document(client, second_client):
	register_and_login(client, "simplify_a@example.com")
	register_and_login(second_client, "simplify_b@example.com")
	doc_id = _upload_extracted_pdf(client)
	_analyse_and_select(client, doc_id, [A1C_TERM])

	resp = second_client.post(f"/documents/{doc_id}/simplify")
	assert resp.status_code == 404


def test_zero_selected_terms_leaves_text_unchanged(client):
	register_and_login(client, "simplify_zero_selected@example.com")
	text = "Patient A1C and hypertension results."
	doc_id = _upload_extracted_pdf(client, text=text)
	_analyse_and_select(client, doc_id, [A1C_TERM], selection={"6308": False})

	resp = client.post(f"/documents/{doc_id}/simplify")
	assert resp.status_code == 200
	# No approved terms -- apply_translations splices nothing in.
	assert resp.json()["simplified_text"] == text


# --- Cross-cutting security --------------------------------------------------

def test_malformed_pdf_document_cannot_be_analysed(client):
	register_and_login(client, "analyse_malformed@example.com")
	folder_id = _first_root_folder_id(client)
	doc_id = _upload(client, folder_id, MALFORMED_PDF_BYTES, "broken.pdf", "application/pdf").json()["id"]

	resp = client.post(f"/documents/{doc_id}/analyse")
	assert resp.status_code == 409


def test_no_cross_user_data_leakage_in_document_detail(client, second_client):
	register_and_login(client, "leak_a@example.com")
	register_and_login(second_client, "leak_b@example.com")
	doc_id = _upload_extracted_pdf(client, text="Secret A1C content for user A only.")
	_analyse_and_select(client, doc_id, [A1C_TERM])
	client.post(f"/documents/{doc_id}/simplify")

	resp = second_client.get(f"/documents/{doc_id}")
	assert resp.status_code == 404
