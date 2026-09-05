import re

from logic.medical_term_trie import MedicalTermTrie, TrieNode
from logic.term_detectors.base import BaseTermDetector

# scans mixed Hebrew/English text in one pass: each match is either a
# contiguous run of Hebrew-block characters or a contiguous run of
# Latin letters/digits. Anything else (whitespace, hyphens, punctuation) is
# not consumed by either alternative, so it's automatically skipped as a
# separator -- this is what splits "מ-Abdominal" into the two tokens "מ" and
# "Abdominal" with no special-casing needed for the hyphen.
_TOKEN_SCAN_RE = re.compile(r"[֐-׿]+|[A-Za-z0-9]+")


def is_hebrew_char(ch: str) -> bool:
	"""True if `ch` is in the Hebrew Unicode block. Shared with
	server_init/scrape_infomed_to_json.py so the "what counts as Hebrew"
	boundary is defined once, not duplicated."""
	return "֐" <= ch <= "׿"


def detect_language_code(text: str) -> str:
	"""Script-sniffs `text` to pick which DetectorFactory language_code to use:
	"he" if any character is in the Hebrew Unicode block, else "en". Mixed
	Hebrew/English text also resolves to "he", since HebrewTermDetector already
	tokenizes both scripts in one pass, while EnglishTermDetector cannot match
	Hebrew at all -- so "he" is the strictly more capable choice whenever any
	Hebrew is present."""
	return "he" if any(is_hebrew_char(ch) for ch in text) else "en"

# common Hebrew prefix particles, longest first so "וכש" isn't preempted by
# its leading "ו"
_HEBREW_PREFIXES = ("וכש", "מ", "ש", "ה", "ב", "ל", "ו")

# how many chained prefixes a single token may have stripped off it
# (e.g. "מהבטן" -> strip "מ" -> "הבטן" -> strip "ה" -> "בטן", 2 layers)
_MAX_PREFIX_STRIP_LAYERS = 3


def _resolve_child(node: TrieNode, token: str) -> TrieNode | None:
	"""Given the current trie node and a Hebrew token's normalized form,
	return the child node to descend into. Tries the token as-is first, and
	only falls back to stripping a known prefix (longest first) if that
	fails, repeating for a bounded number of layers. This ordering is what
	keeps a real root word that happens to start with a prefix letter (e.g.
	"בטן", which starts with the prefix "ב") from being over-stripped: it
	matches on the very first, unstripped check."""
	if token in node.children:
		return node.children[token]
	candidate = token
	for _ in range(_MAX_PREFIX_STRIP_LAYERS):
		stripped = None
		for prefix in _HEBREW_PREFIXES:
			if candidate.startswith(prefix) and len(candidate) > len(prefix):
				stripped = candidate[len(prefix):]
				break
		if stripped is None:
			return None
		if stripped in node.children:
			return node.children[stripped]
		candidate = stripped
	return None


class HebrewTermDetector(BaseTermDetector):
	def detect_terms(self, text: str, trie_instance: MedicalTermTrie) -> list[dict]:
		tokens = self._tokenize_mixed(text)

		results = []
		i = 0
		while i < len(tokens):
			current = trie_instance.root
			longest_match = None  # (main_term, end_token_index)
			j = i
			while j < len(tokens):
				normalized, _, _, script = tokens[j]
				if script == "he":
					next_node = _resolve_child(current, normalized)
				else:
					next_node = current.children.get(normalized)
				if next_node is None:
					break
				current = next_node
				if current.is_end:
					longest_match = (current.main_term, j)
				j += 1

			if longest_match:
				main_term, end_idx = longest_match
				# offsets always come from the untouched spans recorded during
				# tokenization -- prefix stripping only ever affects the trie
				# lookup key above, never what's reported here
				start_char = tokens[i][1]
				end_char = tokens[end_idx][2]
				results.append({
					"matched_text": text[start_char:end_char],
					"main_term": main_term,
					"start": start_char,
					"end": end_char,
				})
				i = end_idx + 1
			else:
				i += 1
		return results

	@staticmethod
	def _tokenize_mixed(text: str) -> list[tuple[str, int, int, str]]:
		# each entry: (normalized_word, start, end, script), script is "he" or "en"
		tokens = []
		for match in _TOKEN_SCAN_RE.finditer(text):
			raw = match.group()
			start, end = match.span()
			if is_hebrew_char(raw[0]):
				# no case-folding for Hebrew; prefix stripping happens later,
				# at trie-walk time, and never mutates the recorded span
				tokens.append((raw, start, end, "he"))
			else:
				tokens.append((raw.lower(), start, end, "en"))
		return tokens
