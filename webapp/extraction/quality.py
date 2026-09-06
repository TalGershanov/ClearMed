from typing import Optional

# Below this many *visible* characters, treat extraction as having found no
# meaningful text -- shared by every extractor (pypdf and OCR alike) so
# "extracted" always means the same thing regardless of which path produced
# the text. Not a medical-content check, purely a length/composition gate.
_MIN_MEANINGFUL_CHARS = 20


def is_meaningful_text(text: Optional[str]) -> bool:
	"""True only if text has enough real content to count as a successful
	extraction. Deliberately more than `len(text) > 0`: whitespace, control
	characters (stray newlines/form-feeds from a near-blank scanned page),
	and a handful of OCR/PDF artifacts must not be reported as success."""
	if not text:
		return False
	# str.isprintable() already excludes control characters like \n and \t
	# while keeping the ASCII space -- excluding isspace() too leaves only
	# real visible content to measure.
	visible = "".join(ch for ch in text if ch.isprintable() and not ch.isspace())
	return len(visible) >= _MIN_MEANINGFUL_CHARS
