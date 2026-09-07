import logging

import boto3
from botocore.exceptions import ClientError

from webapp.storage.base import StorageBackend

logger = logging.getLogger("clearmed.webapp.storage.s3")


class S3StorageBackend(StorageBackend):
	"""Stores uploaded document bytes in a single S3 bucket. Credentials are
	never read from config here -- the process is expected to run with an
	IAM role (e.g. an EC2 instance profile) that already grants exactly
	s3:GetObject/PutObject/DeleteObject/ListBucket on `bucket_name`, so
	boto3's default credential chain picks them up automatically."""

	def __init__(self, bucket_name: str, region_name: str | None = None):
		self._bucket_name = bucket_name
		self._client = boto3.client("s3", region_name=region_name)

	def save(self, data: bytes, key: str) -> None:
		self._client.put_object(Bucket=self._bucket_name, Key=key, Body=data)

	def read(self, key: str) -> bytes:
		response = self._client.get_object(Bucket=self._bucket_name, Key=key)
		return response["Body"].read()

	def delete(self, key: str) -> None:
		try:
			self._client.delete_object(Bucket=self._bucket_name, Key=key)
		except ClientError as e:
			# Mirrors LocalStorageBackend.delete()'s "already gone is success"
			# contract -- S3's delete_object is normally idempotent on its own
			# (no error for a missing key), this only guards the rare case of
			# a ClientError that still means "not there".
			if e.response.get("Error", {}).get("Code") not in ("NoSuchKey", "404"):
				raise
