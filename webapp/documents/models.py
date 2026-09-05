import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text, func
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
