from abc import ABC, abstractmethod


class StorageBackend(ABC):
	"""Contract for where uploaded document bytes actually live. Callers pass
	a key they generated themselves (see webapp/documents/service.py) --
	never a client-supplied filename -- and must not create a DB row
	referencing that key unless save() returns without raising."""

	@abstractmethod
	def save(self, data: bytes, key: str) -> None:
		"""Persists data under key. Raises on failure."""
		...

	@abstractmethod
	def read(self, key: str) -> bytes:
		"""Reads back the bytes stored under key. Raises if missing."""
		...

	@abstractmethod
	def delete(self, key: str) -> None:
		"""Removes the object at key. Safe to call even if it's already
		gone -- callers treat that as success, not an error."""
		...
