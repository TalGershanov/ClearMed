from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from webapp.documents.schemas import DocumentOut


def _validate_folder_name(value: str) -> str:
	value = value.strip()
	if not value:
		raise ValueError("Folder name must not be empty")
	return value


class FolderCreate(BaseModel):
	name: str = Field(min_length=1, max_length=255)
	parent_folder_id: Optional[int] = None
	color: Optional[str] = Field(default=None, max_length=32)
	cover_image_path: Optional[str] = Field(default=None, max_length=512)

	@field_validator("name")
	@classmethod
	def name_not_blank(cls, value: str) -> str:
		return _validate_folder_name(value)


class FolderUpdate(BaseModel):
	"""All fields optional (PATCH semantics). Only fields actually present in
	the request body are applied -- see model_dump(exclude_unset=True) in the
	router, which is what lets parent_folder_id=null mean "move to root"
	while omitting parent_folder_id entirely means "don't touch it"."""

	name: Optional[str] = Field(default=None, min_length=1, max_length=255)
	color: Optional[str] = Field(default=None, max_length=32)
	cover_image_path: Optional[str] = Field(default=None, max_length=512)
	parent_folder_id: Optional[int] = None

	@field_validator("name")
	@classmethod
	def name_not_blank(cls, value: Optional[str]) -> Optional[str]:
		if value is None:
			return value
		return _validate_folder_name(value)


class FolderOut(BaseModel):
	model_config = ConfigDict(from_attributes=True)

	id: int
	name: str
	parent_folder_id: Optional[int]
	color: Optional[str]
	cover_image_path: Optional[str]
	created_at: datetime
	updated_at: datetime
	# Documents directly assigned to this folder only -- never recursive into
	# child folders (see webapp/folders/service.py::count_documents_by_folder_ids).
	# Not a mapped column on Folder, so every endpoint returning a FolderOut
	# must construct it explicitly (from_attributes can't derive this one).
	document_count: int


class FolderDetail(FolderOut):
	children: list[FolderOut] = Field(default_factory=list)
	# Direct documents only -- a nested subfolder's documents are not
	# included here; they're returned when that subfolder itself is opened
	# (see webapp/folders/router.py::get_folder).
	documents: list[DocumentOut] = Field(default_factory=list)


class FolderDeletionPreview(BaseModel):
	"""GET /folders/{id}/deletion-preview -- the real, recursive impact of
	deleting this folder with ?recursive=true, shown to the user before they
	confirm. Distinct from FolderOut.document_count, which is deliberately
	direct-only."""

	document_count: int
	subfolder_count: int
