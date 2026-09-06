import functools
import logging
import os

import deepl

logger = logging.getLogger("clearmed.server_init.translation_service")

# No load_dotenv() call here: this module's only importer (build_db.py)
# imports ai_services first, which already calls load_dotenv() at module
# load time before DEEPL_API_KEY is read below.

DEEPL_API_KEY = os.getenv("DEEPL_API_KEY")

@functools.cache
def _get_deepl_client() -> deepl.Translator:
	return deepl.Translator(DEEPL_API_KEY)

def translate_short_explanation(text, source_lang, target_lang):
	"""Translates an already-selected short_explanation via DeepL. Deterministic
	machine translation -- no LLM generation, no hallucination risk.

	source_lang/target_lang must already be exact DeepL language codes (e.g.
	"EN", "HE") -- callers are responsible for deriving the right DeepL code
	from an internal lowercase language_code (see config.get_deepl_target_lang).

	Returns None on missing input or a failed API call."""
	if not text or not text.strip():
		return None

	try:
		client = _get_deepl_client()
		result = client.translate_text(
			text,
			source_lang=source_lang,
			target_lang=target_lang,
		)
		translated = result.text.strip()
	except Exception:
		logger.warning("DeepL translation failed for %r (source_lang=%r, target_lang=%r)", text, source_lang, target_lang, exc_info=True)
		return None

	if not translated:
		logger.warning("DeepL translation returned empty content for %r", text)
		return None

	return translated
