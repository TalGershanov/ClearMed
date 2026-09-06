import asyncio
import logging
import uuid
from typing import Optional, Tuple

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from webapp.core import config
from webapp.documents.models import AnalysisStatus, Document, ExtractionStatus, SimplificationStatus
from webapp.extraction import get_extractor
from webapp.storage import get_storage

# Phase 5: reuses the exact same ClearMed functions the live /analyse and
# /translate endpoints call (see server/api.py) -- never a duplicate
# implementation, never an HTTP call to our own API.
from logic.medical_term_detector import build_ui_selection, detect_terms_with_explanations
from logic.term_detectors.hebrew import detect_language_code
from logic.translator import apply_translations

# Same explanation field /translate uses (see server/api.py::translate_text) --
# keeping this in one place means both endpoints stay consistent by construction.
_EXPLANATION_FIELD = "short_explanation"

# Never log full extracted document text -- it may be medical content. Log
# lines below only ever reference ids, mime types, and status values.
logger = logging.getLogger("clearmed.webapp.documents")

_CHUNK_SIZE = 1024 * 1024  # 1 MB

# Sniffed from actual file content, never trusted from the client's declared
# Content-Type or filename extension. Order matters only in that PDF/JPEG/PNG
# magic bytes are mutually exclusive, so first-match is fine.
_MAGIC_SNIFFERS: list[Tuple[bytes, str, str]] = [
	(b"%PDF-", "application/pdf", ".pdf"),
	(b"\xff\xd8\xff", "image/jpeg", ".jpg"),
	(b"\x89PNG\r\n\x1a\n", "image/png", ".png"),
]


def _sniff_mime_type(header: bytes) -> Optional[Tuple[str, str]]:
	for magic, mime_type, extension in _MAGIC_SNIFFERS:
		if header.startswith(magic):
			return mime_type, extension
	return None


async def _read_upload_within_limit(file: UploadFile, max_bytes: int) -> bytes:
	"""Reads the upload in bounded chunks, aborting as soon as the limit is
	exceeded rather than buffering an arbitrarily large body first -- a
	naive `await file.read()` would let a client attempt to exhaust server
	memory before any size check ever ran."""
	data = bytearray()
	while True:
		chunk = await file.read(_CHUNK_SIZE)
		if not chunk:
			break
		data.extend(chunk)
		if len(data) > max_bytes:
			raise HTTPException(
				status_code=status.HTTP_413_CONTENT_TOO_LARGE,
				detail=f"File exceeds the {max_bytes // (1024 * 1024)} MB limit",
			)
	return bytes(data)


def _extract_text_if_applicable(mime_type: str, data: bytes) -> Tuple[Optional[str], str]:
	"""Never raises -- any extractor failure is caught here and turned into
	a FAILED status, so a text-extraction problem can never block or
	unwind the upload itself (the document row must still get created).

	This is a plain blocking function (not async) even though the OCR path
	(webapp/extraction/ocr.py) makes a real network call to Gemini -- callers
	must run it via asyncio.to_thread (see save_uploaded_document below) so
	that call doesn't stall the event loop, exactly like server/api.py's own
	POST /ocr endpoint already does for the same reason."""
	extractor = get_extractor(mime_type)
	if extractor is None:
		return None, ExtractionStatus.PENDING.value

	try:
		text = extractor.extract(data)
	except Exception:
		# Deliberately no document content in this log line -- see the
		# module-level note on not logging extracted medical text.
		logger.exception("Text extraction raised for mime_type=%s", mime_type)
		return None, ExtractionStatus.FAILED.value

	if text is None:
		return None, ExtractionStatus.NO_TEXT_FOUND.value
	return text, ExtractionStatus.EXTRACTED.value


def get_owned_document_or_404(db: Session, user_id: int, document_id: int) -> Document:
	"""Same ownership-gate pattern as webapp/folders/service.py::get_owned_folder_or_404
	-- 404 (never 403) whether the document doesn't exist or belongs to
	someone else, so existence isn't leaked across users."""
	document = db.get(Document, document_id)
	if document is None or document.user_id != user_id:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
	return document


def list_documents_in_folder(db: Session, folder_id: int) -> list[Document]:
	return db.query(Document).filter(Document.folder_id == folder_id).order_by(Document.created_at).all()


async def save_uploaded_document(
	db: Session,
	user_id: int,
	folder_id: int,
	display_name: Optional[str],
	file: UploadFile,
) -> Document:
	data = await _read_upload_within_limit(file, config.MAX_UPLOAD_SIZE_BYTES)
	if not data:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty")

	sniffed = _sniff_mime_type(data[:16])
	if sniffed is None:
		raise HTTPException(
			status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
			detail="Unsupported file type. Allowed: PDF, JPG, PNG.",
		)
	mime_type, extension = sniffed

	name = (display_name or "").strip() or (file.filename or "Untitled document")
	# Server-generated -- original_filename below is stored as metadata only
	# and never touches this key or any filesystem path (see webapp/storage/).
	storage_key = f"{uuid.uuid4().hex}{extension}"

	storage = get_storage()
	storage.save(data, storage_key)  # if this raises, nothing below runs -- no DB row is created

	# Extraction runs on the bytes already in memory and never raises out of
	# this function (see _extract_text_if_applicable) -- a text-extraction
	# problem must never prevent the document row itself from being created
	# (see webapp/extraction/). Run off the event loop: the OCR path makes a
	# real blocking network call to Gemini, so this can take several seconds.
	original_text, extraction_status = await asyncio.to_thread(_extract_text_if_applicable, mime_type, data)

	document = Document(
		user_id=user_id,
		folder_id=folder_id,
		name=name,
		original_filename=file.filename or "upload",
		mime_type=mime_type,
		storage_key=storage_key,
		file_size=len(data),
		original_text=original_text,
		extraction_status=extraction_status,
	)
	db.add(document)
	try:
		db.commit()
	except Exception:
		db.rollback()
		storage.delete(storage_key)
		logger.exception("Failed to persist document row after storing file; cleaned up orphaned file")
		raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not save document")
	db.refresh(document)

	logger.info("User id=%s uploaded document id=%s into folder id=%s", user_id, document.id, folder_id)
	return document


def analyse_document(db: Session, document: Document) -> Document:
	"""Runs the same ClearMed term-detection logic /analyse uses against this
	document's own extracted text and persists the result, so reopening the
	document never loses it.

	Idempotent: if analysis already succeeded, returns the persisted result
	as-is rather than re-running detection (no explicit re-analyse trigger
	exists yet -- keep this simple until one is actually needed)."""
	if document.analysis_status == AnalysisStatus.ANALYSED.value and document.detected_terms is not None:
		return document

	if document.extraction_status != ExtractionStatus.EXTRACTED.value or not document.original_text:
		raise HTTPException(
			status_code=status.HTTP_409_CONFLICT,
			detail="Document has no extracted text to analyse",
		)

	try:
		language_code = detect_language_code(document.original_text)
		detected_terms = detect_terms_with_explanations(document.original_text, language_code)
	except ValueError as e:
		document.analysis_status = AnalysisStatus.FAILED.value
		db.commit()
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
	except Exception:
		document.analysis_status = AnalysisStatus.FAILED.value
		db.commit()
		# Deliberately no document content in this log line.
		logger.exception("Analysis failed for document id=%s", document.id)
		raise HTTPException(
			status_code=status.HTTP_502_BAD_GATEWAY,
			detail="Analysis failed. The document and its extracted text were preserved.",
		)

	document.detected_terms = detected_terms
	document.term_selection = build_ui_selection(detected_terms)
	document.analysis_status = AnalysisStatus.ANALYSED.value
	db.commit()
	db.refresh(document)

	logger.info("Analysed document id=%s: %d term(s) detected", document.id, len(detected_terms))
	return document


def update_term_selection(db: Session, document: Document, term_selection: dict) -> Document:
	if document.analysis_status != AnalysisStatus.ANALYSED.value:
		raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Document has not been analysed yet")

	document.term_selection = term_selection
	db.commit()
	db.refresh(document)
	return document


def update_document_notes(db: Session, document: Document, notes: str) -> Document:
	"""Independent of analysis/simplification -- a note can be saved on any
	document regardless of pipeline state, and never touches those fields."""
	document.notes = notes
	db.commit()
	db.refresh(document)
	return document


def simplify_document(db: Session, document: Document) -> Document:
	"""Runs the same apply_translations pipeline /translate uses (see
	logic/translator.py), against this document's persisted detected_terms
	and term_selection. Freely re-callable (no "already simplified" guard) so
	the user can change their selection and simplify again, or just retry.

	document.detected_terms is stored verbatim from
	detect_terms_with_explanations() (see analyse_document below) -- one
	entry per text occurrence, exactly the shape apply_translations expects
	for its own position-based splicing, the same shape /translate's handler
	re-detects fresh from request.text.

	analysis_status/detected_terms/term_selection/original_text are never
	touched here -- only simplification_status/simplified_text change, so a
	failure in this function can't lose the analysis or the user's selections."""
	if document.analysis_status != AnalysisStatus.ANALYSED.value or document.detected_terms is None:
		raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Document has not been analysed yet")

	try:
		selection = document.term_selection or {}
		translated_text, explained_terms_list = apply_translations(
			document.original_text, document.detected_terms, selection, _EXPLANATION_FIELD
		)
		document.simplified_text = translated_text
		document.simplification_status = SimplificationStatus.SIMPLIFIED.value
		db.commit()
	except Exception:
		db.rollback()
		document.simplification_status = SimplificationStatus.FAILED.value
		db.commit()
		logger.exception("Simplification failed for document id=%s", document.id)
		raise HTTPException(
			status_code=status.HTTP_502_BAD_GATEWAY,
			detail="Simplification failed. Your analysis and selections were preserved -- you can try again.",
		)

	db.refresh(document)
	logger.info(
		"Simplified document id=%s using %d approved explanation(s)", document.id, len(explained_terms_list)
	)
	return document


def delete_document_and_file(db: Session, document: Document) -> None:
	document_id = document.id
	storage_key = document.storage_key
	db.delete(document)
	db.commit()
	try:
		get_storage().delete(storage_key)
	except OSError:
		logger.warning("Failed to delete stored file for document id=%s (key=%s)", document_id, storage_key)
