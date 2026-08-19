from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict

class OpenMRSPatient(BaseModel):
	model_config = ConfigDict(extra="allow")

	uuid: str
	display: Optional[str] = None
	identifiers: Optional[List[Dict[str, Any]]] = None
	person: Optional[Dict[str, Any]] = None

class ObservationCreateRequest(BaseModel):
	patient_uuid: str
	concept_uuid: str
	value: Union[str, float, int]
	obs_datetime: Optional[datetime] = None
	encounter_uuid: Optional[str] = None

class OpenMRSObservation(BaseModel):
	model_config = ConfigDict(extra="allow")

	uuid: str
	display: Optional[str] = None
