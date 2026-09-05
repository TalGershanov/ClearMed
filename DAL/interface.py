from abc import ABC, abstractmethod
from typing import Optional


class DatabaseInterface(ABC):
	"""Contract for the data access layer. Any concrete implementation
	(SQLite today, something else tomorrow) must satisfy this without the
	logic layer knowing which one is in use."""

	@abstractmethod
	def get_term_by_name(self, term: str) -> Optional[dict]:
		"""Look up a single term by name (case-insensitive).

		Returns a dict shaped like:
			{
				"term": str,
				"short_explanation": str | None,
				"short_explanation_he": str | None,
				"simple_explanation": str | None,
				"synonyms": list[str],
	def get_all_aliases(self) -> list[dict]:
		"""Return every term_aliases row, for trie-building.

		Returns a list of dicts shaped like:
			{"alias_text": str, "concept_id": str, "language_code": str | None}
		"""
		...

	@abstractmethod
	def insert_concept(
		self,
		concept_id: str,
		categories: list[str],
		explanations: list[dict],
		aliases: list[dict],
		connection=None,
	) -> None:
		"""Insert one concept plus its explanations and aliases.

		explanations: list of {"language_code", "term_name",
			"simple_explanation", "short_explanation"}.
		aliases: list of {"alias_text", "language_code"} -- inserted with
			duplicate-alias_text rows silently ignored, since alias_text is
			a table-wide primary key shared across all concepts.
		Raises sqlite3.IntegrityError if concept_id already exists, or if
		called twice for the same (concept_id, language_code) pair.

		`connection`: optional already-open connection to write through
		instead of opening/committing/closing a new one -- lets a caller
		bulk-insert many concepts in a single transaction.
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
		or None if not found. synonyms/categories are already JSON-decoded.
		short_explanation_he is the Hebrew translation of short_explanation,
		produced by a separate translation stage during DB creation (see
		server_init/create_clearmed_db.py::translate_short_explanation_to_hebrew);
		it is None wherever no successful translation exists yet.
		or None if no explanation exists for that concept_id/language_code.
		"""
		...
