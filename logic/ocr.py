import functools
import logging
import os

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

logger = logging.getLogger("clearmed.ocr")

GEMINI_MODEL = "gemini-flash-latest"

EXTRACTION_PROMPT = (
	"You are an OCR engine. Extract all visible text inside this photographed "
	"document accurately, preserving the original reading order and line breaks. "
	"Return only the extracted text, with no commentary, labels, or markdown formatting."
)

@functools.cache
def _get_genai_client() -> genai.Client:
	if not os.environ.get("GEMINI_API_KEY"):
		raise RuntimeError("GEMINI_API_KEY is not configured; set it in your .env file.")
	return genai.Client()

def extract_text_from_image(image_bytes: bytes, mime_type: str) -> str:
	client = _get_genai_client()
	response = client.models.generate_content(
		model=GEMINI_MODEL,
		contents=[
			types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
			EXTRACTION_PROMPT,
		],
	)
	if response.text is None:
		logger.warning("Gemini returned no extractable text for an uploaded image")
		raise ValueError("Could not read any text from this photo. Try a clearer picture.")
	return response.text
