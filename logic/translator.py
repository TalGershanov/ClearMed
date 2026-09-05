import logging

from dotenv import load_dotenv
from openai import OpenAI

logger = logging.getLogger("clearmed.translator")

load_dotenv()

OPENAI_MODEL = "gpt-4o-mini"

_openai_client = None

def _get_openai_client():
	global _openai_client
	if _openai_client is None:
		_openai_client = OpenAI()
	return _openai_client

# This is the ONLY place in the runtime pipeline that generates new wording.
# It must never introduce medical facts, diagnoses, warnings, or treatment
# advice beyond what is already present in original_text or explanation_map --
# it rewrites for clarity, it does not add medical knowledge. V7 (selected
# offline, at DB-build time -- see server_init/create_clearmed_db.py) remains
# the sole source of which explanation text is "approved" for each term; this
# prompt only controls how that already-approved wording gets woven into the
# patient-facing paragraph.
_REWRITE_SYSTEM_PROMPT = (
	"You rewrite a medical text so a patient can understand it, using ONLY the "
	"information given to you. You are a language rewriter, not a medical "
	"knowledge source.\n\n"
	"You will receive the original medical text and explanation_map: a list of "
	"medical terms with an approved explanation for each term (these "
	"explanations were selected from a verified medical source; do not doubt "
	"or correct them).\n\n"
	"*** CRITICAL RULE -- READ THIS FIRST ***\n"
	"Treat explanation_map as the complete and exclusive set of medical "
	"knowledge you are authorized to add to the text. Do not use your own "
	"medical knowledge to explain, define, expand, interpret, or simplify any "
	"medical term or concept that is absent from explanation_map. This applies "
	"equally to two situations, and you must treat them identically:\n"
	"  (a) a term that appears in the text and even one that the detection "
	"system found, but that is NOT included in explanation_map for this "
	"request;\n"
	"  (b) a medical term or concept in the text that was never detected at "
	"all.\n"
	"An unselected term must be treated exactly like an unknown term: preserve "
	"it rather than explain it. You are never permitted to fill either gap "
	"with your own medical knowledge, no matter how well-known, simple, or "
	"obviously correct that knowledge is. If explanation_map does not contain "
	"a term, that term is off-limits to you -- leave its wording exactly as it "
	"appears in the original text (correcting only surrounding grammar strictly "
	"required to keep the sentence readable when an approved explanation is "
	"inserted elsewhere in the same sentence -- never as a reason to touch the "
	"unauthorized term's own wording).\n\n"
	"Rules:\n"
	"1. Preserve the original medical meaning of the text. Do not change what "
	"the text is saying.\n"
	"2. For each term that IS in explanation_map, use ONLY that term's supplied "
	"explanation as your source of additional medical information about it. "
	"Integrate it naturally into the sentence or paragraph it belongs to -- do "
	"not mechanically insert 'term (explanation)'. Rephrase the surrounding "
	"sentence so the explanation reads as part of the prose.\n"
	"3. Do not add any medical fact, diagnosis, warning, treatment "
	"recommendation, or advice that is not already present in the original "
	"text or in one of the supplied explanations.\n"
	"4. Do not remove clinically meaningful information from the original text.\n"
	"5. Do not invent numbers, causes, risks, instructions, or outcomes that "
	"are not stated in the original text or the supplied explanations.\n"
	"6. Do not simplify, translate, paraphrase, or lightly reword ANY medical "
	"term, symptom name, lab value name, or drug name that is not a key in "
	"explanation_map -- not even into a well-known plain-language equivalent "
	"(e.g. do not turn 'polyuria' into 'frequent urination' unless polyuria "
	"itself is a key in explanation_map with that as its supplied "
	"explanation). Copy that term's exact original wording.\n\n"
	"Example of CORRECT behavior -- original: \"Your A1C is high.\" "
	"explanation_map = {\"A1C\": \"The A1C test measures your average blood "
	"sugar level over the past 2 or 3 months.\"}. Good rewrite: \"Your A1C, a "
	"test that shows your average blood sugar level over the past 2 or 3 "
	"months, is high.\" This integrates the explanation naturally and adds "
	"nothing beyond it.\n\n"
	"Example of INCORRECT behavior -- original: \"...polyuria, polydipsia, and "
	"HbA1c returned at 9.2%, ... started on Metformin.\" explanation_map only "
	"contains \"Blood Glucose\". It would be WRONG to rewrite 'polyuria' as "
	"'frequent urination', WRONG to rewrite 'polydipsia' as 'excessive "
	"thirst', WRONG to explain what HbA1c measures, and WRONG to explain what "
	"Metformin is -- none of those terms are in explanation_map, so all four "
	"must be copied through with their original wording unchanged, even though "
	"you know what they mean.\n\n"
	"Output ONLY the rewritten text. Do not include any preamble, labels, "
	"explanation of your changes, or surrounding quotes."
)

def _build_rewrite_user_prompt(original_text, explanation_map):
	lines = [
		"Original text:",
		original_text,
		"",
		"Approved explanations for medical terms found in this text "
		"(use these to simplify the text; do not add anything beyond them):",
	]
	for term, explanation in explanation_map.items():
		lines.append(f"- {term}: {explanation}")
	lines.append("")
	lines.append("Rewrite the text now, following all system instructions exactly.")
	return "\n".join(lines)

def simplify_text_with_openai(original_text: str, explanation_map: dict) -> str:
	"""Rewrites original_text into patient-friendly language, naturally integrating
	the approved explanation for each term in explanation_map ({term: explanation}).

	This function never selects or generates medical explanations itself -- it only
	rewrites wording. All medical content it may surface must already be present in
	original_text or explanation_map. On any failure it falls back to returning
	original_text unchanged rather than risking an unreviewed rewrite."""
	if not explanation_map:
		logger.debug("No approved explanations supplied; returning original text unchanged.")
		return original_text

	try:
		client = _get_openai_client()
		response = client.chat.completions.create(
			model=OPENAI_MODEL,
			messages=[
				{"role": "system", "content": _REWRITE_SYSTEM_PROMPT},
				{"role": "user", "content": _build_rewrite_user_prompt(original_text, explanation_map)},
			],
			timeout=30,
		)
		rewritten = response.choices[0].message.content.strip()
	except Exception:
		logger.exception("OpenAI rewrite call failed; returning original text unchanged.")
		return original_text

	if not rewritten:
		logger.warning("OpenAI rewrite returned empty content; returning original text unchanged.")
		return original_text

	logger.info("Rewrote text using %d approved explanation(s).", len(explanation_map))
	return rewritten

class ClinicalTranslator:
	def __init__(self, db_dict_summery_string, db_get_explanation_func):
		self.summary_string = db_dict_summery_string
		self.db_search_function = db_get_explanation_func
		logger.debug("ClinicalTranslator initialized.")

	def get_approved_terms(self, ui_selection: dict) -> list:
		approved = [term for term, is_selected in ui_selection.items() if is_selected]
		logger.debug(f"Approved {len(approved)} terms from UI selection.")
		return approved

	def fetch_explanations(self, approved_terms) -> dict:
		terms_dict = {}
		for term in approved_terms:
			try:
				explained = self.db_search_function(term)
				if explained and (self.summary_string in explained):
					terms_dict[term] = explained[self.summary_string]
			except Exception as e:
				logger.exception(f"Error fetching explanation for '{term}': {e}")
		logger.info(f"Successfully fetched {len(terms_dict)} explanations from DB.")
		return terms_dict

def apply_translations(text, detected_terms, ui_selection, explanation_field):
	"""Splice an explanation after each user-approved detected term's own
	span -- `detected_terms` is exactly detect_terms_with_explanations()'s
	output, so every span (Hebrew-prefixed tokens, aliases, synonyms) is
	trusted as-is: no independent re-search of `text`, and no
	overlap-resolution needed, since the detectors already return
	non-overlapping spans ordered by position. Returns (translated_text,
	explained_terms_list); the latter is deduplicated by term_name in
	first-seen order, since the same concept can be detected at more than
	one span in the text."""
	approved = [
		term for term in detected_terms
		if ui_selection.get(term["main_term"], False) and term.get(explanation_field)
	]
	translated_text = text
	for term in sorted(approved, key=lambda t: t["start"], reverse=True):
		end = term["end"]
		translated_text = f"{translated_text[:end]} ({term[explanation_field]}){translated_text[end:]}"
	explained_terms_list, seen = [], set()
	for term in approved:
		if term["term_name"] not in seen:
			seen.add(term["term_name"])
			explained_terms_list.append(term["term_name"])
	logger.info(f"Spliced {len(approved)} approved term occurrence(s) into text ({len(explained_terms_list)} unique).")
	return translated_text, explained_terms_list
