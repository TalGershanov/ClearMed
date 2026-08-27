from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

GEMINI_MODEL = "gemini-flash-latest"

EXTRACTION_PROMPT = (
	"You are an OCR engine. Extract all visible text inside this photographed "
	"document accurately, preserving the original reading order and line breaks. "
	"Return only the extracted text, with no commentary, labels, or markdown formatting."
)

_genai_client = None

def _get_genai_client():
	global _genai_client
	if _genai_client is None:
		_genai_client = genai.Client()
	return _genai_client

def extract_text_from_image(image_bytes: bytes, mime_type: str) -> str:
	client = _get_genai_client()
	response = client.models.generate_content(
		model=GEMINI_MODEL,
		contents=[
			types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
			EXTRACTION_PROMPT,
		],
	)
	return response.text
