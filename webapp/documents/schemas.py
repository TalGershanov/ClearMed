from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class DocumentOut(BaseModel):
	"""Lightweight shape used in folder listings. Deliberately excludes
	original_text -- the full extracted text is only ever returned by the
	authenticated document-detail endpoint (see DocumentDetail)."""

	model_config = ConfigDict(from_attributes=True)

	id: int
	folder_id: int
	name: str
	original_filename: str
	mime_type: str
	file_size: int
	extraction_status: str
	created_at: datetime
	updated_at: datetime


class DocumentDetail(DocumentOut):
	original_text: Optional[str] = None
