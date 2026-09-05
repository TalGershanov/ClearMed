from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHash, VerifyMismatchError

from webapp.core import config

# argon2-cffi's PasswordHasher defaults to the Argon2id variant.
_password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
	return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
	try:
		return _password_hasher.verify(password_hash, password)
	except (VerifyMismatchError, InvalidHash):
		return False


def create_access_token(user_id: int) -> str:
	now = datetime.now(timezone.utc)
	payload = {
		"sub": str(user_id),
		"iat": now,
		"exp": now + timedelta(minutes=config.ACCESS_TOKEN_EXPIRE_MINUTES),
	}
	return jwt.encode(payload, config.JWT_SECRET_KEY, algorithm=config.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
	return jwt.decode(token, config.JWT_SECRET_KEY, algorithms=[config.JWT_ALGORITHM])
