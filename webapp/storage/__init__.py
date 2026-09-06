from functools import lru_cache

from webapp.core import config
from webapp.storage.base import StorageBackend
from webapp.storage.local import LocalStorageBackend


@lru_cache
def get_storage() -> StorageBackend:
	"""The single place that decides which storage backend is active.
	Swapping local disk for S3 later means adding an S3StorageBackend here
	(selected by an env var) -- callers only ever depend on StorageBackend,
	so nothing in webapp/documents/ needs to change."""
	return LocalStorageBackend(config.LOCAL_STORAGE_DIR)
