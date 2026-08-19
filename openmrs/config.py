import os

from dotenv import load_dotenv

load_dotenv()

OPENMRS_BASE_URL = os.environ.get("OPENMRS_BASE_URL", "").rstrip("/")
OPENMRS_USERNAME = os.environ.get("OPENMRS_USERNAME")
OPENMRS_PASSWORD = os.environ.get("OPENMRS_PASSWORD")
OPENMRS_TIMEOUT_SECONDS = float(os.environ.get("OPENMRS_TIMEOUT_SECONDS", "10"))

# The OpenMRS deployment allowed to call the /openmrs/* endpoints from a
# browser (CORS). An env var, like every other OpenMRS setting here, so
# pointing at a different deployment doesn't need a code change.
OPENMRS_ORIGIN = os.environ.get("OPENMRS_ORIGIN", "https://clearmed.duckdns.org")

def is_configured() -> bool:
	return bool(OPENMRS_BASE_URL and OPENMRS_USERNAME and OPENMRS_PASSWORD)
