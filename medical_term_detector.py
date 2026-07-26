import json
import logging

from db import get_connection
from medical_term_trie import build_trie_from_db

logger = logging.getLogger("clearmed.medical_term_detector")

# trie is built once from the DB at import time instead of on every request
trie = build_trie_from_db()

def get_term_details(main_term):
	# receives a main term name, e.g. A1C, and returns its details from the DB
	logger.debug(f"Looking up term details for '{main_term}'")
	connection = get_connection()
	cursor = connection.cursor()
	cursor.execute("""
		SELECT
			term,
			short_explanation,
			simple_explanation,
			synonyms,
			categories
		FROM medical_terms
		WHERE LOWER(term) = LOWER(?)
	""", (main_term,))
	row = cursor.fetchone()
	connection.close()
	if row is None:
		logger.debug(f"No DB entry found for term '{main_term}'")
		return None
	return {
		"term": row[0],
		# the short explanation we generated ourselves
		"short_explanation": row[1],
		# the full explanation from the source
		"simple_explanation": row[2],
		"synonyms": json.loads(row[3]),
		"categories": json.loads(row[4])
	}

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

if __name__ == "__main__":
	sample_text = """
	The patient has HbA1C above normal range.
	The doctor mentioned blood glucose and type 2 diabetes.
	"""
	results = detect_terms_with_explanations(sample_text)
	print("Detected medical terms:\n")
	for item in results:
		print("Matched text:", item["matched_text"])
		print("Main term:", item["main_term"])
		print("Explanation:", item["simple_explanation"])
		print("Categories:", item["categories"])
		print("-" * 50)
