import os

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Deliberately separate from the root config.py, which only configures the
# read-only ClearMed medical-terms SQLite DB. This module configures the new
# application database (users/folders/documents) and auth, and must never be
# merged with that one.

ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

DATABASE_URL = os.getenv(
	"DATABASE_URL",
	"postgresql+psycopg2://clearmed:clearmed@localhost:5433/clearmed_app",
)

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not JWT_SECRET_KEY:
	raise RuntimeError(
		"JWT_SECRET_KEY environment variable must be set. "
		"Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
	)

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

COOKIE_NAME = "access_token"

# Explicit COOKIE_SECURE env var wins; otherwise default to True only in
# production so local HTTP development keeps working without extra setup.
_cookie_secure_env = os.getenv("COOKIE_SECURE")
if _cookie_secure_env is not None:
	COOKIE_SECURE = _cookie_secure_env.strip().lower() == "true"
else:
	COOKIE_SECURE = ENVIRONMENT == "production"

# The React dev frontend (Vite) runs on a different origin/port than this API,
# so a credentialed cross-origin fetch (cookie-based auth) needs explicit CORS
# allowance. Deliberately an explicit list, never "*" -- a wildcard origin is
# rejected by browsers anyway when allow_credentials is True, and would be
# unsafe even if it weren't.
_cors_origins_env = os.getenv("CORS_ALLOWED_ORIGINS")
if _cors_origins_env:
	CORS_ALLOWED_ORIGINS = [origin.strip() for origin in _cors_origins_env.split(",") if origin.strip()]
else:
	CORS_ALLOWED_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]

# Where webapp/storage's LocalStorageBackend writes uploaded document bytes.
# Deliberately outside static/ (publicly served) and outside appFrontend/.
LOCAL_STORAGE_DIR = os.getenv("LOCAL_STORAGE_DIR", os.path.join(BASE_DIR, "uploads"))

MAX_UPLOAD_SIZE_BYTES = int(os.getenv("MAX_UPLOAD_SIZE_BYTES", str(20 * 1024 * 1024)))
