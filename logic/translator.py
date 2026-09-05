import logging

logger = logging.getLogger("clearmed.translator")


def apply_translations(text, detected_terms, ui_selection, explanation_field):
	"""Splice an explanation after each user-approved detected term's own
	span -- `detected_terms` is exactly detect_terms_with_explanations()'s
	output, so every span (Hebrew-prefixed tokens, aliases, synonyms) is
	trusted as-is: no independent re-search of `text`, and no
	overlap-resolution needed, since the detectors already return
	non-overlapping spans ordered by position. Returns (translated_text,
	explained_terms_list); the latter is deduplicated by term_name in
	first-seen order, since the same concept can be detected at more than
	one span in the text."""
	approved = [
		term for term in detected_terms
		if ui_selection.get(term["main_term"], False) and term.get(explanation_field)
	]
	translated_text = text
	for term in sorted(approved, key=lambda t: t["start"], reverse=True):
		end = term["end"]
		translated_text = f"{translated_text[:end]} ({term[explanation_field]}){translated_text[end:]}"
	explained_terms_list, seen = [], set()
	for term in approved:
		if term["term_name"] not in seen:
			seen.add(term["term_name"])
			explained_terms_list.append(term["term_name"])
	logger.info(f"Spliced {len(approved)} approved term occurrence(s) into text ({len(explained_terms_list)} unique).")
	return translated_text, explained_terms_list
