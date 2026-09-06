import logging
import uuid
from datetime import datetime, timedelta, timezone

from DAL import shares_db
from logic.document_translation import get_disclaimer, translate_document_fields

logger = logging.getLogger("clearmed.document_shares")

SHARE_LIFETIME = timedelta(minutes=5)


class ShareNotFoundError(Exception):
	pass


def create_shared_document(explanation_text: str, explained_terms_list: list[str]) -> str:
	share_id = str(uuid.uuid4())
	now = datetime.now(timezone.utc)
	shares_db.insert_share(
		share_id,
		explanation_text,
		explained_terms_list,
		now.isoformat(),
		(now + SHARE_LIFETIME).isoformat(),
	)
	logger.info(f"created document share {share_id}")
	return share_id


def get_shared_document(share_id: str) -> dict:
	share = shares_db.get_share(share_id)
	if share is None:
		logger.info(f"share {share_id} not found (missing or expired)")
		raise ShareNotFoundError(share_id)
	return share


def translate_shared_document(share_id: str, target_language_code: str) -> dict:
	share = get_shared_document(share_id)
	# The translation is produced on-the-fly and returned directly -- never
	# written back to shares.db or cached anywhere, so translated content
	# never outlives the share's own 5-minute window either.
	translated = translate_document_fields(
		share["explanation_text"], share["explained_terms_list"], target_language_code
	)
	translated["disclaimer"] = get_disclaimer(target_language_code)
	return translated
