from typing import Optional

from webapp.extraction.base import TextExtractor
from webapp.extraction.ocr import ImageOCRExtractor, ocr_pdf_pages
from webapp.extraction.pdf import PDFTextExtractor


class _PDFExtractor(TextExtractor):
	"""Tries pypdf first (fast, no external call, unchanged Phase 4 behavior
	for a normal text-based PDF); only falls back to OCR when pypdf parses
	cleanly but finds no meaningful text (a scanned PDF with no text layer).
	A malformed PDF raises straight out of the pypdf attempt and never
	reaches OCR -- that's a parsing failure, not a "needs OCR" case."""

	def __init__(self):
		self._text_extractor = PDFTextExtractor()

	def extract(self, data: bytes) -> Optional[str]:
		text = self._text_extractor.extract(data)
		if text is not None:
			return text
		return ocr_pdf_pages(data)


_EXTRACTORS: dict = {
	"application/pdf": _PDFExtractor(),
	"image/jpeg": ImageOCRExtractor("image/jpeg"),
	"image/png": ImageOCRExtractor("image/png"),
}


def get_extractor(mime_type: str) -> Optional[TextExtractor]:
	"""None means there's no extractor registered for this mime type -- not a
	failure (webapp/documents/service.py treats it as PENDING). Every
	currently-uploadable mime type (PDF, JPG, PNG) has one; this stays a
	lookup so a future mime type can be added here without touching
	webapp/documents/ at all."""
	return _EXTRACTORS.get(mime_type)
