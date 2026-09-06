import logging
import os
import threading

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("clearmed.document_translation")

TRANSLATE_URL = "https://translation.googleapis.com/language/translate/v2"
LANGUAGES_URL = "https://translation.googleapis.com/language/translate/v2/languages"

# The document's legal disclaimer is fixed, legally-sensitive boilerplate --
# a human-reviewed translation beats an unreviewed live API call on every
# page view. Seeded only for languages we expect real use of; any other
# language_code falls back to the English text below, which is always the
# same verified string, never a hallucination risk, just untranslated.
_ENGLISH_DISCLAIMER = (
	"Term explanations are sourced from MedlinePlus, a service of the U.S. National Library of "
	"Medicine (NIH), and were shortened with the help of AI for readability. This "
	"document is not a substitute for professional medical advice."
)
_STATIC_DISCLAIMERS: dict[str, str] = {
	"en": _ENGLISH_DISCLAIMER,
	"es": (
		"Las explicaciones de los términos provienen de MedlinePlus, un servicio de la Biblioteca "
		"Nacional de Medicina de los Estados Unidos (NIH), y se han abreviado con la ayuda de "
		"inteligencia artificial para facilitar su lectura. Este documento no sustituye el consejo "
		"médico profesional."
	),
	"am": (
		"የቃላት ማብራሪያዎች የተገኙት ከዩኤስ ብሔራዊ የሕክምና ቤተ መጻሕፍት (NIH) አገልግሎት ከሚገኘው MedlinePlus ሲሆን፣ ለማንበብ ቀላል "
		"በሆነ መንገድ በAI እገዛ አጠር ተደርገው ነበር። ይህ ሰነድ ለሙያዊ የሕክምና ምክር ምትክ አይደለም።"
	),
}

_languages_cache: list[dict] | None = None
_languages_cache_lock = threading.Lock()


class TranslationAPIError(Exception):
	pass


def _get_api_key() -> str:
	api_key = os.environ.get("GOOGLE_TRANSLATION_API_KEY")
	if not api_key:
		raise RuntimeError("GOOGLE_TRANSLATION_API_KEY is not configured; set it in your .env file.")
	return api_key


def get_disclaimer(language_code: str) -> str:
	return _STATIC_DISCLAIMERS.get(language_code, _ENGLISH_DISCLAIMER)


def translate_document_fields(explanation_text: str, explained_terms_list: list[str], target_language_code: str) -> dict:
	"""Translates the explanation paragraph and every explained-term string
	in a single batched request. Returns
	{"explanation_text": str, "explained_terms_list": list[str]}.
	Never touches clearmed.db / DAL/db.py -- operates purely on already
	AI/verified-generated text, never on raw medical terms."""
	api_key = _get_api_key()
	texts = [explanation_text, *explained_terms_list]
	logger.info(f"translating document fields to {target_language_code!r} ({len(texts)} segment(s))")
	request_body = {"q": texts, "target": target_language_code, "format": "text"}
	response = httpx.post(TRANSLATE_URL, params={"key": api_key}, json=request_body, timeout=30)
	try:
		response.raise_for_status()
	except httpx.HTTPStatusError as e:
		# re-raise without the request/response reprs, which httpx includes
		# verbatim in the default message -- the request carries the key in
		# its query string.
		logger.error(f"Google Translate request failed with status {response.status_code}")
		raise TranslationAPIError(f"Translation request failed with status {response.status_code}") from e
	data = response.json()
	try:
		translations = data["data"]["translations"]
	except (KeyError, TypeError) as e:
		raise TranslationAPIError("Unexpected response shape from Google Translate") from e
	translated_texts = [t["translatedText"] for t in translations]
	return {
		"explanation_text": translated_texts[0],
		"explained_terms_list": translated_texts[1:],
	}


def list_supported_languages(display_language_code: str = "en") -> list[dict]:
	"""Returns [{"code": "es", "name": "Spanish"}, ...], cached in-process
	after the first call -- language lists change essentially never, and a
	process restart is an adequate refresh mechanism at this scale."""
	global _languages_cache
	if _languages_cache is not None:
		return _languages_cache
	with _languages_cache_lock:
		if _languages_cache is not None:
			return _languages_cache
		api_key = _get_api_key()
		logger.info("fetching supported languages from Google Translate")
		response = httpx.get(
			LANGUAGES_URL,
			params={"key": api_key, "target": display_language_code},
			timeout=30,
		)
		try:
			response.raise_for_status()
		except httpx.HTTPStatusError as e:
			logger.error(f"Google Translate languages request failed with status {response.status_code}")
			raise TranslationAPIError(f"Languages request failed with status {response.status_code}") from e
		data = response.json()
		try:
			languages = data["data"]["languages"]
		except (KeyError, TypeError) as e:
			raise TranslationAPIError("Unexpected response shape from Google Translate") from e
		_languages_cache = [{"code": lang["language"], "name": lang["name"]} for lang in languages]
		return _languages_cache
