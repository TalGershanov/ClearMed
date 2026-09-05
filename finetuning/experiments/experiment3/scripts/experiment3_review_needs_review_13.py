"""
Experiment 3: simple interactive review tool for ONLY the 13 test-set predictions
that experiment3_reuse_existing_review.py could not classify from any existing
human judgment (provenance == new_manual_review_required in
review/exp3_review_reused_judgments.csv). The other 37 are already resolved and
are never shown here.

For each of the 13, shows just the term and the sentence Experiment 3 selected.
You answer accepted / not accepted. (Note: "correct," i.e. matching the original
human best_index, is not a possible outcome for any of these 13 by definition --
that's exactly why they weren't already auto-resolved -- so a binary
accepted/wrong judgment is equivalent to the earlier three-way scheme for this
specific set of 13.)

Saves after every judgment (atomic write) and resumes: re-running skips any
source_id already present in the output file.

Writes only:
    finetuning/experiments/experiment3/review/exp3_new_judgments_13.jsonl

Does not modify test.jsonl, annotations_batch3.jsonl, or any Experiment 2 file.
Makes no API calls, launches no training.

Usage:
    python experiment3_review_needs_review_13.py
"""

import csv
import datetime
import os
import sys

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(_THIS_DIR))))
_SHARED_DIR = os.path.join(_REPO_ROOT, "finetuning", "shared")
if _SHARED_DIR not in sys.path:
	sys.path.insert(0, _SHARED_DIR)

from dataset_io import load_jsonl, write_jsonl_atomic  # noqa: E402

REUSED_REVIEW_CSV = os.path.join(_REPO_ROOT, "finetuning", "experiments", "experiment3", "review", "exp3_review_reused_judgments.csv")

OUT_FILE = os.path.join(_REPO_ROOT, "finetuning", "experiments", "experiment3", "review", "exp3_new_judgments_13.jsonl")

VERDICT_MAP = {"y": "accepted", "accepted": "accepted", "n": "wrong", "wrong": "wrong"}


def load_needs_review():
	with open(REUSED_REVIEW_CSV, encoding="utf-8") as f:
		rows = list(csv.DictReader(f))
	return [r for r in rows if r["provenance"] == "new_manual_review_required"]


def print_item(item, progress, target):
	print("=" * 70)
	print(f"Progress: {progress} / {target}")
	print()
	print(f"TERM: {item['term']}")
	print()
	print(f"Experiment 3 selected: {item['exp3_selected_sentence']}")
	print()


def run(items, judgments):
	judged_ids = {str(j["source_id"]) for j in judgments}
	queue = [item for item in items if str(item["source_id"]) not in judged_ids]
	if not queue:
		print("All 13 already judged -- nothing left to review.")
		return judgments

	print(f"{len(judgments)} / {len(items)} already judged. {len(queue)} remaining.")

	idx = 0
	while idx < len(queue):
		item = queue[idx]
		print_item(item, len(judgments), len(items))

		try:
			choice = input("Accepted? (y/n, u=undo, q=quit): ").strip().lower()
		except EOFError:
			break

		if choice == "q":
			print("Exiting. All judgments so far are saved.")
			break

		if choice == "u":
			if not judgments:
				print("Nothing to undo.")
				continue
			last = judgments.pop()
			write_jsonl_atomic(OUT_FILE, judgments)
			judged_ids.discard(str(last["source_id"]))
			print(f"Undid judgment for '{last['term']}'.")
			queue.insert(idx, next(i for i in items if str(i["source_id"]) == str(last["source_id"])))
			continue

		if choice not in VERDICT_MAP:
			print("Invalid input. Enter 'y', 'n', 'u', or 'q'.")
			continue

		verdict = VERDICT_MAP[choice]
		judgments.append({
			"source_id": item["source_id"],
			"term": item["term"],
			"exp3_selected_index": int(item["exp3_selected_index"]),
			"human_review": verdict,
			"judged_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
		})
		write_jsonl_atomic(OUT_FILE, judgments)
		judged_ids.add(str(item["source_id"]))
		idx += 1

	print(f"Total judged: {len(judgments)} / {len(items)}")
	return judgments


def main():
	items = load_needs_review()
	if len(items) != 13:
		print(f"Expected 13 needs_review items, found {len(items)}. Check {REUSED_REVIEW_CSV}.")

	judgments = load_jsonl(OUT_FILE)
	run(items, judgments)


if __name__ == "__main__":
	main()
