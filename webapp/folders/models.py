from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from webapp.core.database import Base


class Folder(Base):
	__tablename__ = "folders"

	id: Mapped[int] = mapped_column(primary_key=True)
	# Ownership is always assigned server-side from the authenticated user
	# (see webapp/auth/deps.py::get_current_user); never trust a user_id
	# supplied by a client. Deleting a user deletes their folders (no
	# user-deletion endpoint exists yet, but this is the correct ownership
	# semantic).
	user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
	name: Mapped[str] = mapped_column(String(255), nullable=False)
	# Self-referencing parent. ondelete="RESTRICT" is a DB-level backstop
	# behind the application-level "block delete while it has children"
	# check in webapp/folders/service.py -- defense in depth, not a
	# replacement for that check (SQLite in tests doesn't enforce this).
	parent_folder_id: Mapped[Optional[int]] = mapped_column(
		ForeignKey("folders.id", ondelete="RESTRICT"), nullable=True, index=True
	)
	color: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
	# Metadata/path only for now -- no image upload/storage implemented yet.
	cover_image_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
	updated_at: Mapped[datetime] = mapped_column(
		DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
	)

	parent: Mapped[Optional["Folder"]] = relationship("Folder", back_populates="children", remote_side=[id])
	children: Mapped[list["Folder"]] = relationship(
		"Folder", back_populates="parent", order_by="Folder.created_at"
	)
