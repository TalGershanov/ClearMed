import logging
from typing import Any, Dict, Optional

import httpx

from openmrs.config import (
	OPENMRS_BASE_URL,
	OPENMRS_PASSWORD,
	OPENMRS_TIMEOUT_SECONDS,
	OPENMRS_USERNAME,
	is_configured,
)

logger = logging.getLogger("clearmed.openmrs.client")

class OpenMRSAPIError(Exception):
	def __init__(self, status_code: int, message: str, detail: Any = None):
		super().__init__(message)
		self.status_code = status_code
		self.message = message
		self.detail = detail

class OpenMRSClient:
	def __init__(self, base_url: str, username: str, password: str, timeout: float):
		self._client = httpx.AsyncClient(
			base_url=base_url,
			auth=httpx.BasicAuth(username, password),
			timeout=timeout,
		)

	async def get_patient(self, patient_uuid: str) -> Dict[str, Any]:
		return await self._request("GET", f"/ws/rest/v1/patient/{patient_uuid}", params={"v": "default"})

	async def create_observation(self, payload: Dict[str, Any]) -> Dict[str, Any]:
		return await self._request("POST", "/ws/rest/v1/obs", json=payload)

	async def aclose(self) -> None:
		await self._client.aclose()

	async def _request(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
		try:
			response = await self._client.request(method, path, **kwargs)
			response.raise_for_status()
			return response.json()
		except httpx.HTTPStatusError as e:
			message = str(e)
			detail = None
			try:
				detail = e.response.json()
				error_field = detail.get("error") if isinstance(detail, dict) else None
				if isinstance(error_field, dict):
					message = error_field.get("message", message)
				elif isinstance(error_field, str):
					message = error_field
			except ValueError:
				pass
			logger.warning("OpenMRS request failed: %s %s -> %s", method, path, e.response.status_code)
			raise OpenMRSAPIError(e.response.status_code, message, detail) from e
		except httpx.RequestError as e:
			logger.error("OpenMRS unreachable: %s %s -> %s", method, path, e)
			raise OpenMRSAPIError(503, f"OpenMRS is unreachable: {e}") from e
		except ValueError as e:
			logger.error("OpenMRS returned a non-JSON response: %s %s -> %s", method, path, e)
			raise OpenMRSAPIError(502, f"OpenMRS returned an invalid response: {e}") from e
		except RuntimeError as e:
			# e.g. the shared httpx.AsyncClient was closed by close_openmrs_client()
			# (app shutdown) while this request was still in flight.
			logger.error("OpenMRS client unavailable: %s %s -> %s", method, path, e)
			raise OpenMRSAPIError(503, f"OpenMRS client is unavailable: {e}") from e

_client: Optional[OpenMRSClient] = None

def get_openmrs_client() -> OpenMRSClient:
	global _client
	if _client is None:
		if not is_configured():
			raise RuntimeError("OpenMRS is not configured (missing OPENMRS_BASE_URL/USERNAME/PASSWORD)")
		_client = OpenMRSClient(OPENMRS_BASE_URL, OPENMRS_USERNAME, OPENMRS_PASSWORD, OPENMRS_TIMEOUT_SECONDS)
	return _client

async def close_openmrs_client() -> None:
	global _client
	if _client is not None:
		await _client.aclose()
		_client = None
