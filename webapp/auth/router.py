import logging

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from webapp.auth.deps import get_current_user
from webapp.auth.schemas import UserCreate, UserLogin, UserOut
from webapp.core import config
from webapp.core.database import get_db
from webapp.core.security import create_access_token, hash_password, verify_password
from webapp.folders.service import seed_default_folders
from webapp.users.models import User

logger = logging.getLogger("clearmed.webapp.auth")

router = APIRouter(prefix="/auth", tags=["auth"])


def _normalize_email(email: str) -> str:
	return email.strip().lower()


def _set_auth_cookie(response: Response, user_id: int) -> None:
	token = create_access_token(user_id)
	response.set_cookie(
		key=config.COOKIE_NAME,
		value=token,
		httponly=True,
		secure=config.COOKIE_SECURE,
		samesite="lax",
		max_age=config.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
		path="/",
	)


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)):
	email = _normalize_email(payload.email)

	existing = db.query(User).filter(User.email == email).first()
	if existing is not None:
		raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

	user = User(email=email, password_hash=hash_password(payload.password))
	db.add(user)
	try:
		db.commit()
	except IntegrityError:
		db.rollback()
		raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
	db.refresh(user)

	seed_default_folders(db, user.id)

	logger.info("Registered new user id=%s", user.id)
	return user


@router.post("/login", response_model=UserOut)
def login(payload: UserLogin, response: Response, db: Session = Depends(get_db)):
	email = _normalize_email(payload.email)
	user = db.query(User).filter(User.email == email).first()

	if user is None or not verify_password(payload.password, user.password_hash):
		raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

	_set_auth_cookie(response, user.id)
	logger.info("User id=%s logged in", user.id)
	return user


@router.post("/logout")
def logout(response: Response):
	response.delete_cookie(key=config.COOKIE_NAME, path="/")
	return {"detail": "Logged out"}


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
	return current_user
