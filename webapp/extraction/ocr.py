import logging
from typing import Optional

import pymupdf  # rasterizes PDF pages to images; no system dependency

# Reuses the exact same Gemini OCR call the standalone POST /ocr endpoint
# uses (server/api.py) -- never a separate OCR implementation.
from logic.ocr import extract_text_from_image
from webapp.extraction.base import TextExtractor
from webapp.extraction.quality import is_meaningful_text

logger = logging.getLogger("clearmed.webapp.extraction.ocr")

# Page images are rendered at this resolution before OCR -- high enough for
# Gemini to read normal print reliably without producing an unreasonably
# large per-page image.
_RENDER_DPI = 200

# Mirrors server/api.py's MAX_OCR_IMAGE_BYTES: stays under Gemini's
# inline-request ceiling once base64-encoded. Applied here too since the
# documents upload pipeline (up to 20 MB, see webapp/core/config.py) doesn't
# go through that endpoint and would otherwise hit an unpredictable failure
# from Gemini itself for a large image.
_MAX_OCR_IMAGE_BYTES = 15 * 1024 * 1024


def _ocr_image_bytes(data: bytes, mime_type: str) -> Optional[str]:
	"""Shared by ImageOCRExtractor and ocr_pdf_pages so the size guard and
	error handling live in exactly one place. Returns None for "no readable
	text" (not a failure); raises for a genuine service/config problem."""
	if len(data) > _MAX_OCR_IMAGE_BYTES:
		raise RuntimeError(f"Image exceeds the {_MAX_OCR_IMAGE_BYTES // (1024 * 1024)} MB OCR limit")
	try:
		text = extract_text_from_image(data, mime_type)
	except ValueError:
		# Gemini found nothing readable -- not a failure, see base.TextExtractor.
		return None
	text = text.strip()
	return text if is_meaningful_text(text) else None


class ImageOCRExtractor(TextExtractor):
	"""Runs OCR directly against an uploaded JPG/PNG. One instance per mime
	type (bound at registration in webapp/extraction/__init__.py) rather than
	widening the TextExtractor interface with a mime_type parameter."""

	def __init__(self, mime_type: str):
		self._mime_type = mime_type

	def extract(self, data: bytes) -> Optional[str]:
		return _ocr_image_bytes(data, self._mime_type)


def ocr_pdf_pages(data: bytes) -> Optional[str]:
	"""OCR fallback for a scanned PDF with no text layer: rasterizes each
	page and OCRs it, joining page text in page order -- mirrors
	PDFTextExtractor's page-join behavior (webapp/extraction/pdf.py) so
	callers see one consistent shape regardless of which path produced the
	text.

	A single unreadable page is skipped (not fatal) so one bad scan in a
	multi-page document doesn't sink the rest; only a genuinely malformed PDF,
	an OCR service/config failure, or a total lack of readable pages ends
	extraction here -- all of which propagate/resolve exactly like
	PDFTextExtractor.extract() and ImageOCRExtractor.extract() already do."""
	doc = pymupdf.open(stream=data, filetype="pdf")  # raises on a genuinely malformed PDF
	try:
		page_texts = []
		for page in doc:
			pixmap = page.get_pixmap(dpi=_RENDER_DPI)
			page_text = _ocr_image_bytes(pixmap.tobytes("png"), "image/png")
			if page_text:
				page_texts.append(page_text)
	finally:
		doc.close()

	full_text = "\n\n".join(page_texts).strip()
	return full_text if is_meaningful_text(full_text) else None
