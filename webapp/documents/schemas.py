from datetime import datetime
from typing import Dict, Optional

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

	# Phase 5: ClearMed analysis + simplification. detected_terms/
	# term_selection are Optional (not defaulted to []/{}), matching the
	# nullable columns exactly -- None means "not analysed yet", not "empty
	# result". A genuinely-analysed-with-zero-terms document has
	# detected_terms == [] (not None), which is a distinct, valid state.
	analysis_status: str
	detected_terms: Optional[list] = None
	term_selection: Optional[Dict[str, bool]] = None

	simplification_status: str
	simplified_text: Optional[str] = None


class TermSelectionUpdate(BaseModel):
	"""Body for PATCH /documents/{id}/selection -- always the full current
	selection, keyed by concept_id (main_term), never by term_name."""

	term_selection: Dict[str, bool]
