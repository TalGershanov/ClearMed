"""
Builds a SEPARATE clearmed_finetuned.db that uses the Experiment 3 fine-tuned
Together AI model to pick each term's short_explanation, instead of v7
(OpenAI gpt-4o-mini). This script never opens or writes clearmed.db (the live
v7-built database) -- it only ever touches clearmed_finetuned.db, so the
current production DB is never at risk of being modified or lost. Rollback
is therefore always trivial: keep serving clearmed.db (nothing about it ever
changed) and delete/ignore clearmed_finetuned.db if the fine-tuned model
doesn't work out.

Resumable by construction, not by memory: every concept is committed to
clearmed_finetuned.db the instant it's inserted (one sqlite commit per term,
not one big transaction for the whole run), and re-running this script skips
any concept_id whose 'en' explanation already exists in the target DB. So a
crash, an interrupt, or a lost Claude/session context loses at most the one
term that was in flight -- never anything already written. The ground truth
for "where did it stop" is always:
  - clearmed_finetuned.db itself: sqlite3 clearmed_finetuned.db \
      "SELECT COUNT(*) FROM explanations WHERE language_code='en';"
  - server_init/finetuned_build_status.json, rewritten every 10 terms

Manages the Together AI dedicated endpoint's full lifecycle (create -> wait
READY -> run -> stop) via a try/finally, so the endpoint is always torn down
-- and billing stopped -- even if this script crashes or is interrupted
mid-run. Reuses (does not reimplement) experiment3_deploy_evaluate_stop.py's
create_endpoint_and_deployment / wait_ready / stop_deployment_and_verify, the
same functions Experiment 3's own evaluation run used, so this is the exact
same deploy/stop mechanics already proven there.

Usage:
    python server_init/build_finetuned_db.py
"""

import logging
import os
import sys
import time

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_THIS_DIR)

# Must happen before importing config/db_operations/DAL/ai_services below --
# those modules read CLEARMED_DB_FILE / SHORT_EXPLANATION_SELECTOR at import
# time, so setting these afterwards would silently have no effect.
FINETUNED_DB_FILE = os.path.join(_REPO_ROOT, "clearmed_finetuned.db")
os.environ["CLEARMED_DB_FILE"] = FINETUNED_DB_FILE
os.environ["SHORT_EXPLANATION_SELECTOR"] = "finetuned"

_EXP3_SCRIPTS_DIR = os.path.join(_REPO_ROOT, "finetuning", "experiments", "experiment3", "scripts")
_EXP2_SCRIPTS_DIR = os.path.join(_REPO_ROOT, "finetuning", "experiments", "experiment2", "scripts")
_SHARED_DIR = os.path.join(_REPO_ROOT, "finetuning", "shared")
_DATA_SCRIPTS_DIR = os.path.join(_REPO_ROOT, "finetuning", "scripts", "data")
for _path in (_REPO_ROOT, _THIS_DIR, _EXP3_SCRIPTS_DIR, _EXP2_SCRIPTS_DIR, _SHARED_DIR, _DATA_SCRIPTS_DIR):
	if _path not in sys.path:
		sys.path.insert(0, _path)

from dotenv import load_dotenv  # noqa: E402
load_dotenv()

from config import DB_FILE, PRIMARY_LANGUAGE_CODE, SUPPORTED_LANGUAGES  # noqa: E402
from db_operations import reset_and_create_schema, concept_exists, run_smoke_check  # noqa: E402
from DAL.db import SQLiteDatabase  # noqa: E402
from ai_services import select_short_explanation_ai  # noqa: E402
from build_db import _load_terms, _populate_secondary_language  # noqa: E402
from dataset_io import write_json_atomic  # noqa: E402
import experiment3_deploy_evaluate_stop as exp3  # noqa: E402

assert DB_FILE == FINETUNED_DB_FILE, (
	"DB_FILE did not pick up CLEARMED_DB_FILE -- refusing to run, "
	"since that would mean this script is about to write to clearmed.db."
)

logger = logging.getLogger("clearmed.server_init.build_finetuned_db")

STATUS_FILE = os.path.join(_THIS_DIR, "finetuned_build_status.json")


def _write_status(**fields):
	write_json_atomic(STATUS_FILE, {"updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"), **fields})


def _populate_primary_resumable(json_file_path, model_name):
	terms = _load_terms(json_file_path)
	total = len(terms)
	dal = SQLiteDatabase()
	connection = dal._get_connection()
	newly_done = 0
	already_present = 0
	try:
		for index, item in enumerate(terms, start=1):
			concept_id = item.get("source_id")
			if concept_exists(connection, concept_id, PRIMARY_LANGUAGE_CODE):
				already_present += 1
				continue

			simple_explanation = item.get("simple_explanation")
			term = item.get("term")
			# ai_services.select_short_explanation_ai() reads SHORT_EXPLANATION_SELECTOR
			# / TOGETHER_FINETUNED_MODEL from the environment (both set above/by main()),
			# so this call goes to the fine-tuned Together model, not v7.
			short_explanation = select_short_explanation_ai(simple_explanation, term=term)
			synonyms = item.get("synonyms", [])
			dal.insert_concept(
				concept_id=concept_id,
				categories=item.get("categories", []),
				explanations=[{
					"language_code": PRIMARY_LANGUAGE_CODE,
					"term_name": term,
					"simple_explanation": simple_explanation,
					"short_explanation": short_explanation,
				}],
				aliases=[
					{"alias_text": term, "language_code": PRIMARY_LANGUAGE_CODE},
					*({"alias_text": s, "language_code": PRIMARY_LANGUAGE_CODE} for s in synonyms),
				],
				connection=connection,
			)
			connection.commit()  # per-term commit: a crash loses at most this one term
			newly_done += 1

			if index % 10 == 0 or index == total:
				logger.info(
					"Primary (finetuned): %d/%d processed (%d newly written this run, %d already present)",
					index, total, newly_done, already_present,
				)
				_write_status(
					phase="primary", model=model_name, processed=index, total=total,
					newly_written_this_run=newly_done, already_present=already_present,
				)
	finally:
		connection.close()

	print(
		f"Primary language done. Newly written this run: {newly_done}, "
		f"already present (resumed past): {already_present}, total terms: {total}"
	)
	if terms:
		run_smoke_check(terms[0])


def build_finetuned_database():
	if not os.environ.get("DEEPL_API_KEY"):
		raise SystemExit("DEEPL_API_KEY is not set in the environment. Stopping before the English seed.")
	if not os.environ.get("TOGETHER_API_KEY"):
		raise SystemExit("TOGETHER_API_KEY is not set in the environment. Stopping.")

	fresh_build = not os.path.exists(FINETUNED_DB_FILE)
	if fresh_build:
		logger.info("No existing %s -- creating schema fresh.", FINETUNED_DB_FILE)
		reset_and_create_schema()
	else:
		logger.info("Found existing %s -- resuming (already-present concepts are skipped).", FINETUNED_DB_FILE)

	_write_status(phase="starting_endpoint")
	project_id, endpoint_id, deployment_id, endpoint_name = exp3.create_endpoint_and_deployment()
	os.environ["TOGETHER_FINETUNED_MODEL"] = endpoint_name
	try:
		exp3.wait_ready(project_id, endpoint_id, deployment_id)

		_write_status(phase="primary_starting", model=endpoint_name)
		_populate_primary_resumable(SUPPORTED_LANGUAGES[PRIMARY_LANGUAGE_CODE], endpoint_name)

		for language_code, json_file_path in SUPPORTED_LANGUAGES.items():
			if language_code == PRIMARY_LANGUAGE_CODE:
				continue
			_write_status(phase=f"secondary_{language_code}", model=endpoint_name)
			_populate_secondary_language(language_code, json_file_path)

		_write_status(phase="done", model=endpoint_name)
		print(f"Finetuned database build complete: {FINETUNED_DB_FILE}")
		print(f"clearmed.db (v7, live) was never opened by this script -- nothing to roll back there.")
	finally:
		_write_status(phase="stopping_endpoint")
		exp3.stop_deployment_and_verify(project_id, endpoint_id, deployment_id)
		_write_status(phase="endpoint_stopped")


if __name__ == "__main__":
	from log_config import setup_logging
	setup_logging()
	build_finetuned_database()
