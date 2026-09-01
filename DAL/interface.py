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

	@abstractmethod
	def insert_concept(
		self,
		concept_id: str,
		categories: list[str],
		explanations: list[dict],
		aliases: list[dict],
	) -> None:
		"""Insert one concept plus its explanations and aliases in a single
		transaction.

		explanations: list of {"language_code", "term_name",
			"simple_explanation", "short_explanation"}.
		aliases: list of {"alias_text", "language_code"}.
		Raises sqlite3.IntegrityError if concept_id already exists, or if
		called twice for the same (concept_id, language_code) pair.
		"""
		...

	@abstractmethod
	def get_term_details(self, concept_id: str, language_code: str) -> dict | None:
		"""Look up one concept's explanation in a given language via a JOIN
		between concepts and explanations.

		Returns a dict shaped like:
			{
				"concept_id": str,
				"categories": list[str],
				"language_code": str,
				"term_name": str,
				"simple_explanation": str | None,
				"short_explanation": str | None,
			}
		or None if no explanation exists for that concept_id/language_code.
		"""
		...
