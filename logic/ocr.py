import base64
import logging
import os

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("clearmed.ocr")

VISION_ANNOTATE_URL = "https://vision.googleapis.com/v1/images:annotate"

class VisionAPIError(Exception):
	pass

def _get_api_key() -> str:
	api_key = os.environ.get("GOOGLE_CLOUD_VISION_API_KEY")
	if not api_key:
		raise RuntimeError("GOOGLE_CLOUD_VISION_API_KEY is not configured; set it in your .env file.")
	return api_key

def extract_text_from_image(image_bytes: bytes, mime_type: str) -> str:
	api_key = _get_api_key()
	request_body = {
		"requests": [
			{
				"image": {"content": base64.b64encode(image_bytes).decode("ascii")},
				"features": [{"type": "DOCUMENT_TEXT_DETECTION"}],
			}
		]
	}
	response = httpx.post(
		VISION_ANNOTATE_URL,
		headers={"X-Goog-Api-Key": api_key},
		json=request_body,
		timeout=30,
	)
	try:
		response.raise_for_status()
	except httpx.HTTPStatusError as e:
		# re-raise without the request/response reprs, which httpx includes verbatim
		# in the default message -- the request carries the key in its headers.
		raise VisionAPIError(f"Cloud Vision request failed with status {response.status_code}") from e
	result = response.json()["responses"][0]
	if "error" in result:
		raise VisionAPIError(result["error"].get("message", "Unknown Cloud Vision error"))
	text = result.get("fullTextAnnotation", {}).get("text")
	if not text:
		logger.warning("Cloud Vision returned no extractable text for an uploaded image")
		raise ValueError("Could not read any text from this photo. Try a clearer picture.")
	return text
