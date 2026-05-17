import logging
from log_config import setup_logging
from medical_term_detector import detect_terms_with_explanations #yuval
from translator import ClinicalTranslator
from fastapi import FastAPI
from pydantic import BaseModel
from typing import List , Dict


logger = logging.getLogger("clearmed.api")
logger.info("--- Starting ClearMed Application ---")
original_text = "The patient has HbA1C above normal range and type 2 diabetes." # later - import from front
#    logger.debug(f"Received text length: {len(original_text)} chars")


app = FastAPI(title="ClearMed API")

class AnalyseRequest(BaseModel):
    text: str
class TranslateRequest(BaseModel):
    text: str
    ui_selection: Dict[str, bool]

@app.post("/analyse")
async def analyse_text(request: AnalyseRequest):
    logger.info("analysing text for medical terms")
    result = detect_terms_with_explanations(request.text)
    return {"detected_terms": [item["matched_text"] for item in result]}

@app.post("/translate")
async def translate_text(request: TranslateRequest):
    logger.info("translating text abased on ui selection")
    def db_func(term):
        return # need to fill in here connection with yuval, maybe translator instance is altered
    translator = ClinicalTranslator("short_explanation", db_func)
    approved_terms = translator.get_approved_terms(request.ui_selection)
    terms_with_data = translator.fetch_explanations(approved_terms)
    final_text = translator.replace_terms(request.text, terms_with_data)
    return {"translated_text": final_text, "explained_terms_list": approved_terms}

#to activate server run in terminal uvicorn app:app --reload

