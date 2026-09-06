import asyncio
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import httpx
from DAL import shares_db
from log_config import setup_logging
from logic.document_shares import ShareNotFoundError, create_shared_document, get_shared_document, translate_shared_document
from logic.document_translation import TranslationAPIError, get_disclaimer, list_supported_languages, translate_document_fields
from logic.medical_term_detector import build_ui_selection, detect_terms_with_explanations, init_trie
from logic.ocr import VisionAPIError, extract_text_from_image
from logic.term_detectors.hebrew import detect_language_code
from logic.translator import apply_translations
from openmrs.client import OpenMRSAPIError, close_openmrs_client, get_openmrs_client
from openmrs.config import OPENMRS_NOTE_CONCEPT_UUID, OPENMRS_ORIGIN
from openmrs.schemas import (
	NoteSummary,
	NotesResponse,
	ObservationCreateRequest,
	OpenMRSObservation,
	OpenMRSPatient,
)
from webapp.auth.router import router as auth_router
from webapp.core import config as webapp_config
from webapp.documents.router import router as documents_router
from webapp.folders.router import router as folders_router
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Dict, List

setup_logging()

logger = logging.getLogger("clearmed.api")
logger.info("--- Starting ClearMed Application ---")

@asynccontextmanager
async def lifespan(_app: FastAPI):
	# build the medical term trie once, before the server starts accepting requests
	init_trie()
	# create shares.db's table if it doesn't exist yet -- separate file from
	# DB_FILE/clearmed.db, see DAL/shares_db.py
	shares_db.init_schema()
	yield
	await close_openmrs_client()

app = FastAPI(title="ClearMed API", lifespan=lifespan)

# --- Patient app (webapp/) ---------------------------------------------------
# A separate application/user-data system (auth, user-owned folders and
# documents) living alongside the ClearMed medical-term pipeline above -- its
# own PostgreSQL database, its own routers. See webapp/ for details; nothing
# here touches logic/, DAL/, or clearmed.db.
#
# allow_origins is the union of the patient-app frontend's origin and
# openmrs_app's own origins (below) -- NOT because they share a CORS policy,
# but because Starlette's CORSMiddleware.preflight_response rejects an
# unrecognized origin with a 400 *before* the request ever reaches an inner
# mounted app. Adding a narrower CORSMiddleware here that only knew about the
# patient-app origin would 400 every OpenMRS-origin preflight at this outer
# layer, never letting it reach openmrs_app's own (correctly-scoped)
# CORSMiddleware below. openmrs_app's middleware is left untouched; this is
# purely an outer-layer widening so both origins' preflights get past this
# layer, each still gated by its own middleware after that.
app.add_middleware(
	CORSMiddleware,
	allow_origins=list(dict.fromkeys(webapp_config.CORS_ALLOWED_ORIGINS + [OPENMRS_ORIGIN, "http://localhost:8080"])),
	allow_credentials=True,
	allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
	allow_headers=["Content-Type"],
)
app.include_router(auth_router)
app.include_router(folders_router)
app.include_router(documents_router)
# --- end patient app ----------------------------------------------------------

class AnalyseRequest(BaseModel):
	text: str
	language_code: str = "en"

class TranslateRequest(BaseModel):
	text: str
	ui_selection: Dict[str, bool]
	language_code: str = "en"

class ShareCreateRequest(BaseModel):
	explanation_text: str
	explained_terms_list: List[str]

class ShareTranslateRequest(BaseModel):
	target_language_code: str

class DocumentTranslateRequest(BaseModel):
	explanation_text: str
	explained_terms_list: List[str]
	target_language_code: str

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
MAX_OCR_IMAGE_BYTES = 15 * 1024 * 1024  # stays under Cloud Vision's 20MB request-payload ceiling once base64-encoded

@app.post("/ocr")
async def ocr_image(image: UploadFile = File(...)):
	logger.info("extracting text from uploaded image via Cloud Vision")
	if not image.content_type or not image.content_type.startswith("image/"):
		raise HTTPException(status_code=400, detail="Uploaded file must be an image.")
	image_bytes = await image.read()
	if len(image_bytes) > MAX_OCR_IMAGE_BYTES:
		raise HTTPException(status_code=413, detail="Image is too large; please use a smaller photo.")
	try:
		# the Vision REST call is blocking -- run it off the event loop so a
		# slow round-trip doesn't stall every other concurrent request.
		text = await asyncio.to_thread(extract_text_from_image, image_bytes, image.content_type)
	except RuntimeError as e:
		raise HTTPException(status_code=503, detail=str(e))
	except ValueError as e:
		raise HTTPException(status_code=422, detail=str(e))
	except (httpx.HTTPError, VisionAPIError) as e:
		logger.error("Cloud Vision OCR request failed: %s", e)
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
	# detect_terms_with_explanations() returns one entry per text occurrence
	# (needed by /translate's per-span splicing, which re-detects independently
	# below) -- dedup by main_term (concept_id) here so the "select terms" list
	# this endpoint feeds shows each concept once, first-seen order.
	seen_main_terms = set()
	unique_terms = []
	for term in result:
		if term["main_term"] not in seen_main_terms:
			seen_main_terms.add(term["main_term"])
			unique_terms.append(term)
	ui_selection = build_ui_selection(unique_terms)
	return {"detected_terms": unique_terms, "ui_selection": ui_selection, "language_code": effective_language_code}

@app.post("/translate")
@openmrs_app.post("/translate")
async def translate_text(request: TranslateRequest):
	effective_language_code = detect_language_code(request.text)
	logger.info("translating text based on ui selection (language_code=%s)", effective_language_code)
	# short_explanation is now AI-translated per-language inline at DB-build
	# time (see server_init/build_db.py::_populate_secondary_language),
	# so the same field works for every language.
	explanation_field = "short_explanation"
	try:
		detected_terms = detect_terms_with_explanations(request.text, effective_language_code)
	except ValueError as e:
		raise HTTPException(status_code=400, detail=str(e))
	final_text, explained_terms_list = apply_translations(request.text, detected_terms, request.ui_selection, explanation_field)
	return {"translated_text": final_text, "explained_terms_list": explained_terms_list}

# Only the OpenMRS widget (cross-origin) creates shares -- the static wizard
# never does, so this only needs registering on openmrs_app, not dual-
# registered like /analyse and /translate above.
@openmrs_app.post("/documents/share")
async def create_document_share(request: ShareCreateRequest):
	logger.info("creating document share")
	share_id = create_shared_document(request.explanation_text, request.explained_terms_list)
	return {"uuid": share_id}

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

# --- Same-origin document translation/sharing (static wizard + mobile QR page) --
# All same-origin (called by static/script.js and static/mobile-doc.js, both
# served from this same app), so no CORS scoping needed -- unlike the
# create-share endpoint above, which is the one call the OpenMRS widget makes
# cross-origin. Must be registered before the "/" StaticFiles mount below:
# Starlette tries explicit path operations before falling through to a mount,
# but only if they're registered earlier than the mount.

@app.get("/shares/{share_id}")
async def get_document_share(share_id: str):
	try:
		share = get_shared_document(share_id)
	except ShareNotFoundError:
		raise HTTPException(status_code=404, detail="This document link is no longer valid.")
	return {
		"explanation_text": share["explanation_text"],
		"explained_terms_list": share["explained_terms_list"],
		"disclaimer": get_disclaimer("en"),
	}

@app.post("/shares/{share_id}/translate")
async def translate_document_share(share_id: str, request: ShareTranslateRequest):
	logger.info("translating shared document %s to %s", share_id, request.target_language_code)
	try:
		# translate_shared_document makes a blocking Google Translate REST
		# call -- run it off the event loop, same as /ocr does for Vision.
		return await asyncio.to_thread(translate_shared_document, share_id, request.target_language_code)
	except ShareNotFoundError:
		raise HTTPException(status_code=404, detail="This document link is no longer valid.")
	except TranslationAPIError as e:
		logger.error("translation failed for share %s: %s", share_id, e)
		raise HTTPException(status_code=502, detail="Translation service is temporarily unavailable. Please try again.")

@app.get("/languages")
async def get_languages():
	try:
		return await asyncio.to_thread(list_supported_languages)
	except TranslationAPIError as e:
		logger.error("failed to fetch supported languages: %s", e)
		raise HTTPException(status_code=502, detail="Translation service is temporarily unavailable. Please try again.")

@app.post("/translate-document")
async def translate_document(request: DocumentTranslateRequest):
	logger.info("translating document (stateless) to %s", request.target_language_code)
	try:
		result = await asyncio.to_thread(
			translate_document_fields, request.explanation_text, request.explained_terms_list, request.target_language_code
		)
	except TranslationAPIError as e:
		logger.error("translation failed: %s", e)
		raise HTTPException(status_code=502, detail="Translation service is temporarily unavailable. Please try again.")
	result["disclaimer"] = get_disclaimer(request.target_language_code)
	return result

STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")

@app.get("/doc/{uuid}")
async def mobile_document_page(uuid: str):
	# The uuid itself is read client-side from location.pathname by
	# static/mobile-doc.js, which then fetches GET /shares/{uuid} -- this
	# route only ever serves the same static page shell for any uuid shape.
	return FileResponse(os.path.join(STATIC_DIR, "mobile-doc.html"))

app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")

# to activate server run in terminal uvicorn server.api:app --reload
