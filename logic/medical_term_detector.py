import logging

from DAL import get_dal
from logic.medical_term_trie import build_trie_from_db

logger = logging.getLogger("clearmed.medical_term_detector")

# trie is built once from the DB at import time instead of on every request
trie = build_trie_from_db()

def get_term_details(main_term):
	# receives a main term name, e.g. A1C, and returns its details from the DB
	logger.debug(f"Looking up term details for '{main_term}'")
	dal = get_dal()
	return dal.get_term_by_name(main_term)

def detect_terms_with_explanations(text):
	# detects medical terms in the text and returns them together with explanations from the DB
	logger.info(f"Detecting medical terms in text of length {len(text)}")
	detected_terms = trie.find_terms(text)
	results = []
	for detected in detected_terms:
		details = get_term_details(detected["main_term"])
		if details:
			results.append({
				"matched_text": detected["matched_text"],
				"main_term": detected["main_term"],
				"start_word_index": detected["start_word_index"],
				"end_word_index": detected["end_word_index"],
				"short_explanation": details["short_explanation"],
				"simple_explanation": details["simple_explanation"],
				"categories": details["categories"],
				"synonyms": details["synonyms"]
			})
		else:
			logger.debug(f"Dropping detected term '{detected['main_term']}' - no DB details found")
	logger.info(f"Detected {len(results)} medical term(s) with explanations")
	return results
