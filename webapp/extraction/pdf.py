import io
from typing import Optional

from pypdf import PdfReader

from webapp.extraction.base import TextExtractor
from webapp.extraction.quality import is_meaningful_text


class PDFTextExtractor(TextExtractor):
	"""Extracts text from a normal (non-scanned) text-based PDF, all pages in
	natural order, joined with paragraph breaks. Does not attempt OCR --
	a scanned PDF simply yields no meaningful text (see extract()); the OCR
	fallback for that case lives one level up, in webapp/extraction/__init__.py,
	so this class stays a pure pypdf extractor."""

	def extract(self, data: bytes) -> Optional[str]:
		reader = PdfReader(io.BytesIO(data))  # raises on a genuinely malformed PDF

		page_texts = []
		for page in reader.pages:
			page_text = (page.extract_text() or "").strip()
			if page_text:
				page_texts.append(page_text)

		full_text = "\n\n".join(page_texts).strip()
		return full_text if is_meaningful_text(full_text) else None
