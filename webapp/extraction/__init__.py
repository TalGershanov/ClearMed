from typing import Optional

from webapp.extraction.base import TextExtractor
from webapp.extraction.pdf import PDFTextExtractor

_EXTRACTORS: dict = {
	"application/pdf": PDFTextExtractor(),
}


def get_extractor(mime_type: str) -> Optional[TextExtractor]:
	"""None means there's no extractor registered for this mime type yet
	(images, pending OCR support in a later phase) -- not a failure. This is
	the one seam Phase 4.1 needs: register an OCRExtractor for image mime
	types (and optionally re-route NO_TEXT_FOUND PDFs through it) without
	touching webapp/documents/ at all."""
	return _EXTRACTORS.get(mime_type)
