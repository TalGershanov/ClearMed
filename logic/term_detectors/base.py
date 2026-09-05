from abc import ABC, abstractmethod

from logic.medical_term_trie import MedicalTermTrie


class BaseTermDetector(ABC):
	"""Contract for a language-specific medical-term detector. Any concrete
	implementation (English, Hebrew, ...) must satisfy this without the
	caller (medical_term_detector.py) knowing which language it's dealing
	with."""

	@abstractmethod
	def detect_terms(self, text: str, trie_instance: MedicalTermTrie) -> list[dict]:
		"""Find every medical term mentioned in `text` by walking `trie_instance`.

		Returns a list of dicts, ordered by position of first appearance in
		`text`, each shaped like:
			{
				"matched_text": str,  # exact original substring of `text`,
				                      # preserving original casing/punctuation/
				                      # any stripped prefix characters
				"main_term": str,     # canonical term key, for DB lookup
				"start": int,         # character offset into `text`, inclusive
				"end": int,           # character offset into `text`, exclusive
			}
		`text[start:end] == matched_text` must always hold.

		Detectors needing custom per-token matching (e.g. prefix stripping)
		may walk `trie_instance.root` directly: `TrieNode.children: dict[str,
		TrieNode]`, `.is_end: bool`, `.main_term: str | None`.
		"""
		...
