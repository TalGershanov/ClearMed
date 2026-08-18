import argparse
import os
import random
import sys

_ANNOTATION_DIR = os.path.dirname(os.path.abspath(__file__))
if _ANNOTATION_DIR not in sys.path:
	sys.path.insert(0, _ANNOTATION_DIR)

from dataset_io import load_jsonl, write_jsonl_atomic  # noqa: E402

DATA_DIR = os.path.join(_ANNOTATION_DIR, "data")
ANNOTATIONS_FILE = os.path.join(DATA_DIR, "annotations.jsonl")
SPLITS_DIR = os.path.join(DATA_DIR, "splits")


def v7_accuracy(records):
	scored = [r for r in records if r.get("current_v7_index") is not None]
	if not scored:
		return None
	correct = sum(1 for r in scored if r["current_v7_index"] == r["selected_index"])
	return correct, len(scored)


def print_accuracy(label, records):
	result = v7_accuracy(records)
	if result is None:
		print(f"  {label}: no V7 comparisons available")
		return
	correct, total = result
	print(f"  {label}: V7 agreement {correct}/{total} = {correct / total:.1%}")


def main():
	parser = argparse.ArgumentParser(description="Deterministic train/test split for the ClearMed annotation dataset")
	parser.add_argument("--test-size", type=int, default=50, help="Number of held-out test examples")
	parser.add_argument("--seed", type=int, default=42, help="Shuffle seed, kept fixed for reproducibility")
	parser.add_argument("--stats-only", action="store_true", help="Only print V7 agreement stats; do not write split files")
	args = parser.parse_args()

	records = load_jsonl(ANNOTATIONS_FILE)
	if not records:
		print("No annotations found yet. Run annotate.py first.")
		return

	print(f"Total annotations: {len(records)}")
	print_accuracy("overall", records)

	if args.stats_only:
		return

	if len(records) <= args.test_size:
		print(f"Not enough annotations ({len(records)}) for a held-out set of {args.test_size}; skipping split.")
		return

	# Shuffle a copy with a fixed seed; the raw annotations.jsonl file is never modified.
	shuffled = records[:]
	random.Random(args.seed).shuffle(shuffled)
	test = shuffled[: args.test_size]
	train = shuffled[args.test_size :]

	write_jsonl_atomic(os.path.join(SPLITS_DIR, "train.jsonl"), train)
	write_jsonl_atomic(os.path.join(SPLITS_DIR, "test.jsonl"), test)

	print(f"Wrote {len(train)} train / {len(test)} test examples to {SPLITS_DIR}")
	print_accuracy("train", train)
	print_accuracy("test", test)


if __name__ == "__main__":
	main()
