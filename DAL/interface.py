from abc import ABC, abstractmethod


class DatabaseInterface(ABC):
	"""Contract for the data access layer. Any concrete implementation
	(SQLite today, something else tomorrow) must satisfy this without the
	logic layer knowing which one is in use."""

	@abstractmethod
	def get_term_by_name(self, term: str) -> dict | None:
		"""Look up a single term by name (case-insensitive).

		Returns a dict shaped like:
			{
				"term": str,
				"short_explanation": str | None,
				"simple_explanation": str | None,
				"synonyms": list[str],
				"categories": list[str],
			}
		or None if not found. synonyms/categories are already JSON-decoded.
		"""
		...

	@abstractmethod
	def get_all_terms(self) -> list[dict]:
		"""Return every term row, each shaped identically to
		get_term_by_name's return dict."""
		...
