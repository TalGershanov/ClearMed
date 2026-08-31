import datetime
import json
import os
import sys
import time

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(_THIS_DIR))))
_SERVER_INIT_DIR = os.path.join(_REPO_ROOT, "server_init")
_SHARED_DIR = os.path.join(_REPO_ROOT, "finetuning", "shared")
for _path in (_REPO_ROOT, _SERVER_INIT_DIR, _SHARED_DIR):
	if _path not in sys.path:
		sys.path.insert(0, _path)

from dotenv import load_dotenv  # noqa: E402
from openai import OpenAI  # noqa: E402

from dataset_io import write_json_atomic  # noqa: E402

load_dotenv()

_EXP1_DIR = os.path.join(_REPO_ROOT, "finetuning", "experiments", "experiment1")
TRAIN_FT_FILE = os.path.join(_EXP1_DIR, "data", "train_ft.jsonl")
TEST_FT_FILE = os.path.join(_EXP1_DIR, "data", "test_ft.jsonl")
RESULT_FILE = os.path.join(_EXP1_DIR, "results", "finetune_result.json")

BASE_MODEL = "gpt-4o-mini-2024-07-18"
POLL_SECONDS = 30


def main():
	if not os.environ.get("OPENAI_API_KEY"):
		print("OPENAI_API_KEY is not set in the environment. Stopping.")
		sys.exit(1)

	if not os.path.exists(TRAIN_FT_FILE) or not os.path.exists(TEST_FT_FILE):
		print("Missing train_ft.jsonl / test_ft.jsonl. Run finetune_prepare.py first.")
		sys.exit(1)

	client = OpenAI()

	print(f"Uploading {TRAIN_FT_FILE} ...")
	with open(TRAIN_FT_FILE, "rb") as f:
		train_file = client.files.create(file=f, purpose="fine-tune")
	print(f"  training file id: {train_file.id}")

	print(f"Uploading {TEST_FT_FILE} ...")
	with open(TEST_FT_FILE, "rb") as f:
		val_file = client.files.create(file=f, purpose="fine-tune")
	print(f"  validation file id: {val_file.id}")

	n_examples = sum(1 for _ in open(TRAIN_FT_FILE, encoding="utf-8"))

	print(f"Creating fine-tuning job (model={BASE_MODEL}) ...")
	job = client.fine_tuning.jobs.create(
		model=BASE_MODEL,
		training_file=train_file.id,
		validation_file=val_file.id,
	)
	print(f"  job id: {job.id}, status: {job.status}")

	seen_event_ids = set()
	while True:
		job = client.fine_tuning.jobs.retrieve(job.id)

		events = client.fine_tuning.jobs.list_events(job.id, limit=20)
		new_events = [e for e in reversed(events.data) if e.id not in seen_event_ids]
		for e in new_events:
			seen_event_ids.add(e.id)
			ts = datetime.datetime.fromtimestamp(e.created_at, tz=datetime.timezone.utc).isoformat()
			print(f"  [{ts}] {e.message}")

		if job.status in ("succeeded", "failed", "cancelled"):
			break
		time.sleep(POLL_SECONDS)

	if job.status != "succeeded":
		print(f"Fine-tuning job ended with status: {job.status}")
		print(f"Full job object: {job.model_dump_json(indent=2)}")
		sys.exit(1)

	result = {
		"fine_tuned_model": job.fine_tuned_model,
		"job_id": job.id,
		"base_model": BASE_MODEL,
		"training_file_id": train_file.id,
		"validation_file_id": val_file.id,
		"n_training_examples": n_examples,
		"trained_tokens": job.trained_tokens,
		"created_at": datetime.datetime.fromtimestamp(job.created_at, tz=datetime.timezone.utc).isoformat(),
		"finished_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
	}
	write_json_atomic(RESULT_FILE, result)

	print("Fine-tuning succeeded.")
	print(f"  fine_tuned_model: {job.fine_tuned_model}")
	print(f"  saved result to {RESULT_FILE}")


if __name__ == "__main__":
	main()
