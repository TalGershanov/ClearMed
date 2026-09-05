import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlalchemy.orm import Session

from webapp.auth.deps import get_current_user
from webapp.core.database import get_db
from webapp.documents.schemas import DocumentDetail, DocumentOut, TermSelectionUpdate
from webapp.documents.service import (
	analyse_document,
	delete_document_and_file,
	get_owned_document_or_404,
	save_uploaded_document,
	simplify_document,
	update_term_selection,
)
from webapp.folders.service import get_owned_folder_or_404
from webapp.users.models import User

logger = logging.getLogger("clearmed.webapp.documents")

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
	folder_id: int = Form(...),
	name: Optional[str] = Form(None),
	file: UploadFile = File(...),
	current_user: User = Depends(get_current_user),
	db: Session = Depends(get_db),
):
	# Ownership check doubles as the guard against uploading into another
	# user's folder, or a folder that doesn't exist -- 404 either way.
	get_owned_folder_or_404(db, current_user.id, folder_id)
	return await save_uploaded_document(db, current_user.id, folder_id, name, file)


@router.get("/{document_id}", response_model=DocumentDetail)
def get_document(document_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
	# The only endpoint that returns original_text -- folder listings use
	# the lighter DocumentOut, which never includes it.
	return get_owned_document_or_404(db, current_user.id, document_id)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
	document = get_owned_document_or_404(db, current_user.id, document_id)
	delete_document_and_file(db, document)
	return None


@router.post("/{document_id}/analyse", response_model=DocumentDetail)
def analyse_document_endpoint(
	document_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
	document = get_owned_document_or_404(db, current_user.id, document_id)
	return analyse_document(db, document)


@router.patch("/{document_id}/selection", response_model=DocumentDetail)
def update_selection_endpoint(
	document_id: int,
	payload: TermSelectionUpdate,
	current_user: User = Depends(get_current_user),
	db: Session = Depends(get_db),
):
	document = get_owned_document_or_404(db, current_user.id, document_id)
	return update_term_selection(db, document, payload.term_selection)


@router.post("/{document_id}/simplify", response_model=DocumentDetail)
def simplify_document_endpoint(
	document_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
	document = get_owned_document_or_404(db, current_user.id, document_id)
	return simplify_document(db, document)
