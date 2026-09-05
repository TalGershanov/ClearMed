import pytest

from logic.medical_term_trie import MedicalTermTrie, tokenize
from logic.term_detectors import EnglishTermDetector, HebrewTermDetector


@pytest.fixture
def trie():
	t = MedicalTermTrie()
	t.insert_words(tokenize("blood pressure"), "blood pressure")
	t.insert_words(tokenize("abdominal pain"), "abdominal pain")
	# hebrew phrase synonym for the same concept as "abdominal pain"
	t.insert_words(["כאב", "בטן"], "abdominal pain")
	# a bare hebrew root word that happens to start with a prefix letter (ב)
	t.insert_words(["בטן"], "abdomen")
	return t


def test_english_offsets_with_punctuation(trie):
	text = "Patient has high blood pressure, confirmed."
	results = EnglishTermDetector().detect_terms(text, trie)
	assert len(results) == 1
	match = results[0]
	assert match["main_term"] == "blood pressure"
	assert text[match["start"]:match["end"]] == match["matched_text"] == "blood pressure"


def test_hebrew_chained_prefix_strip(trie):
	# "מהבטן" chain-prefixes the bare root "בטן" with "מ" then "ה"
	text = "התלונן מהבטן"
	results = HebrewTermDetector().detect_terms(text, trie)
	assert len(results) == 1
	match = results[0]
	assert match["main_term"] == "abdomen"
	# offsets must span the full original token "מהבטן", not just "בטן"
	assert text[match["start"]:match["end"]] == match["matched_text"] == "מהבטן"


def test_hebrew_bare_word_not_overstripped(trie):
	# "בטן" appears bare here, with no attached prefix -- it must match
	# as-is and never be stripped down to "טן"
	text = "יש לו בטן נפוחה"
	results = HebrewTermDetector().detect_terms(text, trie)
	assert len(results) == 1
	match = results[0]
	assert match["main_term"] == "abdomen"
	assert match["matched_text"] == "בטן"


def test_mixed_hebrew_english_sentence(trie):
	text = "סבלה מ-Abdominal Pain"
	results = HebrewTermDetector().detect_terms(text, trie)
	assert len(results) == 1
	match = results[0]
	assert match["main_term"] == "abdominal pain"
	# original casing is preserved even though matching is case-insensitive
	assert text[match["start"]:match["end"]] == match["matched_text"] == "Abdominal Pain"


def test_all_offsets_are_internally_consistent(trie):
	text = "כאב מהבטן וגם Blood Pressure"
	results = HebrewTermDetector().detect_terms(text, trie)
	assert results
	for match in results:
		assert text[match["start"]:match["end"]] == match["matched_text"]
