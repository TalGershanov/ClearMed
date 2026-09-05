import re

from logic.medical_term_trie import MedicalTermTrie
from logic.term_detectors.base import BaseTermDetector

# a token is a maximal run of letters/digits -- matches the character class
# medical_term_trie.normalize_text() keeps after stripping punctuation, but
# applied per-token directly over the raw text so each token's original
# (start, end) span is preserved
TOKEN_RE = re.compile(r"[A-Za-z0-9]+")


class EnglishTermDetector(BaseTermDetector):
	def detect_terms(self, text: str, trie_instance: MedicalTermTrie) -> list[dict]:
		# tokenize the raw text once, keeping each token's normalized form
		# (for trie lookup) alongside its original character span (for offsets)
		words = []
		spans = []
		for match in TOKEN_RE.finditer(text):
			words.append(match.group().lower())
			spans.append(match.span())

		matches = trie_instance.find_word_matches(words)

		results = []
		for match in matches:
			start = spans[match["start_word_index"]][0]
			end = spans[match["end_word_index"]][1]
			results.append({
				# sliced from the raw text so original casing/punctuation
				# between matched words is preserved verbatim
				"matched_text": text[start:end],
				"main_term": match["main_term"],
				"start": start,
				"end": end,
			})
		return results
