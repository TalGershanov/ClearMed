import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from webapp.core.database import Base


class ExtractionStatus(str, enum.Enum):
	# Images (JPG/PNG): no extractor registered yet -- awaiting OCR support.
	PENDING = "pending"
	# Real text recovered; original_text is populated.
	EXTRACTED = "extracted"
	# Parsed successfully but found no meaningful text -- most likely a
	# scanned PDF with no text layer. Awaiting OCR support, same as PENDING,
	# but kept distinct so the frontend/Phase 4.1 can tell "never attempted"
	# apart from "attempted, needs OCR".
	NO_TEXT_FOUND = "no_text_found"
	# A genuine parsing error (corrupted/malformed file).
	FAILED = "failed"


class AnalysisStatus(str, enum.Enum):
	# Never attempted (e.g. no usable extracted text yet).
	NOT_ANALYSED = "not_analysed"
	# ClearMed term detection ran and detected_terms/term_selection are populated
	# (detected_terms may legitimately be an empty list -- zero terms found).
	ANALYSED = "analysed"
	# Detection raised; original_text and the upload itself are untouched.
	FAILED = "failed"


class SimplificationStatus(str, enum.Enum):
	NOT_SIMPLIFIED = "not_simplified"
	# The pipeline ran to completion. Note this does NOT distinguish a real
	# OpenAI rewrite from simplify_text_with_openai's own internal "return
	# original_text unchanged" fallback on API failure -- that fallback is
	# that function's existing, intentional contract (see logic/translator.py),
	# not something this layer reinterprets. FAILED below is reserved for a
	# failure in *this* layer (e.g. a DB error), not an OpenAI-side hiccup.
	SIMPLIFIED = "simplified"
	FAILED = "failed"


class Document(Base):
	__tablename__ = "documents"

	id: Mapped[int] = mapped_column(primary_key=True)
	# Ownership assigned server-side from the authenticated user, same as
	# Folder -- never trust a user_id supplied by a client.
	user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
	# RESTRICT: webapp/folders/router.py blocks deleting a folder that still
	# has documents; this FK is a DB-level backstop if that check is ever
	# bypassed -- documents are never implicitly cascade-deleted with a folder.
	folder_id: Mapped[int] = mapped_column(ForeignKey("folders.id", ondelete="RESTRICT"), nullable=False, index=True)
	name: Mapped[str] = mapped_column(String(255), nullable=False)
	# Metadata only, from the client -- never used to construct a filesystem
	# path (see webapp/storage/).
	original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
	# Sniffed from file content server-side (webapp/documents/service.py),
	# never trusted from the client's declared Content-Type.
	mime_type: Mapped[str] = mapped_column(String(127), nullable=False)
	# Server-generated (UUID-based) key used to address the file in
	# webapp/storage/ -- the only thing ever used to locate it on disk.
	storage_key: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
	file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
	# Nullable: old documents predate this column, extraction may fail, and
	# image OCR isn't implemented yet -- None is a normal, expected state,
	# never fabricated content.
	original_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
	extraction_status: Mapped[str] = mapped_column(
		String(32), nullable=False, server_default=ExtractionStatus.PENDING.value
	)
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
	updated_at: Mapped[datetime] = mapped_column(
		DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
	)

	# --- Phase 5: ClearMed analysis + simplification, persisted so reopening
	# the document never loses them. Plain (not JSONB) JSON columns -- works
	# identically on Postgres and the SQLite engine the test suite uses,
	# and we don't need Postgres-only query features here.
	analysis_status: Mapped[str] = mapped_column(
		String(32), nullable=False, server_default=AnalysisStatus.NOT_ANALYSED.value
	)
	# Exactly logic.medical_term_detector.detect_terms_with_explanations()'s
	# return value, stored verbatim (list of dicts) -- never re-modeled, so it
	# can't drift out of sync with whatever fields that function returns.
	detected_terms: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
	# {concept_id: bool} -- keyed by concept_id (main_term), the same key
	# build_ui_selection()/ui_selection use. Never keyed by term_name.
	term_selection: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

	simplification_status: Mapped[str] = mapped_column(
		String(32), nullable=False, server_default=SimplificationStatus.NOT_SIMPLIFIED.value
	)
	simplified_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
