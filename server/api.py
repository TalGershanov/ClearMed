import logging
import os
from contextlib import asynccontextmanager
from log_config import setup_logging

setup_logging()

from logic.medical_term_detector import build_ui_selection, detect_terms_with_explanations, get_term_details, init_trie
from logic.translator import ClinicalTranslator, simplify_text_with_openai
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Dict

logger = logging.getLogger("clearmed.api")
logger.info("--- Starting ClearMed Application ---")

@asynccontextmanager
async def lifespan(app: FastAPI):
	# build the medical term trie once, before the server starts accepting requests
	init_trie()
	yield

app = FastAPI(title="ClearMed API", lifespan=lifespan)

class AnalyseRequest(BaseModel):
	text: str

class TranslateRequest(BaseModel):
	text: str
	ui_selection: Dict[str, bool]

@app.post("/analyse")
async def analyse_text(request: AnalyseRequest):
	logger.info("analysing text for medical terms")
	result = detect_terms_with_explanations(request.text)
	ui_selection = build_ui_selection(result)
	return {"detected_terms": result, "ui_selection": ui_selection}

@app.post("/translate")
async def translate_text(request: TranslateRequest):
	logger.info("translating text based on ui selection")
	translator = ClinicalTranslator("short_explanation", get_term_details)
	approved_terms = translator.get_approved_terms(request.ui_selection)
	detected_terms = detect_terms_with_explanations(request.text)
	explanation_map = {
		term["main_term"]: term[translator.summary_string]
		for term in detected_terms
		if term["main_term"] in approved_terms and term.get(translator.summary_string)
	}
	final_text = simplify_text_with_openai(request.text, explanation_map)
	return {"translated_text": final_text, "explained_terms_list": approved_terms}

STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")

# to activate server run in terminal uvicorn server.api:app --reload
