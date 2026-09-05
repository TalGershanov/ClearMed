import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from webapp.auth.deps import get_current_user
from webapp.core.database import get_db
from webapp.documents.models import Document
from webapp.documents.service import list_documents_in_folder
from webapp.folders.models import Folder
from webapp.folders.schemas import FolderCreate, FolderDetail, FolderOut, FolderUpdate
from webapp.folders.service import get_owned_folder_or_404, would_create_cycle
from webapp.users.models import User

logger = logging.getLogger("clearmed.webapp.folders")

router = APIRouter(prefix="/folders", tags=["folders"])


@router.get("", response_model=list[FolderOut])
def list_root_folders(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
	return (
		db.query(Folder)
		.filter(Folder.user_id == current_user.id, Folder.parent_folder_id.is_(None))
		.order_by(Folder.created_at)
		.all()
	)


@router.get("/{folder_id}", response_model=FolderDetail)
def get_folder(folder_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
	folder = get_owned_folder_or_404(db, current_user.id, folder_id)
	documents = list_documents_in_folder(db, folder.id)
	return FolderDetail(
		id=folder.id,
		name=folder.name,
		parent_folder_id=folder.parent_folder_id,
		color=folder.color,
		cover_image_path=folder.cover_image_path,
		created_at=folder.created_at,
		updated_at=folder.updated_at,
		children=folder.children,
		documents=documents,
	)


@router.post("", response_model=FolderOut, status_code=status.HTTP_201_CREATED)
def create_folder(payload: FolderCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
	if payload.parent_folder_id is not None:
		# Ownership check doubles as the guard against creating a child
		# under another user's folder -- 404 either way.
		get_owned_folder_or_404(db, current_user.id, payload.parent_folder_id)

	folder = Folder(
		user_id=current_user.id,
		name=payload.name,
		parent_folder_id=payload.parent_folder_id,
		color=payload.color,
		cover_image_path=payload.cover_image_path,
	)
	db.add(folder)
	db.commit()
	db.refresh(folder)

	logger.info("User id=%s created folder id=%s", current_user.id, folder.id)
	return folder


@router.patch("/{folder_id}", response_model=FolderOut)
def update_folder(
	folder_id: int,
	payload: FolderUpdate,
	current_user: User = Depends(get_current_user),
	db: Session = Depends(get_db),
):
	folder = get_owned_folder_or_404(db, current_user.id, folder_id)
	update_data = payload.model_dump(exclude_unset=True)

	if "parent_folder_id" in update_data:
		new_parent_id = update_data["parent_folder_id"]
		if new_parent_id is not None:
			# Same ownership check as create -- also blocks reparenting
			# under another user's folder.
			get_owned_folder_or_404(db, current_user.id, new_parent_id)
			if new_parent_id == folder.id:
				raise HTTPException(
					status_code=status.HTTP_400_BAD_REQUEST,
					detail="A folder cannot be its own parent",
				)
			if would_create_cycle(db, folder.id, new_parent_id):
				raise HTTPException(
					status_code=status.HTTP_400_BAD_REQUEST,
					detail="Cannot move a folder under one of its own descendants",
				)
		folder.parent_folder_id = new_parent_id

	if "name" in update_data:
		folder.name = update_data["name"]
	if "color" in update_data:
		folder.color = update_data["color"]
	if "cover_image_path" in update_data:
		folder.cover_image_path = update_data["cover_image_path"]

	db.commit()
	db.refresh(folder)

	logger.info("User id=%s updated folder id=%s", current_user.id, folder.id)
	return folder


@router.delete("/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_folder(folder_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
	folder = get_owned_folder_or_404(db, current_user.id, folder_id)

	has_children = db.query(Folder.id).filter(Folder.parent_folder_id == folder.id).first() is not None
	if has_children:
		raise HTTPException(
			status_code=status.HTTP_409_CONFLICT,
			detail="Folder contains subfolders; delete or move them first",
		)

	has_documents = db.query(Document.id).filter(Document.folder_id == folder.id).first() is not None
	if has_documents:
		raise HTTPException(
			status_code=status.HTTP_409_CONFLICT,
			detail="Folder contains documents; delete or move them first",
		)

	db.delete(folder)
	db.commit()
	logger.info("User id=%s deleted folder id=%s", current_user.id, folder_id)
	return None
