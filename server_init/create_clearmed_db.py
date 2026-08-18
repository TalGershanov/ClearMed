import json
import logging
import sqlite3
import re

from dotenv import load_dotenv
from openai import OpenAI

import bootstrap
from config import JSON_FILE, DB_FILE

load_dotenv()

logger = logging.getLogger("clearmed.server_init.create_clearmed_db")

OPENAI_MODEL = "gpt-4o-mini"

_openai_client = None

def _get_openai_client():
	global _openai_client
	if _openai_client is None:
		_openai_client = OpenAI()
	return _openai_client

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
		if lower_sentence.startswith("what is "):
			continue
		if lower_sentence.startswith("what are "):
			continue
		if lower_sentence.startswith("what causes "):
			continue
		if lower_sentence.startswith("who is "):
			continue
		if lower_sentence.startswith("who are "):
			continue
		if lower_sentence.startswith("how is "):
			continue
		if lower_sentence.startswith("how are "):
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

def create_tables(cursor):
	cursor.execute("""
		CREATE TABLE IF NOT EXISTS medical_terms (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			source_id TEXT,
			term TEXT NOT NULL,
			simple_explanation TEXT,
			short_explanation TEXT,
			synonyms TEXT,
			categories TEXT
		)
	""")

def insert_terms(cursor, terms):
	total = len(terms)
	for index, item in enumerate(terms, start=1):
		simple_explanation = item.get("simple_explanation")
		short_explanation = select_short_explanation_ai(simple_explanation, term=item.get("term"))
		if index % 50 == 0:
			logger.info("Processed %d/%d terms", index, total)
		cursor.execute("""
			INSERT INTO medical_terms (
				source_id,
				term,
				short_explanation,
				simple_explanation,
				synonyms,
				categories
			)
			VALUES (?, ?, ?, ?, ?, ?)
		""", (
			item.get("source_id"),
			item.get("term"),
			short_explanation,
			simple_explanation,
			json.dumps(item.get("synonyms", []), ensure_ascii=False),
			json.dumps(item.get("categories", []), ensure_ascii=False)
		))

def create_database():
	# Deliberately writes via raw sqlite3 rather than DAL/db.py: this is offline
	# schema/seed tooling with its own lifecycle, and DatabaseInterface only
	# declares the read methods the running app needs. If SQLiteDatabase is ever
	# swapped for a different backend, this script must be updated to match, or
	# it will keep seeding a store the app no longer reads from.
	with open(JSON_FILE, "r", encoding="utf-8") as f:
		data = json.load(f)
	terms = data["terms"]
	connection = sqlite3.connect(DB_FILE)
	cursor = connection.cursor()
	cursor.execute("DROP TABLE IF EXISTS medical_terms")
	create_tables(cursor)
	cursor.execute("DELETE FROM medical_terms")
	insert_terms(cursor, terms)
	connection.commit()
	connection.close()
	print(f"Database created: {DB_FILE}")
	print(f"Inserted terms: {len(terms)}")

if __name__ == "__main__":
	from log_config import setup_logging
	setup_logging()
	create_database()
