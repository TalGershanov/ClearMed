import logging
from log_config import setup_logging
from medical_detector import detect_terms_with_explanations #yuval
from translator import ClinicalTranslator

def main():
    logger = logging.getLogger("clearmed.main")
    logger.info("--- Starting ClearMed Application ---")
    original_text = "The patient has HbA1C above normal range and type 2 diabetes." # later - import from front
    logger.debug(f"Received text length: {len(original_text)} chars")

    db_search_list_of_dicts = detect_terms_with_explanations(original_text)
    logger.info(f"Detector found {len(db_search_list_of_dicts)} terms.")

  # from list of dicts to dict
    def get_explanation_from_partner_results(term):
        for item in db_search_list_of_dicts:
            if item["matched_text"] == term:
                return item # single dict
        return None


    translator = ClinicalTranslator(
        db_dict_summery_string="simple_explanation",
        db_get_explanation_func=get_explanation_from_partner_results
    )

    found_terms = [item["matched_text"] for item in db_search_list_of_dicts]

    # this is an example - later - connection to front
    ui_selection = {term: True for term in found_terms}

    # translation flow
    logger.info("Starting translation flow...")
    approved_terms = translator.get_approved_terms(ui_selection)
    terms_dict = translator.fetch_explanations(approved_terms)
    final_text = translator.replace_terms(original_text, terms_dict)


    print("--- Original Text ---")
    print(original_text)
    print("\n--- ClearMed Output ---")
    print(final_text)

    logger.info("--- ClearMed Application Finished Successfully ---")

if __name__ == "__main__":
    main()