from functools import lru_cache

from webapp.core import config
from webapp.storage.base import StorageBackend
from webapp.storage.local import LocalStorageBackend


@lru_cache
def get_storage() -> StorageBackend:
	"""The single place that decides which storage backend is active --
	callers only ever depend on StorageBackend, so nothing in
	webapp/documents/ needs to change when this switches backends."""
	if config.STORAGE_BACKEND == "s3":
		if not config.S3_BUCKET_NAME:
			raise RuntimeError("S3_BUCKET_NAME must be set when STORAGE_BACKEND=s3")
		# Imported lazily so local dev (STORAGE_BACKEND unset) never needs
		# boto3 installed at all.
		from webapp.storage.s3 import S3StorageBackend

		return S3StorageBackend(config.S3_BUCKET_NAME, config.AWS_REGION)
	return LocalStorageBackend(config.LOCAL_STORAGE_DIR)
