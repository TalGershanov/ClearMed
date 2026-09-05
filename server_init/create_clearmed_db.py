import functools
import json
import logging
import sqlite3
import re
import unicodedata
from typing import Optional

from dotenv import load_dotenv
from openai import OpenAI

import bootstrap
_ = bootstrap  # side-effect import: puts the repo root on sys.path (see server_init/bootstrap.py)
from config import JSON_FILE, DB_FILE
from DAL.db import SQLiteDatabase

load_dotenv()

logger = logging.getLogger("clearmed.server_init.create_clearmed_db")

OPENAI_MODEL = "gpt-4o-mini"

@functools.cache
def _get_openai_client() -> OpenAI:
	return OpenAI()

_QUESTION_PREFIXES = ("what is ", "what are ", "what causes ", "who is ", "who are ", "how is ", "how are ")

def _clean_candidate_sentences(full_explanation):
	if not full_explanation:
		return []
	# remove source references like NIH etc.
	text = re.sub(r"NIH:.*", "", full_explanation).strip()
	# split into sentences
	sentences = re.split(r"(?<=[.!?])\s+|\n+", text)
	sentences = [s.strip() for s in sentences if s.strip()]
	if not sentences:
		return []
	cleaned_sentences = []
	for sentence in sentences:
		lower_sentence = sentence.lower().strip()
		# skip question sentences that don't explain anything
		if lower_sentence.startswith(_QUESTION_PREFIXES):
			continue
		cleaned_sentences.append(sentence)
	# if filtering removed everything, revert to the original sentences
	if not cleaned_sentences:
		cleaned_sentences = sentences
	return cleaned_sentences

def _select_short_explanation_fallback(full_explanation, max_words=30):
	sentences = _clean_candidate_sentences(full_explanation)
	if not sentences:
		return None
	priority_keywords = [
		"measures",
		"used to",
		"means",
		"is a",
		"is an",
		"are a",
		"are an",
		"refers to",
		"is the",
		"are the"
	]
	chosen_sentence = None
	for keyword in priority_keywords:
		for sentence in sentences[:6]:
			if keyword in sentence.lower():
				chosen_sentence = sentence
				break
		if chosen_sentence is not None:
			break
	# if we didn't find one by keywords, take the first sentence remaining after filtering questions
	if chosen_sentence is None:
		chosen_sentence = sentences[0]
	return _truncate_to_max_words(chosen_sentence, max_words)

def _truncate_to_max_words(sentence, max_words):
	words = sentence.split()
	if len(words) > max_words:
		sentence = " ".join(words[:max_words]) + "..."
	return sentence.strip()

_SYSTEM_PROMPT = (
	"You select ONE sentence from a numbered list of candidate sentences to "
	"show a patient who just encountered a medical term in their medical "
	"document. You never write, rewrite, paraphrase, shorten, combine "
	"sentences, extract part of a sentence, correct the source, or add "
	"medical information: you only choose which existing candidate to "
	"show, exactly as it appears. The patient will see ONLY the sentence "
	"you pick, with no surrounding context.\n\n"
	"The purpose of the sentence you choose is to explain the meaning of "
	"the term as clearly and meaningfully as possible in one source "
	"sentence. Do not optimize for the most interesting, medically "
	"detailed, or generally useful fact -- optimize for understanding the "
	"term. Use the following decision hierarchy.\n\n"
	"1. THE SENTENCE MUST WORK ON ITS OWN\n"
	"The patient will see only this sentence. Prefer a sentence that feels "
	"complete and understandable without anything before or after it. Do "
	"not select a sentence that feels like the continuation of another "
	"sentence -- this includes cases such as 'One type...', 'Another "
	"type...', 'But...', 'In that case...', 'They...', 'It...', when the "
	"reader needs previous context to understand what is being discussed. "
	"Do NOT reject these words mechanically. The actual test is: if this "
	"were the only sentence shown to the patient, would the patient "
	"clearly understand what the sentence is referring to and what it "
	"means? If not, prefer another meaningful standalone candidate. A "
	"standalone explanation should not feel like the patient entered "
	"halfway through a paragraph. Example: 'One type of ...' is bad when "
	"understanding 'one type' requires the previous sentence -- prefer a "
	"complete sentence that explains the concept directly. The fact that "
	"a sentence is grammatically valid does not mean it works as a "
	"standalone explanation.\n\n"
	"2. EXPLAIN THE TERM -- NOT JUST SOMETHING ABOUT THE TOPIC\n"
	"The sentence should help answer 'What does this term mean?'. Do not "
	"select a sentence merely because it contains useful, important, or "
	"interesting information related to the topic -- e.g. advice given to "
	"a caregiver is not necessarily a good explanation of the term "
	"'caregiver'. For example, for the term 'Alzheimer's Caregivers', "
	"prefer 'A caregiver gives care to someone who needs help taking care "
	"of themselves.' over 'As a caregiver, it is important for you to "
	"learn about AD.' -- the first explains the core concept, the second "
	"gives advice related to it. Similarly, do not prefer recommendations, "
	"warnings, prevalence, statistics, risk information, exposure routes, "
	"or treatment advice when another sentence more directly explains the "
	"term.\n\n"
	"3. MEANINGFUL EXPLANATION CAN BE BETTER THAN A SHALLOW DEFINITION\n"
	"Do not automatically select the sentence that looks most like a "
	"dictionary definition. 'X is a disease.' or 'X is a rare disorder.' "
	"may technically define the term while providing very little "
	"understanding. If another standalone sentence explains what "
	"fundamentally happens in the condition, what a test measures, or "
	"what something does, that sentence may be better. Ask: which "
	"sentence leaves the patient with the clearest understanding of what "
	"this term actually means? This depends on the type of term: for a "
	"disease/condition, what it is or what fundamentally happens in the "
	"condition; for a test/screening, what it measures, detects, or looks "
	"for; for a medication/treatment, what it is used for or what it "
	"does; for a procedure, what it does or why it is performed; for "
	"anatomy/body structures, what it is, where it is, or what it does; "
	"for a general concept, its clearest direct meaning. Example: for "
	"'Polio and Post-Polio Syndrome', prefer 'Post-polio syndrome (PPS) "
	"is a condition that affects polio survivors many years after they "
	"recovered from polio.' over 'Post-polio syndrome (PPS), which "
	"happens later in life.' -- the first is understandable and "
	"informative by itself, the second is a fragment that depends on "
	"surrounding text. Example: for 'Drugs and Young People', prefer "
	"'Taking drugs when young can interfere with developmental processes "
	"occurring in the brain.' over 'Why are drugs especially dangerous "
	"for young people?' -- the question introduces the topic but does not "
	"explain it; the preferred sentence gives actual understanding.\n\n"
	"4. CONSIDER THE CORE CONCEPT FOR BROAD 'X DISEASES / X DISORDERS' "
	"TOPICS\n"
	"For broad terms such as 'Bladder Diseases', 'Foot Injuries and "
	"Disorders', or other 'X Diseases' / 'X Disorders' topics, do not "
	"assume a generic sentence saying 'many conditions can affect X' is "
	"automatically the best explanation. Sometimes a sentence explaining "
	"the underlying body part or core concept gives the patient more "
	"useful understanding -- e.g. for 'Bladder Diseases', a clear sentence "
	"explaining what the bladder is and what it does may be more "
	"informative than a generic statement that many diseases can affect "
	"the bladder. Judge which existing sentence best helps the patient "
	"understand the concept represented by the term.\n\n"
	"5. USE PATIENT VALUE ONLY AFTER THE TERM IS EXPLAINED\n"
	"Patient usefulness is a tie-breaker, not the primary objective. "
	"First ask: does this explain the term? Then: does it stand alone? "
	"Then, if multiple candidates are still good: which one gives the "
	"patient the most meaningful understanding? Do not choose a secondary "
	"fact merely because it may be useful to know.\n\n"
	"6. DO NOT PREFER BREVITY AT THE COST OF UNDERSTANDING\n"
	"The shortest sentence is not necessarily the best sentence. A "
	"somewhat longer sentence is preferable when it gives substantially "
	"better understanding of the term. However, do not select a long list "
	"or unnecessary detail merely because it contains more information. "
	"Choose the best balance of clarity + meaning + completeness within "
	"ONE existing source sentence.\n\n"
	"FINAL INTERNAL DECISION -- before choosing, ask in this order: "
	"(1) Does the sentence actually explain the term or its core concept? "
	"(2) Can it be understood completely on its own? (3) Does it provide "
	"meaningful understanding rather than a shallow label or secondary "
	"fact? (4) Is it appropriate for the type of term? (5) If several "
	"candidates remain strong, which gives the patient the greatest "
	"understanding?\n\n"
	"You must never rewrite, paraphrase, shorten, combine sentences, "
	"extract part of a sentence, correct the source, or add medical "
	"information. You select ONE candidate index only. All final medical "
	"text must continue to come directly from the verified MedlinePlus "
	"source.\n\n"
	"Respond with ONLY JSON of the form "
	'{"selected_index": <the integer index of the chosen candidate>}. '
	"Do not include any reasoning or explanation in your response."
)

# Split out from select_short_explanation_ai so the annotation tool (annotation/annotate.py)
# can get the raw model index for comparison against a human label, without duplicating this
# API-calling logic or the candidate-splitting logic in _clean_candidate_sentences.
def _select_short_explanation_index_ai(sentences, term=None):
	try:
		client = _get_openai_client()
		user_prompt = (
			"Term: " + (term or "") + "\n"
			"Candidate sentences (respond with the index of exactly one):\n"
			+ "\n".join(f"{i}: {s}" for i, s in enumerate(sentences))
		)
		response = client.chat.completions.create(
			model=OPENAI_MODEL,
			response_format={"type": "json_object"},
			messages=[
				{"role": "system", "content": _SYSTEM_PROMPT},
				{"role": "user", "content": user_prompt},
			],
			timeout=30,
		)
		payload = json.loads(response.choices[0].message.content)
		selected_index = payload.get("selected_index")
	except Exception:
		logger.warning("AI short-explanation call failed for term %r; using fallback", term, exc_info=True)
		return None

	if not isinstance(selected_index, int) or isinstance(selected_index, bool) or not (0 <= selected_index < len(sentences)):
		logger.warning("AI short-explanation for term %r returned an invalid index (%r); using fallback", term, selected_index)
		return None

	return selected_index

def select_short_explanation_ai(full_explanation, term=None, max_words=30):
	sentences = _clean_candidate_sentences(full_explanation)
	if not sentences:
		return None

	selected_index = _select_short_explanation_index_ai(sentences, term=term)
	if selected_index is None:
		return _select_short_explanation_fallback(full_explanation, max_words)

	# Pulled directly from our own candidate list, never from model-generated text.
	selected = sentences[selected_index]
	return _truncate_to_max_words(selected, max_words)

# --- Hebrew translation stage --------------------------------------------
# Completely independent from V7. This function only ever receives the
# sentence V7 already selected (a plain string) -- it never sees the
# candidate list, simple_explanation, or the term name, and it never
# participates in selection. It has exactly one job: translate the given
# English sentence to Hebrew, word-for-meaning, without adding, removing, or
# reinterpreting any medical content. V7's own prompt/logic above this point
# is untouched by this stage.
_HEBREW_TRANSLATION_SYSTEM_PROMPT = (
	"You are translating a patient-friendly medical explanation from English "
	"to Hebrew.\n\n"
	"Translate the supplied English text into clear, natural Hebrew suitable "
	"for a patient.\n\n"
	"Rules:\n"
	"1. Preserve the medical meaning exactly.\n"
	"2. Translate all information contained in the source sentence.\n"
	"3. Do not add any medical information.\n"
	"4. Do not remove any medical information.\n"
	"5. Do not explain, expand, summarize, reinterpret, or medically "
	"simplify the content beyond what is required for natural Hebrew "
	"translation.\n"
	"6. Do not introduce diagnoses, causes, risks, warnings, treatment "
	"advice, numbers, or medical facts that are not explicitly present in "
	"the English source.\n"
	"7. Preserve important medical terminology accurately while using "
	"natural Hebrew phrasing.\n"
	"8. Preserve numbers, units, percentages, and other clinical values "
	"exactly if present.\n"
	"9. If a term is ambiguous, prefer a faithful translation rather than "
	"guessing additional medical meaning.\n"
	"10. The translation must be fully Hebrew. Every ordinary word -- every "
	"noun, verb, and adjective, including medical-sounding ones like "
	"'sclerosis', 'hernia', 'thrombosis', 'mental', 'causing', or "
	"'procedure' -- must be rendered in Hebrew. Never leave an English word "
	"untranslated because it looks technical; that is a translation error, "
	"not a valid abbreviation. The ONLY text allowed to remain in Latin "
	"script is a short, standard acronym or initialism that is itself the "
	"accepted medical shorthand (e.g. 'HIV', 'DNA', 'COPD', 'DVT') -- never "
	"a spelled-out English word or phrase. When you do keep such an acronym, "
	"surround it with normal Hebrew spacing and punctuation; never glue it "
	"directly onto an adjacent Hebrew word with no space.\n"
	"11. Return ONLY the Hebrew translation. Do not include explanations, "
	"labels, quotation marks, or commentary."
)

# Observed in production output: gpt-4o-mini occasionally (a) hallucinates a
# stray character (or run of characters) from an unrelated script -- Cyrillic,
# Thai, Arabic, CJK -- spliced directly into an otherwise-correct Hebrew
# sentence (e.g. "אטрофיה" with Cyrillic р/о, or "להת出生" with a Chinese
# character glued mid-word), or (b) leaves an ordinary English word untranslated
# even though _HEBREW_TRANSLATION_SYSTEM_PROMPT rule 10 forbids it (e.g.
# "thrombosis", "causing", "veins"). Neither is ever valid output: Hebrew
# medical text only ever legitimately contains Hebrew script,
# digits/punctuation, and the occasional Latin acronym -- and a real acronym
# is conventionally written in ALL CAPS (HIV, COPD, DVT...), never lowercase
# or mixed case, which is what distinguishes it from a spelled-out word here.
# _translation_defect() lets translate_short_explanation_to_hebrew() detect
# and retry either failure mode instead of ever writing one to the DB.
_ALLOWED_NON_HEBREW_SCRIPTS = ("LATIN",)
_LATIN_WORD_RE = re.compile(r"[A-Za-z]+")

def _translation_defect(text: str) -> Optional[str]:
	"""Returns a short human-readable reason `text` fails validation, or
	None if it passes."""
	for char in text:
		if not char.isalpha():
			continue
		char_name = unicodedata.name(char, "")
		if "HEBREW" in char_name:
			continue
		if any(char_name.startswith(script) for script in _ALLOWED_NON_HEBREW_SCRIPTS):
			continue
		return f"disallowed script character {char!r} ({char_name})"

	stray_words = [word for word in _LATIN_WORD_RE.findall(text) if not word.isupper()]
	if stray_words:
		return f"stray non-acronym English word(s) {stray_words!r}"

	return None

_MAX_TRANSLATION_ATTEMPTS = 3

def translate_short_explanation_to_hebrew(short_explanation: str) -> Optional[str]:
	"""Translates an already V7-selected English short_explanation to Hebrew.

	Never called with anything other than V7's final output; never invokes
	V7 or any selection logic itself. Returns None (not an English fallback
	string) on missing input, a call that keeps failing/erroring, an empty
	response, or a response that still fails validation after retrying --
	see the module-level note on why None is the correct fallback for this
	field."""
	if not short_explanation:
		return None

	for attempt in range(1, _MAX_TRANSLATION_ATTEMPTS + 1):
		try:
			client = _get_openai_client()
			response = client.chat.completions.create(
				model=OPENAI_MODEL,
				messages=[
					{"role": "system", "content": _HEBREW_TRANSLATION_SYSTEM_PROMPT},
					{"role": "user", "content": short_explanation},
				],
				timeout=30,
			)
			translated = response.choices[0].message.content.strip()
		except Exception:
			logger.warning("Hebrew translation call failed for %r (attempt %d/%d)", short_explanation, attempt, _MAX_TRANSLATION_ATTEMPTS, exc_info=True)
			continue

		if not translated:
			logger.warning("Hebrew translation returned empty content for %r (attempt %d/%d)", short_explanation, attempt, _MAX_TRANSLATION_ATTEMPTS)
			continue

		defect = _translation_defect(translated)
		if defect:
			logger.warning("Hebrew translation failed validation (%s) for %r (attempt %d/%d): %r", defect, short_explanation, attempt, _MAX_TRANSLATION_ATTEMPTS, translated)
			continue

		return translated

	logger.warning("Hebrew translation failed after %d attempt(s) for short_explanation %r", _MAX_TRANSLATION_ATTEMPTS, short_explanation)
	return None

def populate_hebrew_translations():
	"""Replaces the placeholder short_explanation on every existing 'he'
	explanations row (created by populate_hebrew_terms() from the
	infomed.co.il scrape -- see server_init/hebrew_terms.py, where that
	placeholder is just the matched English concept's short_explanation
	copied verbatim) with a real AI translation of that English
	short_explanation. Never touches term_name/simple_explanation, and never
	calls V7. Used both by the normal bootstrap pipeline
	(server_init/bootstrap.py, after populate_hebrew_terms()) and by
	server_init/retranslate_hebrew.py, so there is exactly one
	implementation of this loop.

	If translation fails for a row (translate_short_explanation_to_hebrew
	returns None), that row is skipped entirely: its existing
	short_explanation (the placeholder, or a previously successful
	translation) is left untouched rather than being overwritten with NULL."""
	connection = sqlite3.connect(DB_FILE)
	cursor = connection.cursor()
	cursor.execute("""
		SELECT he.explanation_id, he.term_name, en.short_explanation
		FROM explanations AS he
		JOIN explanations AS en
			ON en.concept_id = he.concept_id AND en.language_code = 'en'
		WHERE he.language_code = 'he'
	""")
	rows = cursor.fetchall()

	total = len(rows)
	updated = 0
	skipped_no_source = 0
	failed = 0

	for index, (explanation_id, term_name, english_short_explanation) in enumerate(rows, start=1):
		if not english_short_explanation:
			skipped_no_source += 1
			continue

		translated = translate_short_explanation_to_hebrew(english_short_explanation)
		if translated is None:
			failed += 1
			logger.warning("Hebrew translation failed for term %r (explanation_id=%s); existing short_explanation left untouched", term_name, explanation_id)
			continue

		cursor.execute("UPDATE explanations SET short_explanation = ? WHERE explanation_id = ?", (translated, explanation_id))
		connection.commit()
		updated += 1

		if index % 50 == 0:
			logger.info("Hebrew: processed %d/%d rows", index, total)

	connection.close()
	logger.info(
		"Hebrew stage complete: %d updated, %d skipped (no source), %d failed (of %d rows)",
		updated, skipped_no_source, failed, total,
	)
	return {"total": total, "updated": updated, "skipped_no_source": skipped_no_source, "failed": failed}

def create_concept_tables(cursor):
	cursor.execute("""
		CREATE TABLE IF NOT EXISTS concepts (
			concept_id TEXT PRIMARY KEY,
			categories TEXT
		)
	""")
	cursor.execute("""
		CREATE TABLE IF NOT EXISTS explanations (
			explanation_id INTEGER PRIMARY KEY AUTOINCREMENT,
			concept_id TEXT NOT NULL REFERENCES concepts (concept_id),
			language_code TEXT NOT NULL,
			term_name TEXT NOT NULL,
			simple_explanation TEXT,
			short_explanation TEXT,
			UNIQUE (concept_id, language_code)
		)
	""")
	cursor.execute("""
		CREATE TABLE IF NOT EXISTS term_aliases (
			alias_text TEXT PRIMARY KEY,
			concept_id TEXT NOT NULL REFERENCES concepts (concept_id),
			language_code TEXT
		)
	""")
	cursor.execute("""
		CREATE INDEX IF NOT EXISTS idx_term_aliases_concept_id
		ON term_aliases (concept_id)
	""")

def insert_concepts(terms):
	# Writes through DAL.insert_concept() rather than raw sqlite3: the
	# interface already declares exactly this write primitive (one concept +
	# its explanations + aliases in one transaction), so there's no reason
	# for this script to hand-roll a second copy of that INSERT logic. One
	# connection is opened for the whole run and passed to every call so the
	# ~1000-term seed is one transaction/commit, not one per concept.
	dal = SQLiteDatabase()
	connection = dal._get_connection()
	total = len(terms)
	try:
		with connection:
			for index, item in enumerate(terms, start=1):
				simple_explanation = item.get("simple_explanation")
				# OpenAI hook (English): this is where the English short_explanation
				# is generated today. If you're improving this algorithm, change it
				# here -- select_short_explanation_ai() above.
				short_explanation = select_short_explanation_ai(simple_explanation, term=item.get("term"))
				if index % 50 == 0:
					logger.info("Processed %d/%d terms", index, total)
				term = item.get("term")
				synonyms = item.get("synonyms", [])
				dal.insert_concept(
					concept_id=item.get("source_id"),
					categories=item.get("categories", []),
					explanations=[{
						"language_code": "en",
						"term_name": term,
						"simple_explanation": simple_explanation,
						"short_explanation": short_explanation,
					}],
					aliases=[
						{"alias_text": term, "language_code": "en"},
						*({"alias_text": synonym, "language_code": "en"} for synonym in synonyms),
					],
					connection=connection,
				)
	finally:
		connection.close()

def create_database():
	with open(JSON_FILE, "r", encoding="utf-8") as f:
		data = json.load(f)
	terms = data["terms"]
	connection = sqlite3.connect(DB_FILE)
	cursor = connection.cursor()
	# Retire the old flat schema and (re)build the normalized one -- a fresh
	# rebuild lands directly in the current concepts/explanations/term_aliases
	# shape, so no separate migration step is ever needed after this runs.
	cursor.execute("DROP TABLE IF EXISTS medical_terms")
	cursor.execute("DROP TABLE IF EXISTS term_aliases")
	cursor.execute("DROP TABLE IF EXISTS explanations")
	cursor.execute("DROP TABLE IF EXISTS concepts")
	create_concept_tables(cursor)
	connection.commit()
	connection.close()

	insert_concepts(terms)
	print(f"Database created: {DB_FILE}")
	print(f"Inserted concepts: {len(terms)}")

	# Smoke check: verify the DAL read path agrees with what this script just
	# wrote. Catches write/read schema drift (e.g. a reordered SELECT or
	# CREATE TABLE) immediately at seed time instead of silently corrupting
	# data in production.
	first_term = terms[0]
	dal = SQLiteDatabase()
	fetched = dal.get_term_details(first_term["source_id"], "en")
	if fetched is None:
		raise AssertionError(
			f"Smoke check failed: DAL could not find seeded concept {first_term['source_id']!r}"
		)
	if fetched["short_explanation"] is not None and not isinstance(fetched["short_explanation"], str):
		raise AssertionError(
			"Smoke check failed: short_explanation has unexpected type -- check DAL/db.py column mapping"
		)
	for field, expected in (
		("term_name", first_term["term"]),
		("simple_explanation", first_term.get("simple_explanation")),
		("categories", first_term.get("categories", [])),
	):
		if fetched[field] != expected:
			raise AssertionError(
				f"Smoke check failed: {field} mismatch ({fetched[field]!r} != {expected!r})"
			)
	print(f"Smoke check passed: DAL read back concept {first_term['source_id']!r} correctly")

if __name__ == "__main__":
	from log_config import setup_logging
	from populate_hebrew_terms import populate_hebrew_terms
	setup_logging()
	create_database()
	# create_database() drops and rebuilds concepts/explanations/term_aliases
	# from the English JSON alone, which would silently wipe any existing
	# Hebrew data if this script is run standalone instead of through
	# bootstrap.py -- repopulate it here so that can't happen.
	populate_hebrew_terms()
	# Overwrite each 'he' row's placeholder short_explanation (copied
	# verbatim from English at scrape time) with a real translation -- must
	# run after populate_hebrew_terms(), since it depends on the 'he' rows
	# that step creates.
	populate_hebrew_translations()
