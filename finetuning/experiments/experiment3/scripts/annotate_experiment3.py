"""
Experiment 3: human annotation tool for the 50-example disease/condition-priority batch
selected by experiment3_sample_pool.py.

Same interaction model as annotate.py / annotate_experiment2.py (numbered candidates,
undo/quit, incremental atomic save so progress is never lost), with three differences
specific to Experiment 3:
  - reads the fixed, hand-reviewed selection from candidate_pool_selected_50.json (never
    modified by this script) instead of a difficulty-score queue or a fresh bucket sample.
  - shows the sampling bucket / failure-mode category and domain classification for
    context, and the V7 pick ONLY if it is already sitting in finetuning/data/v7_cache.json
    under a matching content fingerprint. This script never calls V7/OpenAI itself -- no
    API calls are made, no cache entries are written by this tool -- and the V7 pick (when
    shown) is never pre-filled or treated as correct; it is display-only context.
  - collects three fields per example instead of one: best_index (required),
    acceptable_indices (optional, comma-separated, defaults to empty list if left blank),
    and difficulty ("easy" or "hard", required). None of these are inferred automatically.

Writes to data/annotations_batch3.jsonl, so the existing Experiment 1 (annotations.jsonl)
and Experiment 2 (annotations_batch2.jsonl) files are never touched, and the held-out
finetuning/data/splits/test.jsonl is never read or written by this script.

Usage:
    python annotate_experiment3.py            # label new items
    python annotate_experiment3.py --review   # review/correct already-labeled items
"""

import argparse
import datetime
import hashlib
import os
import sys

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(_THIS_DIR))))
_SHARED_DIR = os.path.join(_REPO_ROOT, "finetuning", "shared")
if _SHARED_DIR not in sys.path:
	sys.path.insert(0, _SHARED_DIR)

from dataset_io import load_jsonl, write_jsonl_atomic, load_json  # noqa: E402

EXP3_DIR = os.path.join(_REPO_ROOT, "finetuning", "experiments", "experiment3")
SELECTION_FILE = os.path.join(EXP3_DIR, "data", "candidate_pool_selected_50.json")
ANNOTATIONS_FILE = os.path.join(EXP3_DIR, "data", "annotations_batch3.jsonl")
V7_CACHE_FILE = os.path.join(_REPO_ROOT, "finetuning", "data", "v7_cache.json")

BATCH_NAME = "experiment3_disease_condition_priority"
VALID_DIFFICULTIES = ("easy", "hard")


def fingerprint(sentences):
	joined = "␟".join(sentences)
	return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16]


def get_cached_v7_choice(source_id, sentences, cache):
	"""Read-only lookup. Never calls V7/OpenAI, never writes the cache."""
	cached = cache.get(str(source_id))
	if cached and cached.get("fingerprint") == fingerprint(sentences):
		return cached.get("index"), cached.get("source")
	return None, "not_queried"


def make_record(item, v7_index, v7_source, best_index, acceptable_indices, difficulty):
	return {
		"source_id": item["source_id"],
		"term": item["term"],
		"candidates": item["candidates"],
		"categories": item.get("categories"),
		"domain": item.get("domain"),
		"bucket": item.get("bucket"),
		"candidate_count": item.get("candidate_count"),
		"current_v7_index": v7_index,
		"v7_source": v7_source,
		"best_index": best_index,
		"acceptable_indices": acceptable_indices,
		"difficulty": difficulty,
		"annotated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
		"batch": BATCH_NAME,
	}


def print_item(item, v7_index, v7_source, progress, target):
	print("-" * 60)
	print(f"Progress: {progress} / {target}")
	print()
	print(f"TERM: {item['term']}")
	categories = item.get("categories")
	if categories:
		print(f"Categories: {', '.join(categories)}")
	print(f"Domain: {item.get('domain')}   Bucket (failure-mode category): {item.get('bucket')}")
	print(f"Candidate count: {item.get('candidate_count')}")
	print()
	print("Candidates:")
	for i, s in enumerate(item["candidates"]):
		print(f"[{i}] {s}")
	print()
	if v7_index is not None:
		print(f"V7 selected (context only -- not preselected, not necessarily correct): [{v7_index}]")
	else:
		print(f"V7 selected: unavailable ({v7_source})")
	print()


def prompt_acceptable_indices(n, best_index):
	while True:
		raw = input(
			"Acceptable indices besides the best one, comma-separated (Enter for none): "
		).strip()
		if raw == "":
			return []
		parts = [p.strip() for p in raw.split(",") if p.strip() != ""]
		if all(p.isdigit() and 0 <= int(p) < n for p in parts):
			return sorted({int(p) for p in parts})
		print(f"Invalid input. Enter comma-separated numbers 0-{n - 1}, or leave blank.")


def prompt_difficulty():
	while True:
		raw = input("Difficulty (e=easy / h=hard): ").strip().lower()
		if raw in ("e", "easy"):
			return "easy"
		if raw in ("h", "hard"):
			return "hard"
		print("Invalid input. Enter 'e' for easy or 'h' for hard.")


def run_annotation(pool, annotations, annotated_ids, v7_cache):
	queue = [item for item in pool if str(item["source_id"]) not in annotated_ids]
	if not queue:
		print("No more items to annotate -- batch complete.")
		return

	print(f"{len(annotations)} already labeled in this batch. {len(queue)} remaining.")

	idx = 0
	while idx < len(queue):
		item = queue[idx]
		n = len(item["candidates"])
		v7_index, v7_source = get_cached_v7_choice(item["source_id"], item["candidates"], v7_cache)
		print_item(item, v7_index, v7_source, len(annotations), len(pool))

		try:
			choice = input("Best index (u=undo / q=quit): ").strip().lower()
		except EOFError:
			break

		if choice == "q":
			print("Exiting. All answers so far are saved.")
			break

		if choice == "u":
			if not annotations:
				print("Nothing to undo.")
				continue
			last = annotations.pop()
			write_jsonl_atomic(ANNOTATIONS_FILE, annotations)
			annotated_ids.discard(str(last["source_id"]))
			print(f"Undid annotation for '{last['term']}'.")
			queue.insert(idx, next(p for p in pool if str(p["source_id"]) == str(last["source_id"])))
			continue

		if not choice.isdigit() or not (0 <= int(choice) < n):
			print(f"Invalid input. Enter a number 0-{n - 1}, 'u', or 'q'.")
			continue

		best_index = int(choice)
		acceptable_indices = prompt_acceptable_indices(n, best_index)
		difficulty = prompt_difficulty()

		record = make_record(item, v7_index, v7_source, best_index, acceptable_indices, difficulty)
		annotations.append(record)
		write_jsonl_atomic(ANNOTATIONS_FILE, annotations)
		annotated_ids.add(str(item["source_id"]))
		idx += 1

	print(f"Total labeled in this batch: {len(annotations)} / {len(pool)}")


def run_review(annotations):
	if not annotations:
		print("No annotations to review yet.")
		return

	i = 0
	while i < len(annotations):
		record = annotations[i]
		n = len(record["candidates"])
		print("-" * 60)
		print(f"Reviewing {i + 1} / {len(annotations)}")
		print()
		print(f"TERM: {record['term']}  (domain: {record.get('domain')}, bucket: {record.get('bucket')})")
		print()
		print("Candidates:")
		for j, s in enumerate(record["candidates"]):
			print(f"[{j}] {s}")
		print()
		print(f"Your previous best_index: [{record['best_index']}]")
		print(f"Your previous acceptable_indices: {record.get('acceptable_indices')}")
		print(f"Your previous difficulty: {record.get('difficulty')}")
		if record.get("current_v7_index") is not None:
			print(f"V7 selected: [{record['current_v7_index']}]")
		print()

		try:
			choice = input(
				"Press Enter to keep, type a new best_index to correct, or q to stop: "
			).strip().lower()
		except EOFError:
			break

		if choice == "q":
			break
		if choice == "":
			i += 1
			continue
		if not choice.isdigit() or not (0 <= int(choice) < n):
			print(f"Invalid input. Enter a number 0-{n - 1}, or press Enter, or 'q'.")
			continue

		record["best_index"] = int(choice)
		record["acceptable_indices"] = prompt_acceptable_indices(n, record["best_index"])
		record["difficulty"] = prompt_difficulty()
		record["annotated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
		write_jsonl_atomic(ANNOTATIONS_FILE, annotations)
		print(f"Updated best_index to [{record['best_index']}].")
		i += 1


def main():
	parser = argparse.ArgumentParser(description="ClearMed Experiment 3 annotation tool")
	parser.add_argument("--review", action="store_true", help="Review/correct already-labeled items instead of labeling new ones")
	args = parser.parse_args()

	pool = load_json(SELECTION_FILE, None)
	if pool is None:
		print(f"{SELECTION_FILE} not found. Run experiment3_sample_pool.py first.")
		sys.exit(1)

	annotations = load_jsonl(ANNOTATIONS_FILE)
	annotated_ids = {str(r["source_id"]) for r in annotations}
	v7_cache = load_json(V7_CACHE_FILE, {})

	if args.review:
		run_review(annotations)
	else:
		run_annotation(pool, annotations, annotated_ids, v7_cache)


if __name__ == "__main__":
	main()
