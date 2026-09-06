import os

from webapp.storage.base import StorageBackend


class LocalStorageBackend(StorageBackend):
	def __init__(self, base_dir: str):
		self._base_dir = base_dir
		os.makedirs(self._base_dir, exist_ok=True)

	def _path_for(self, key: str) -> str:
		# Defense in depth: keys are always server-generated UUIDs (see
		# webapp/documents/service.py), never derived from a client-supplied
		# filename, so this can't actually be walked out of _base_dir today --
		# but refuse anything that looks like it could be, regardless.
		if "/" in key or "\\" in key or ".." in key:
			raise ValueError(f"Unsafe storage key: {key!r}")
		return os.path.join(self._base_dir, key)

	def save(self, data: bytes, key: str) -> None:
		with open(self._path_for(key), "wb") as f:
			f.write(data)

	def read(self, key: str) -> bytes:
		with open(self._path_for(key), "rb") as f:
			return f.read()

	def delete(self, key: str) -> None:
		try:
			os.remove(self._path_for(key))
		except FileNotFoundError:
			pass
