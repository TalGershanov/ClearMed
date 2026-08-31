"""
Phase 1, step 2: human annotation tool for the Experiment 2 distribution-correction batch.

Same interaction model as annotate.py (term, numbered candidates, pick one index,
undo/quit, incremental atomic save so progress is never lost) but:
  - reads the fixed, bucket-stratified pool from experiment2_sample_pool.py instead of
    the difficulty-score queue, so this batch's length distribution is NOT re-skewed
    toward hard/long examples.
  - writes to a separate file (data/experiment2/annotations_batch2.jsonl), so the
    existing Experiment 1 annotations.jsonl is never touched.
  - does not call any AI model for a "V7 pick" -- no OpenAI or Together calls are made
    by this tool. Your selection is the only ground truth recorded.

Usage:
    python annotate_experiment2.py            # label new items
    python annotate_experiment2.py --review   # review/correct already-labeled items
"""

import argparse
import datetime
import os
import sys

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(_THIS_DIR))))
_SHARED_DIR = os.path.join(_REPO_ROOT, "finetuning", "shared")
if _SHARED_DIR not in sys.path:
	sys.path.insert(0, _SHARED_DIR)

from dataset_io import load_jsonl, write_jsonl_atomic, load_json  # noqa: E402

EXP2_DIR = os.path.join(_REPO_ROOT, "finetuning", "experiments", "experiment2")
POOL_FILE = os.path.join(EXP2_DIR, "data", "candidate_pool.json")
ANNOTATIONS_FILE = os.path.join(EXP2_DIR, "data", "annotations_batch2.jsonl")

BATCH_NAME = "experiment2_distribution_correction"


def make_record(item, selected_index):
	return {
		"source_id": item["source_id"],
		"term": item["term"],
		"candidates": item["candidates"],
		"simple_explanation": item["simple_explanation"],
		"current_v7_index": None,
		"v7_source": "not_queried",
		"selected_index": selected_index,
		"agrees_with_v7": None,
		"annotated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
		"batch": BATCH_NAME,
		"candidate_count_bucket": item["candidate_count_bucket"],
	}


def print_item(item, progress, target):
	print("-" * 60)
	print(f"Progress: {progress} / {target}")
	print()
	print(f"TERM: {item['term']}")
	print(f"Candidate count: {item['candidate_count']}  (bucket: {item['candidate_count_bucket']})")
	print()
	print("Candidates:")
	for i, s in enumerate(item["candidates"]):
		print(f"[{i}] {s}")
	print()


def run_annotation(pool, annotations, annotated_ids):
	queue = [item for item in pool if str(item["source_id"]) not in annotated_ids]
	if not queue:
		print("No more items to annotate -- batch complete.")
		return

	print(f"{len(annotations)} already labeled in this batch. {len(queue)} remaining.")

	idx = 0
	while idx < len(queue):
		item = queue[idx]
		print_item(item, len(annotations), len(pool))

		try:
			choice = input("Your choice (index / u=undo / q=quit): ").strip().lower()
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

		n = len(item["candidates"])
		if not choice.isdigit() or not (0 <= int(choice) < n):
			print(f"Invalid input. Enter a number 0-{n - 1}, 'u', or 'q'.")
			continue

		selected_index = int(choice)
		record = make_record(item, selected_index)
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
		print("-" * 60)
		print(f"Reviewing {i + 1} / {len(annotations)}")
		print()
		print(f"TERM: {record['term']}  (bucket: {record.get('candidate_count_bucket')})")
		print()
		print("Candidates:")
		for j, s in enumerate(record["candidates"]):
			print(f"[{j}] {s}")
		print()
		print(f"Your previous choice: [{record['selected_index']}]")
		print()

		try:
			choice = input("Press Enter to keep, type a new index to correct, or q to stop: ").strip().lower()
		except EOFError:
			break

		if choice == "q":
			break
		if choice == "":
			i += 1
			continue
		if not choice.isdigit() or not (0 <= int(choice) < len(record["candidates"])):
			print(f"Invalid input. Enter a number 0-{len(record['candidates']) - 1}, or press Enter, or 'q'.")
			continue

		record["selected_index"] = int(choice)
		record["annotated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
		write_jsonl_atomic(ANNOTATIONS_FILE, annotations)
		print(f"Updated selection to [{record['selected_index']}].")
		i += 1


def main():
	parser = argparse.ArgumentParser(description="ClearMed Experiment 2 distribution-correction annotation tool")
	parser.add_argument("--review", action="store_true", help="Review/correct already-labeled items instead of labeling new ones")
	args = parser.parse_args()

	pool = load_json(POOL_FILE, None)
	if pool is None:
		print(f"{POOL_FILE} not found. Run experiment2_sample_pool.py first.")
		sys.exit(1)

	annotations = load_jsonl(ANNOTATIONS_FILE)
	annotated_ids = {str(r["source_id"]) for r in annotations}

	if args.review:
		run_review(annotations)
	else:
		run_annotation(pool, annotations, annotated_ids)


if __name__ == "__main__":
	main()
