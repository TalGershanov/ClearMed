import os

from dotenv import load_dotenv

load_dotenv()

OPENMRS_BASE_URL="https://dev3.openmrs.org/openmrs"
OPENMRS_USERNAME="admin"
OPENMRS_PASSWORD="Admin123"
OPENMRS_TIMEOUT_SECONDS = float(os.environ.get("OPENMRS_TIMEOUT_SECONDS", "10"))

# The OpenMRS deployment allowed to call the /openmrs/* endpoints from a
# browser (CORS). An env var, like every other OpenMRS setting here, so
# pointing at a different deployment doesn't need a code change.
OPENMRS_ORIGIN = os.environ.get("OPENMRS_ORIGIN", "https://clearmed.duckdns.org")

# Concept UUID for the clinical note observation the widget lets a clinician
# pick from and translate. Concept UUIDs are instance-specific (see
# openmrs/README.md) -- left empty until set to the real value for your
# OpenMRS instance's concept dictionary.
OPENMRS_NOTE_CONCEPT_UUID = os.environ.get("OPENMRS_NOTE_CONCEPT_UUID", "")

def is_configured() -> bool:
	return bool(OPENMRS_BASE_URL and OPENMRS_USERNAME and OPENMRS_PASSWORD)
