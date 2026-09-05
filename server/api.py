import asyncio
import functools
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from google.genai import errors as genai_errors
from log_config import setup_logging
from logic.medical_term_detector import build_ui_selection, detect_terms_with_explanations, get_term_details, init_trie
from logic.ocr import extract_text_from_image
from logic.term_detectors.hebrew import detect_language_code
from logic.translator import ClinicalTranslator
from openmrs.client import OpenMRSAPIError, close_openmrs_client, get_openmrs_client
from openmrs.config import OPENMRS_NOTE_CONCEPT_UUID, OPENMRS_ORIGIN
from openmrs.schemas import (
	NoteSummary,
	NotesResponse,
	ObservationCreateRequest,
	OpenMRSObservation,
	OpenMRSPatient,
)
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Dict

setup_logging()

logger = logging.getLogger("clearmed.api")
logger.info("--- Starting ClearMed Application ---")

@asynccontextmanager
async def lifespan(_app: FastAPI):
	# build the medical term trie once, before the server starts accepting requests
	init_trie()
	yield
	await close_openmrs_client()

app = FastAPI(title="ClearMed API", lifespan=lifespan)

class AnalyseRequest(BaseModel):
	text: str
	language_code: str = "en"

class TranslateRequest(BaseModel):
	text: str
	ui_selection: Dict[str, bool]
	language_code: str = "en"

# Mounted as its own sub-app (not routes on `app` directly) so the CORS
# allowlist below applies only to /openmrs/*, not to every route on `app`
# (the static mount). These endpoints let a browser read/write patient-
# adjacent data, so only the trusted OpenMRS deployment (plus the local
# OpenMRS dev-shell) may call them cross-origin -- a closed allowlist,
# never a wildcard.
openmrs_app = FastAPI(title="ClearMed OpenMRS Integration")
openmrs_app.add_middleware(
	CORSMiddleware,
	allow_origins=[OPENMRS_ORIGIN, "http://localhost:8080"],
	allow_methods=["GET", "POST"],
	allow_headers=["Content-Type"],
)

# /analyse and /translate are registered on BOTH `app` (for the same-origin
# static/ wizard, at their original top-level paths) and `openmrs_app` (so
# the OpenMRS widget can call them cross-origin as /openmrs/analyse and
# /openmrs/translate, inheriting openmrs_app's CORS scoping above) -- the
# same handler function is just registered twice, no logic duplicated.
MAX_OCR_IMAGE_BYTES = 15 * 1024 * 1024  # stays under Gemini's inline-request ceiling once base64-encoded

@app.post("/ocr")
async def ocr_image(image: UploadFile = File(...)):
	logger.info("extracting text from uploaded image via Gemini")
	if not image.content_type or not image.content_type.startswith("image/"):
		raise HTTPException(status_code=400, detail="Uploaded file must be an image.")
	image_bytes = await image.read()
	if len(image_bytes) > MAX_OCR_IMAGE_BYTES:
		raise HTTPException(status_code=413, detail="Image is too large; please use a smaller photo.")
	try:
		# generate_content is a blocking call -- run it off the event loop so a
		# slow Gemini round-trip doesn't stall every other concurrent request.
		text = await asyncio.to_thread(extract_text_from_image, image_bytes, image.content_type)
	except RuntimeError as e:
		raise HTTPException(status_code=503, detail=str(e))
	except ValueError as e:
		raise HTTPException(status_code=422, detail=str(e))
	except genai_errors.APIError as e:
		logger.error("Gemini OCR request failed: %s", e)
		raise HTTPException(status_code=502, detail="OCR service is temporarily unavailable. Please try again.")
	return {"text": text}

@app.post("/analyse")
@openmrs_app.post("/analyse")
async def analyse_text(request: AnalyseRequest):
	effective_language_code = detect_language_code(request.text)
	logger.info("analysing text for medical terms (language_code=%s)", effective_language_code)
	try:
		result = detect_terms_with_explanations(request.text, effective_language_code)
	except ValueError as e:
		raise HTTPException(status_code=400, detail=str(e))
	ui_selection = build_ui_selection(result)
	return {"detected_terms": result, "ui_selection": ui_selection, "language_code": effective_language_code}

@app.post("/translate")
@openmrs_app.post("/translate")
async def translate_text(request: TranslateRequest):
	effective_language_code = detect_language_code(request.text)
	logger.info("translating text based on ui selection (language_code=%s)", effective_language_code)
	# short_explanation is English-only even for Hebrew concepts (the infomed
	# scraper never translated it -- see server_init/hebrew_terms.py); the
	# genuine scraped Hebrew explanation lives in simple_explanation instead.
	explanation_field = "simple_explanation" if effective_language_code == "he" else "short_explanation"
	translator = ClinicalTranslator(explanation_field, functools.partial(get_term_details, language_code=effective_language_code))
	approved_terms = translator.get_approved_terms(request.ui_selection)
	terms_with_data = translator.fetch_explanations(approved_terms)
	final_text = translator.replace_terms(request.text, terms_with_data)
	return {"translated_text": final_text, "explained_terms_list": list(terms_with_data.keys())}

async def _call_openmrs(action):
	"""Runs `action(client)` against the shared OpenMRS client, mapping client
	failures to the HTTPException the calling endpoint should raise."""
	try:
		client = get_openmrs_client()
		return await action(client)
	except RuntimeError as e:
		raise HTTPException(status_code=503, detail=str(e))
	except OpenMRSAPIError as e:
		raise HTTPException(status_code=e.status_code, detail=e.message)

@openmrs_app.get("/patients/{patient_uuid}", response_model=OpenMRSPatient)
async def get_openmrs_patient(patient_uuid: str):
	logger.info("fetching OpenMRS patient %s", patient_uuid)
	return await _call_openmrs(lambda client: client.get_patient(patient_uuid))

@openmrs_app.post("/observations", response_model=OpenMRSObservation)
async def create_openmrs_observation(request: ObservationCreateRequest):
	logger.info("creating OpenMRS observation for patient %s", request.patient_uuid)
	# a Patient's UUID is the same as its underlying Person's UUID in OpenMRS,
	# so it can be passed directly as the obs resource's "person" field
	obs_datetime = request.obs_datetime or datetime.now(timezone.utc)
	if obs_datetime.tzinfo is None:
		# a naive timestamp has no timezone to convert from -- treat it as
		# already being UTC rather than assuming the server's local timezone
		obs_datetime = obs_datetime.replace(tzinfo=timezone.utc)
	else:
		obs_datetime = obs_datetime.astimezone(timezone.utc)
	# OpenMRS expects ISO8601 with millisecond precision and a literal "Z",
	# e.g. yyyy-MM-dd'T'HH:mm:ss.SSSZ -- plain isoformat() gives "+00:00" and
	# microsecond precision instead.
	formatted_obs_datetime = obs_datetime.isoformat(timespec="milliseconds").replace("+00:00", "Z")
	payload = {
		"person": request.patient_uuid,
		"concept": request.concept_uuid,
		"value": request.value,
		"obsDatetime": formatted_obs_datetime,
	}
	if request.encounter_uuid:
		payload["encounter"] = request.encounter_uuid
	return await _call_openmrs(lambda client: client.create_observation(payload))

@openmrs_app.get("/patients/{patient_uuid}/notes", response_model=NotesResponse)
async def get_patient_notes(patient_uuid: str):
	logger.info("listing OpenMRS clinical notes for patient %s", patient_uuid)
	if not OPENMRS_NOTE_CONCEPT_UUID:
		raise HTTPException(
			status_code=503,
			detail="OPENMRS_NOTE_CONCEPT_UUID is not configured; set it to your OpenMRS "
			"instance's concept UUID for clinical notes (see openmrs/README.md).",
		)
	observations = await _call_openmrs(lambda client: client.list_observations(patient_uuid, OPENMRS_NOTE_CONCEPT_UUID))
	notes = []
	for obs in observations:
		value = obs.get("value")
		if isinstance(value, dict):
			note_text = value.get("display", "")
		elif value is None:
			note_text = ""
		else:
			note_text = str(value)
		notes.append(NoteSummary(obs_uuid=obs["uuid"], obs_datetime=obs.get("obsDatetime"), note_text=note_text))
	return NotesResponse(notes=notes)

app.mount("/openmrs", openmrs_app)

STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")

# to activate server run in terminal uvicorn server.api:app --reload
