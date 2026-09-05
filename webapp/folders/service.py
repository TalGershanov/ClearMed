from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from webapp.folders.models import Folder

DEFAULT_FOLDER_NAMES = ["Lab Results", "Imaging", "Prescriptions", "Surgery", "General"]


def get_owned_folder_or_404(db: Session, user_id: int, folder_id: int) -> Folder:
	"""The single ownership gate used by every folder endpoint. A folder that
	exists but belongs to a different user is indistinguishable from a folder
	that doesn't exist -- 404 either way, never 403, to avoid leaking which
	folder ids exist for other users. user_id must always come from
	get_current_user, never from a request body/query param."""
	folder = db.get(Folder, folder_id)
	if folder is None or folder.user_id != user_id:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")
	return folder


def would_create_cycle(db: Session, folder_id: int, new_parent_id: int) -> bool:
	"""True if setting folder_id's parent to new_parent_id would create a
	cycle -- i.e. new_parent_id is folder_id itself or one of its
	descendants. Walks up from new_parent_id toward the root rather than
	down from folder_id, since the ancestor chain is the shorter walk."""
	current_id: Optional[int] = new_parent_id
	while current_id is not None:
		if current_id == folder_id:
			return True
		parent = db.get(Folder, current_id)
		current_id = parent.parent_folder_id if parent is not None else None
	return False


def seed_default_folders(db: Session, user_id: int) -> None:
	"""Creates the default root folders for a user. Idempotent: only runs if
	the user currently has zero folders, so it's safe to call both at
	registration time and from a one-time backfill migration for users
	created before this feature existed."""
	existing = db.query(Folder.id).filter(Folder.user_id == user_id).first()
	if existing is not None:
		return

	for name in DEFAULT_FOLDER_NAMES:
		db.add(Folder(user_id=user_id, name=name, parent_folder_id=None))
	db.commit()
