import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from log_config import setup_logging

setup_logging()

from logic.medical_term_detector import build_ui_selection, detect_terms_with_explanations, get_term_details, init_trie
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
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
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
	await close_openmrs_client()

app = FastAPI(title="ClearMed API", lifespan=lifespan)

class AnalyseRequest(BaseModel):
	text: str

class TranslateRequest(BaseModel):
	text: str
	ui_selection: Dict[str, bool]

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
@app.post("/analyse")
@openmrs_app.post("/analyse")
async def analyse_text(request: AnalyseRequest):
	logger.info("analysing text for medical terms")
	result = detect_terms_with_explanations(request.text)
	ui_selection = build_ui_selection(result)
	return {"detected_terms": result, "ui_selection": ui_selection}

@app.post("/translate")
@openmrs_app.post("/translate")
async def translate_text(request: TranslateRequest):
	logger.info("translating text based on ui selection")
	translator = ClinicalTranslator("short_explanation", get_term_details)
	approved_terms = translator.get_approved_terms(request.ui_selection)
	terms_with_data = translator.fetch_explanations(approved_terms)
	final_text = translator.replace_terms(request.text, terms_with_data)
	return {"translated_text": final_text, "explained_terms_list": approved_terms}

@openmrs_app.get("/patients/{patient_uuid}", response_model=OpenMRSPatient)
async def get_openmrs_patient(patient_uuid: str):
	logger.info("fetching OpenMRS patient %s", patient_uuid)
	try:
		client = get_openmrs_client()
		return await client.get_patient(patient_uuid)
	except RuntimeError as e:
		raise HTTPException(status_code=503, detail=str(e))
	except OpenMRSAPIError as e:
		raise HTTPException(status_code=e.status_code, detail=e.message)

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
	try:
		client = get_openmrs_client()
		return await client.create_observation(payload)
	except RuntimeError as e:
		raise HTTPException(status_code=503, detail=str(e))
	except OpenMRSAPIError as e:
		raise HTTPException(status_code=e.status_code, detail=e.message)

@openmrs_app.get("/patients/{patient_uuid}/notes", response_model=NotesResponse)
async def get_patient_notes(patient_uuid: str):
	logger.info("listing OpenMRS clinical notes for patient %s", patient_uuid)
	if not OPENMRS_NOTE_CONCEPT_UUID:
		raise HTTPException(
			status_code=503,
			detail="OPENMRS_NOTE_CONCEPT_UUID is not configured; set it to your OpenMRS "
			"instance's concept UUID for clinical notes (see openmrs/README.md).",
		)
	try:
		client = get_openmrs_client()
		observations = await client.list_observations(patient_uuid, OPENMRS_NOTE_CONCEPT_UUID)
	except RuntimeError as e:
		raise HTTPException(status_code=503, detail=str(e))
	except OpenMRSAPIError as e:
		raise HTTPException(status_code=e.status_code, detail=e.message)
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
