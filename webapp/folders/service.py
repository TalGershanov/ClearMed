from typing import Optional, Sequence

from fastapi import HTTPException, status
from sqlalchemy import literal, func
from sqlalchemy.orm import Session

from webapp.documents.models import Document
from webapp.documents.service import delete_document_and_file
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


def count_documents_by_folder_ids(db: Session, folder_ids: Sequence[int]) -> dict[int, int]:
	"""Direct documents only -- never recursive into child folders, matching
	FolderDetail.documents' own semantics. One grouped query for however many
	folder ids are passed, so a folder *listing* (root folders, or a folder's
	children) never issues one count query per folder. A folder id with zero
	documents is simply absent from the result -- callers must default to 0."""
	if not folder_ids:
		return {}
	rows = (
		db.query(Document.folder_id, func.count(Document.id))
		.filter(Document.folder_id.in_(folder_ids))
		.group_by(Document.folder_id)
		.all()
	)
	return {folder_id: count for folder_id, count in rows}


def count_documents_in_folder(db: Session, folder_id: int) -> int:
	"""Single-folder convenience wrapper -- used where only one folder's own
	count is needed (create/update responses), never in a loop over a list."""
	return db.query(Document.id).filter(Document.folder_id == folder_id).count()


def get_folder_subtree(db: Session, root_folder_id: int) -> list[tuple[int, int]]:
	"""Returns (folder_id, depth) for root_folder_id and every descendant,
	depth 0 for the root itself and increasing with each level down. One
	recursive query regardless of subtree size or depth -- never a query per
	folder. The tree can't contain cycles (would_create_cycle blocks that at
	reparent time), so this always terminates."""
	base = db.query(Folder.id.label("id"), literal(0).label("depth")).filter(Folder.id == root_folder_id).cte(
		name="folder_subtree", recursive=True
	)
	children = db.query(Folder.id.label("id"), (base.c.depth + 1).label("depth")).join(
		base, Folder.parent_folder_id == base.c.id
	)
	subtree = base.union_all(children)
	return [(row.id, row.depth) for row in db.query(subtree.c.id, subtree.c.depth).all()]


def count_folder_subtree_contents(db: Session, root_folder_id: int) -> tuple[int, int]:
	"""(document_count, subfolder_count) for everything inside root_folder_id
	-- root's own direct documents included, subfolder_count excludes the
	root itself. Used to show the user an accurate impact before a cascading
	delete, never to display the (deliberately direct-only) folder-card
	badge (see count_documents_by_folder_ids)."""
	subtree = get_folder_subtree(db, root_folder_id)
	folder_ids = [folder_id for folder_id, _ in subtree]
	document_count = db.query(Document.id).filter(Document.folder_id.in_(folder_ids)).count()
	return document_count, len(folder_ids) - 1


def delete_folder_recursive(db: Session, root_folder: Folder) -> None:
	"""Permanently deletes root_folder, every descendant folder, and every
	document (DB row + stored file) anywhere in that subtree. Only ever
	called when the caller explicitly opted into cascading delete (see
	?recursive=true on DELETE /folders/{id} in webapp/folders/router.py) --
	the default there stays the safe 409-on-non-empty block.

	Reuses delete_document_and_file for every document, exactly the same
	function the plain document-delete endpoint uses -- never a second,
	duplicated file-cleanup path."""
	subtree = get_folder_subtree(db, root_folder.id)
	folder_ids = [folder_id for folder_id, _ in subtree]

	documents = db.query(Document).filter(Document.folder_id.in_(folder_ids)).all()
	for document in documents:
		delete_document_and_file(db, document)

	# Deepest folders first -- Folder.parent_folder_id's ondelete="RESTRICT"
	# FK means a folder can never be deleted while it still has a child row,
	# so children must always go before their parent.
	for folder_id, _depth in sorted(subtree, key=lambda pair: pair[1], reverse=True):
		folder = db.get(Folder, folder_id)
		if folder is not None:
			db.delete(folder)
			db.commit()


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
