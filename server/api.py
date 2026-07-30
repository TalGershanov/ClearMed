import logging
from contextlib import asynccontextmanager
from log_config import setup_logging

setup_logging()

from logic.medical_term_detector import detect_terms_with_explanations, get_term_details, init_trie
from logic.translator import ClinicalTranslator
from fastapi import FastAPI
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
	return {"detected_terms": result}

@app.post("/translate")
async def translate_text(request: TranslateRequest):
	logger.info("translating text based on ui selection")
	translator = ClinicalTranslator("short_explanation", get_term_details)
	approved_terms = translator.get_approved_terms(request.ui_selection)
	terms_with_data = translator.fetch_explanations(approved_terms)
	final_text = translator.replace_terms(request.text, terms_with_data)
	return {"translated_text": final_text, "explained_terms_list": approved_terms}

# to activate server run in terminal uvicorn server.api:app --reload
