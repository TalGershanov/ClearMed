import re
import logging

logger = logging.getLogger("clearmed.translator")

class ClinicalTranslator:
	def __init__(self, db_dict_summery_string, db_get_explanation_func):
		self.summary_string = db_dict_summery_string
		self.db_search_function = db_get_explanation_func
		logger.debug("ClinicalTranslator initialized.")

	def get_approved_terms(self, ui_selection: dict) -> list:
		approved = [term for term, is_selected in ui_selection.items() if is_selected]
		logger.debug(f"Approved {len(approved)} terms from UI selection.")
		return approved

	def fetch_explanations(self, approved_terms) -> dict:
		terms_dict = {}
		for term in approved_terms:
			try: #here - already have dict from main so use that instead of yuvals func- so change class to recieve the dict OR just the term list and then use yuvals func
				explained = self.db_search_function(term)
				if explained and (self.summary_string in explained):
					terms_dict[term] = explained[self.summary_string]
			except Exception as e:
				logger.exception(f"Error fetching explanation for '{term}': {e}")
		logger.info(f"Successfully fetched {len(terms_dict)} explanations from DB.")
		return terms_dict

	def replace_terms(self, original_text: str, terms_dict: dict) -> str: #add here the translated term so we know what we translated
		if not terms_dict:
			logger.warning("No terms dictionary provided for replacement.")
			return original_text
		# Match every term against the original text only -- matching against
		# the text as it's progressively substituted would let one term's
		# explanation (which may itself mention another selected term) get
		# matched and wrapped again, producing nested "(...(...).)" parens.
		# long to short to avoid switching blood vs blood pressure
		sorted_terms = sorted(terms_dict.keys(), key=len, reverse=True)
		matches = []
		for term in sorted_terms:
			pattern = re.compile(rf'\b({re.escape(term)})\b', re.IGNORECASE)
			for m in pattern.finditer(original_text):
				matches.append((m.start(), m.end(), terms_dict[term]))
		matches.sort(key=lambda span: span[0])
		non_overlapping = []
		last_end = -1
		for start, end, explanation in matches:
			if start >= last_end:
				non_overlapping.append((start, end, explanation))
				last_end = end
		translated_text = original_text
		for start, end, explanation in sorted(non_overlapping, reverse=True):
			translated_text = f"{translated_text[:end]} ({explanation}){translated_text[end:]}"
		logger.info("Finished translating terms in text.")
		return translated_text
