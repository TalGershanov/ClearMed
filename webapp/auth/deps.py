import jwt
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from webapp.core import config
from webapp.core.database import get_db
from webapp.core.security import decode_access_token
from webapp.users.models import User


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
	"""Resolves the authenticated user strictly from the HttpOnly JWT cookie.
	This is the only place identity is derived server-side; callers must never
	accept a user id supplied by the client to authorize access."""
	token = request.cookies.get(config.COOKIE_NAME)
	if not token:
		raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

	try:
		payload = decode_access_token(token)
		user_id = int(payload["sub"])
	except (jwt.PyJWTError, KeyError, ValueError, TypeError):
		raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session")

	user = db.get(User, user_id)
	if user is None:
		raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session")

	return user
