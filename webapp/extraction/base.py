from abc import ABC, abstractmethod
from typing import Optional


class TextExtractor(ABC):
	"""Extracts human-readable text from a document's raw bytes. Never
	interprets, simplifies, translates, or otherwise medically modifies the
	content -- it only recovers the text that's already there.

	Returns None when parsing succeeds but yields no meaningful text (e.g. a
	scanned PDF with no text layer) -- callers must not treat that the same
	as a hard failure. Raises on a genuine parsing error (corrupted/
	malformed file); callers are responsible for catching that and recording
	it as a failure rather than letting it abort the surrounding request."""

	@abstractmethod
	def extract(self, data: bytes) -> Optional[str]:
		...
