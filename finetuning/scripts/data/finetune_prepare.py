import json
import os
import sys

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(_THIS_DIR)))
_SERVER_INIT_DIR = os.path.join(_REPO_ROOT, "server_init")
_SHARED_DIR = os.path.join(_REPO_ROOT, "finetuning", "shared")
for _path in (_REPO_ROOT, _SERVER_INIT_DIR, _SHARED_DIR):
	if _path not in sys.path:
		sys.path.insert(0, _path)

from ai_services import _SYSTEM_PROMPT  # noqa: E402

from dataset_io import load_jsonl, write_jsonl_atomic, write_json_atomic  # noqa: E402

DATA_DIR = os.path.join(_REPO_ROOT, "finetuning", "data")
TRAIN_FILE = os.path.join(DATA_DIR, "splits", "train.jsonl")
TEST_FILE = os.path.join(DATA_DIR, "splits", "test.jsonl")

EXP1_DIR = os.path.join(_REPO_ROOT, "finetuning", "experiments", "experiment1")
TRAIN_FT_FILE = os.path.join(EXP1_DIR, "data", "train_ft.jsonl")
TEST_FT_FILE = os.path.join(EXP1_DIR, "data", "test_ft.jsonl")
BASELINE_FILE = os.path.join(EXP1_DIR, "results", "baseline_result.json")


def user_prompt_for(record):
	return (
		"Term: " + (record.get("term") or "") + "\n"
		"Candidate sentences (respond with the index of exactly one):\n"
		+ "\n".join(f"{i}: {s}" for i, s in enumerate(record["candidates"]))
	)


def to_chat_example(record):
	return {
		"messages": [
			{"role": "system", "content": _SYSTEM_PROMPT},
			{"role": "user", "content": user_prompt_for(record)},
			{"role": "assistant", "content": json.dumps({"selected_index": record["selected_index"]})},
		]
	}


def compute_baseline(test_records):
	correct = sum(1 for r in test_records if r.get("current_v7_index") == r.get("selected_index"))
	total = len(test_records)
	return correct, total


def main():
	train_records = load_jsonl(TRAIN_FILE)
	test_records = load_jsonl(TEST_FILE)

	if not train_records or not test_records:
		print("train.jsonl / test.jsonl not found or empty; run split_dataset.py first.")
		return

	# Step 0: honest baseline on the held-out 50, not the full 181-example set.
	correct, total = compute_baseline(test_records)
	accuracy = correct / total
	print(f"Step 0 - V7 baseline on held-out test.jsonl: {correct}/{total} = {accuracy:.1%}")
	write_json_atomic(BASELINE_FILE, {
		"correct": correct,
		"total": total,
		"accuracy": accuracy,
	})

	# Step 1: build OpenAI chat fine-tuning files, reusing the exact production prompt.
	train_ft = [to_chat_example(r) for r in train_records]
	test_ft = [to_chat_example(r) for r in test_records]
	write_jsonl_atomic(TRAIN_FT_FILE, train_ft)
	write_jsonl_atomic(TEST_FT_FILE, test_ft)
	print(f"Step 1 - wrote {len(train_ft)} training examples to {TRAIN_FT_FILE}")
	print(f"Step 1 - wrote {len(test_ft)} validation examples to {TEST_FT_FILE}")


if __name__ == "__main__":
	main()
