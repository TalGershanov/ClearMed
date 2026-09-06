import logging

import anthropic
from dotenv import load_dotenv

logger = logging.getLogger("clearmed.translator")

load_dotenv()

CLAUDE_MODEL = "claude-haiku-4-5-20251001"

_claude_client = None

def _get_claude_client():
	global _claude_client
	if _claude_client is None:
		_claude_client = anthropic.Anthropic()
	return _claude_client

# This is the ONLY place in the runtime pipeline that generates new wording.
# It must never introduce medical facts, diagnoses, warnings, or treatment
# advice beyond what is already present in original_text or explanation_map --
# it rewrites for clarity, it does not add medical knowledge. V7 (selected
# offline, at DB-build time -- see server_init/ai_services.py) remains
# the sole source of which explanation text is "approved" for each term; this
# prompt only controls how that already-approved wording gets woven into the
# patient-facing paragraph.
_REWRITE_SYSTEM_PROMPT = """<role>
You are a clinical language rewriter. You rewrite medical text so a patient can understand it, using ONLY the information given to you. You are not a medical knowledge source.
</role>

<context>
You will receive the original medical text and explanation_map: approved explanations for specific medical terms, already selected from a verified medical source. For Hebrew text, these explanations were produced by a literal machine-translation engine (DeepL) -- their medical content is correct and final, but the Hebrew phrasing may not yet fit the grammar of the sentence around it.
</context>

<critical_rule name="strict_whitelist">
Treat explanation_map as the complete and exclusive boundary of medical knowledge you are authorized to add to the text. Never use your own medical knowledge to explain, define, expand, interpret, or simplify a medical term or concept absent from explanation_map -- whether it was detected but not approved, or never detected at all. An unlisted term must be left EXACTLY as it appears in the original text: do not translate it, simplify it, or reword it into a plain-language equivalent, no matter how well-known or obviously correct that knowledge is. You may adjust surrounding grammar only as strictly required to keep a sentence readable when an approved explanation is inserted elsewhere in it -- never as a reason to touch an unlisted term's own wording.
</critical_rule>

<critical_rule name="grammatical_smoothing">
Every explanation in explanation_map is a literal translation and may read stiffly in context. Weave each one naturally into the surrounding prose -- adjusting Hebrew prepositions (ב, ל, מ, ש) and inflection so the sentence reads as fluent, native Hebrew -- instead of mechanically inserting "term (explanation)". This smoothing may change ONLY grammar and phrasing. It must never alter, soften, sharpen, or add to the explanation's clinical meaning.
</critical_rule>

<rules>
1. Preserve the original medical meaning of the text; do not change what it says.
2. Do not add any medical fact, diagnosis, warning, treatment recommendation, or advice beyond what is already in the original text or an approved explanation.
3. Do not remove clinically meaningful information from the original text.
4. Do not invent numbers, causes, risks, instructions, or outcomes not stated in the original text or the approved explanations.
</rules>

<examples>
<example type="correct">
Original: "Your A1C is high."
explanation_map: {"A1C": "The A1C test measures your average blood sugar level over the past 2 or 3 months."}
Rewrite: "Your A1C, a test that shows your average blood sugar level over the past 2 or 3 months, is high."
</example>
<example type="incorrect">
Original: "...polyuria, polydipsia, and HbA1c returned at 9.2%, ... started on Metformin."
explanation_map only contains "Blood Glucose".
It would be WRONG to rewrite polyuria as "frequent urination", polydipsia as "excessive thirst", or to explain HbA1c or Metformin -- none of those terms are in explanation_map, so all four must be copied through with their original wording unchanged.
</example>
</examples>

<output_format>
Output ONLY the rewritten text. No preamble, labels, explanation of your changes, or surrounding quotes.
</output_format>"""

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

def simplify_text_with_claude(original_text: str, explanation_map: dict) -> str:
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
		client = _get_claude_client()
		response = client.messages.create(
			model=CLAUDE_MODEL,
			max_tokens=4096,
			# temperature is no longer a typed kwarg on this SDK version's
			# messages.create(), but the API still honors it -- extra_body is
			# the SDK's documented passthrough for such fields. 0 makes token
			# selection deterministic (always the highest-probability token);
			# it does not by itself enforce the whitelist rule -- that's the
			# system prompt's job (see _REWRITE_SYSTEM_PROMPT).
			extra_body={"temperature": 0},
			system=[
				{
					"type": "text",
					"text": _REWRITE_SYSTEM_PROMPT,
					"cache_control": {"type": "ephemeral"},
				}
			],
			messages=[
				{"role": "user", "content": _build_rewrite_user_prompt(original_text, explanation_map)},
			],
			timeout=30,
		)
		rewritten = response.content[0].text.strip()
	except Exception:
		logger.exception("Claude rewrite call failed; returning original text unchanged.")
		return original_text

	if not rewritten:
		logger.warning("Claude rewrite returned empty content; returning original text unchanged.")
		return original_text

	logger.info("Rewrote text using %d approved explanation(s).", len(explanation_map))
	return rewritten

def build_explanation_map(detected_terms, ui_selection, explanation_field):
	"""Filter detected_terms down to the user-approved ones with a usable
	explanation_field value, deduplicated by term_name in first-seen order --
	same approval/dedup semantics as apply_translations below, but returning
	{term_name: explanation} for simplify_text_with_claude instead of
	splicing spans: no position/offset handling needed since the Claude
	rewrite integrates explanations by name in prose, not by text offset."""
	explanation_map = {}
	explained_terms_list = []
	for term in detected_terms:
		if not ui_selection.get(term["main_term"], False):
			continue
		explanation = term.get(explanation_field)
		if not explanation or term["term_name"] in explanation_map:
			continue
		explanation_map[term["term_name"]] = explanation
		explained_terms_list.append(term["term_name"])
	return explanation_map, explained_terms_list

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
