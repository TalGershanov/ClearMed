import datetime
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
from together import Together  # noqa: E402

from dataset_io import write_json_atomic  # noqa: E402

load_dotenv()

_EXP1_DIR = os.path.join(_REPO_ROOT, "finetuning", "experiments", "experiment1")
TRAIN_FT_FILE = os.path.join(_EXP1_DIR, "data", "train_ft.jsonl")
RESULT_FILE = os.path.join(_EXP1_DIR, "results", "finetune_result_together.json")

BASE_MODEL = "Qwen/Qwen3.5-9B"
SUFFIX = "clearmed-short-explanation"
N_EPOCHS = 3
POLL_SECONDS = 30


def wait_for_file_ready(client, file_id):
	while True:
		meta = client.files.retrieve(file_id)
		if meta.processing_status == "COMPLETED":
			return
		if meta.processing_status == "INVALID_FORMAT":
			raise ValueError(f"file {file_id} rejected: {meta.validation_report}")
		if meta.processing_status == "FAILED":
			raise RuntimeError(f"file {file_id} processing did not complete: {meta.validation_report}")
		time.sleep(5)


def main():
	if not os.environ.get("TOGETHER_API_KEY"):
		print("TOGETHER_API_KEY is not set in the environment. Stopping.")
		sys.exit(1)

	if not os.path.exists(TRAIN_FT_FILE):
		print("Missing train_ft.jsonl. Run finetune_prepare.py first.")
		sys.exit(1)

	client = Together()

	# test_ft.jsonl (the 50 held-out examples) is intentionally never uploaded or
	# referenced here. It must stay a true final test set: not used for training,
	# not used as a Together `validation_file`, not used for hyperparameter selection.
	print(f"Uploading {TRAIN_FT_FILE} ...")
	train_file = client.files.upload(file=TRAIN_FT_FILE, purpose="fine-tune", check=True)
	print(f"  training file id: {train_file.id}")
	wait_for_file_ready(client, train_file.id)

	n_examples = sum(1 for _ in open(TRAIN_FT_FILE, encoding="utf-8"))

	print(f"Creating LoRA fine-tuning job (model={BASE_MODEL}) ...")
	job = client.fine_tuning.create(
		model=BASE_MODEL,
		training_file=train_file.id,
		lora=True,
		n_epochs=N_EPOCHS,
		suffix=SUFFIX,
	)
	print(f"  job id: {job.id}, status: {job.status}")

	seen_event_hashes = set()
	while True:
		job = client.fine_tuning.retrieve(id=job.id)

		events = client.fine_tuning.list_events(id=job.id)
		new_events = [e for e in events.data if e.hash not in seen_event_hashes]
		for e in new_events:
			seen_event_hashes.add(e.hash)
			print(f"  [{e.created_at}] {e.message}")

		if job.status in ("completed", "error", "cancelled"):
			break
		time.sleep(POLL_SECONDS)

	if job.status != "completed":
		print(f"Fine-tuning job ended with status: {job.status}")
		sys.exit(1)

	result = {
		"fine_tuned_model": job.x_model_output_name,
		"job_id": job.id,
		"base_model": BASE_MODEL,
		"training_file_id": train_file.id,
		"n_training_examples": n_examples,
		"finished_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
	}
	write_json_atomic(RESULT_FILE, result)

	print("Fine-tuning succeeded.")
	print(f"  fine_tuned_model: {job.x_model_output_name}")
	print(f"  saved result to {RESULT_FILE}")


if __name__ == "__main__":
	main()
