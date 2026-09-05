import io
from typing import Optional

from pypdf import PdfReader

from webapp.extraction.base import TextExtractor

# Below this, treat the PDF as having no meaningful extractable text (most
# likely a scanned document with no text layer) rather than claiming success
# over a handful of stray characters.
_MIN_MEANINGFUL_CHARS = 20


class PDFTextExtractor(TextExtractor):
	"""Extracts text from a normal (non-scanned) text-based PDF, all pages in
	natural order, joined with paragraph breaks. Does not attempt OCR --
	a scanned PDF simply yields no meaningful text (see extract())."""

	def extract(self, data: bytes) -> Optional[str]:
		reader = PdfReader(io.BytesIO(data))  # raises on a genuinely malformed PDF

		page_texts = []
		for page in reader.pages:
			page_text = (page.extract_text() or "").strip()
			if page_text:
				page_texts.append(page_text)

		full_text = "\n\n".join(page_texts).strip()
		if len(full_text) < _MIN_MEANINGFUL_CHARS:
			return None
		return full_text
