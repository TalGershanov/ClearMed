from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from webapp.core.database import Base


class User(Base):
	__tablename__ = "users"

	id: Mapped[int] = mapped_column(primary_key=True)
	# Always stored normalized (stripped + lowercased) by the auth layer;
	# uniqueness is enforced at the DB level on that normalized value.
	email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
	password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
	# Nullable: required at the API layer for every new registration (see
	# webapp/auth/schemas.py::UserCreate), but accounts created before this
	# field existed have no value -- None is a normal, expected state for
	# those, never backfilled with a fabricated name.
	name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
