import re

class ClinicalTranslator:
    def __init__(self, db_dict_summery_string, db_get_explanation_func):
        self.summary_string = db_dict_summery_string
        self.db_search_function = db_get_explanation_func

    def get_approved_terms(self, ui_selection: dict) -> list:
        return [term for term, is_selected in ui_selection.items() if is_selected]

    def filter_terms(self, found_terms: list, terms_to_ignore: list) -> list:
        return [t for t in found_terms if t not in terms_to_ignore]

    def fetch_explanations(self, approved_terms) -> dict:
        terms_dict = {}
        for term in approved_terms:
            try:
                explained = self.db_search_function(term)
                if explained and (self.summary_string in explained):
                    terms_dict[term] = explained[self.summary_string]
            except Exception as e:
                print(f"Error fetching explanation for '{term}': {e}")

        return terms_dict

    def replace_terms(self, original_text: str, terms_dict: dict) -> str:
        if not terms_dict:
            return original_text

        translated_text = original_text

        # long to short to avoid switching blood vs blood pressure
        sorted_terms = sorted(terms_dict.keys(), key=len, reverse=True)

        for term in sorted_terms:
            explanation = terms_dict[term]

            pattern = re.compile(rf'\b({re.escape(term)})\b')
            replacement_string = f"{term} ({explanation})"

            translated_text = pattern.sub(replacement_string, translated_text)

        return translated_text