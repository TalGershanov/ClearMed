import logging

from DAL import get_dal
from logic.medical_term_trie import build_trie_from_db
from logic.term_detectors import DetectorFactory

logger = logging.getLogger("clearmed.medical_term_detector")

# built once by the server at startup via init_trie()
trie = None

def init_trie():
	global trie
	trie = build_trie_from_db()

def get_term_details(main_term):
	# receives a main term name, e.g. A1C, and returns its details from the DB
	logger.debug(f"Looking up term details for '{main_term}'")
	dal = get_dal()
	return dal.get_term_by_name(main_term)

def detect_terms_with_explanations(text, language_code="en"):
	# detects medical terms in the text and returns them together with explanations from the DB
	logger.info(f"Detecting medical terms in text of length {len(text)} (language_code={language_code})")
	detector = DetectorFactory.get_detector(language_code)
	detected_terms = detector.detect_terms(text, trie)
	results = []
	for detected in detected_terms:
		details = get_term_details(detected["main_term"])
		if details:
			results.append({
				"matched_text": detected["matched_text"],
				"main_term": detected["main_term"],
				"start": detected["start"],
				"end": detected["end"],
				"short_explanation": details["short_explanation"],
				"simple_explanation": details["simple_explanation"],
				"categories": details["categories"],
				"synonyms": details["synonyms"]
			})
		else:
			logger.debug(f"Dropping detected term '{detected['main_term']}' - no DB details found")
	logger.info(f"Detected {len(results)} medical term(s) with explanations")
	return results

def build_ui_selection(detected_terms):
	# builds a default ui_selection dict (all true) from a detect_terms_with_explanations() result
	return {term["main_term"]: True for term in detected_terms}
