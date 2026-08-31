"""
Experiment 3: launch the LoRA fine-tuning job on Together.

This is Experiment 2's launcher (finetune_launch_together_experiment2.py) with only
three things changed: the training file, the suffix, and the result output path.
Every training hyperparameter (base model, lora flag, lora_r, n_epochs,
learning_rate, n_evals, upload check behavior) is copied verbatim so the only
variable between Experiment 2 and Experiment 3 is the training data itself.

Training file: finetuning/experiments/experiment3/data/experiment3_train_final.jsonl
(416 rows = Experiment 2's exact 316-row train_final.jsonl, unchanged, plus 100 new
rows from the 50 newly annotated terms + their shuffled twins).

Validation file: intentionally REUSES Experiment 2's own dev.jsonl unchanged (18
unique / 36 rows). Experiment 3's training-data build deliberately excluded these
18 source_ids from the "used" pool it extended, so this file has zero overlap with
Experiment 3's 208-unique training pool -- it is exactly the same held-out
validation set Experiment 2 evaluated against during training, reused rather than
rebuilt so the training/validation split methodology is identical, not just the
hyperparameters. This script only ever READS that file (uploads it by path); it
never writes to anything under experiment2/ or experiment1/.

LoRA alpha, LoRA dropout, batch size, warmup ratio, and train_on_inputs are not
set explicitly here, for the same reason they were not set explicitly in
Experiment 2's launcher: Experiment 2 never specified them, relying on
Together's request-time defaults. Preserving Experiment 2's configuration
"exactly" therefore means not introducing an explicit value here either -- doing
so would risk diverging from whatever default Experiment 2 actually trained
under, which is the opposite of isolating the dataset as the only variable.

Note: the 50-example held-out test set (finetuning/data/splits/test.jsonl) is
intentionally never imported, opened, or referenced anywhere in this file.

Does NOT run on import. Nothing is created, uploaded, or billed until this script
is executed and reaches client.files.upload() / client.fine_tuning.create().

Usage:
    python finetune_launch_together_experiment3.py
"""

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

EXP2_DIR = os.path.join(_REPO_ROOT, "finetuning", "experiments", "experiment2")
EXP3_DIR = os.path.join(_REPO_ROOT, "finetuning", "experiments", "experiment3")

TRAIN_FILE = os.path.join(EXP3_DIR, "data", "experiment3_train_final.jsonl")
# Reused read-only from Experiment 2 -- see module docstring. Never written to.
VALIDATION_FILE = os.path.join(EXP2_DIR, "data", "dev.jsonl")
RESULT_FILE = os.path.join(EXP3_DIR, "results", "finetune_result_together_exp3.json")

# --- Everything below this line is copied verbatim from Experiment 2's launcher,
# --- except SUFFIX. Do not change these independently of a documented reason.
BASE_MODEL = "Qwen/Qwen3.5-9B"
SUFFIX = "clearmed-short-explanation-exp3"
N_EPOCHS = 3
LEARNING_RATE = 1e-5
LORA_R = 8
N_EVALS = 6
POLL_SECONDS = 30

# Identical reasoning as Experiment 2: together==2.9.0's local `files.upload(check=True)`
# pre-check rejects any top-level JSONL column other than "messages"/"tools" for
# conversational format -- it does not yet know about the (documented,
# server-supported) per-sample "weight" field used for our natural (1.0) vs.
# shuffled-twin (0.5) rows. check=False skips that stale local check; the
# server-side schema validation polled below via processing_status is the
# authoritative check and still runs normally.
UPLOAD_CHECK = False


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

	if not os.path.exists(TRAIN_FILE) or not os.path.exists(VALIDATION_FILE):
		print("Missing experiment3_train_final.jsonl / Experiment 2's dev.jsonl. "
		      "Run experiment3_build_training_dataset.py first (and confirm Experiment 2's "
		      "data/dev.jsonl still exists).")
		sys.exit(1)

	client = Together()

	print(f"Uploading {TRAIN_FILE} (check={UPLOAD_CHECK}) ...")
	train_file = client.files.upload(file=TRAIN_FILE, purpose="fine-tune", check=UPLOAD_CHECK)
	print(f"  training file id: {train_file.id}")
	wait_for_file_ready(client, train_file.id)

	print(f"Uploading {VALIDATION_FILE} (check={UPLOAD_CHECK}) ...")
	val_file = client.files.upload(file=VALIDATION_FILE, purpose="fine-tune", check=UPLOAD_CHECK)
	print(f"  validation file id: {val_file.id}")
	wait_for_file_ready(client, val_file.id)

	n_train_examples = sum(1 for _ in open(TRAIN_FILE, encoding="utf-8"))
	n_val_examples = sum(1 for _ in open(VALIDATION_FILE, encoding="utf-8"))

	print(f"Creating LoRA fine-tuning job (model={BASE_MODEL}) ...")
	job = client.fine_tuning.create(
		model=BASE_MODEL,
		training_file=train_file.id,
		validation_file=val_file.id,
		n_evals=N_EVALS,
		lora=True,
		lora_r=LORA_R,
		n_epochs=N_EPOCHS,
		learning_rate=LEARNING_RATE,
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
		"validation_file_id": val_file.id,
		"n_train_examples": n_train_examples,
		"n_val_examples": n_val_examples,
		"n_epochs": N_EPOCHS,
		"learning_rate": LEARNING_RATE,
		"lora_r": LORA_R,
		"n_evals": N_EVALS,
		"suffix": SUFFIX,
		"finished_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
	}
	write_json_atomic(RESULT_FILE, result)

	print("Fine-tuning succeeded.")
	print(f"  fine_tuned_model: {job.x_model_output_name}")
	print(f"  saved result to {RESULT_FILE}")


if __name__ == "__main__":
	main()
