"""
Phase 2: build the Experiment 2 augmented training dataset.

Steps:
  1. Combine the 131 Experiment 1 training examples (splits/train.jsonl) with the
     newly labeled Experiment 2 distribution-correction batch
     (experiment2/annotations_batch2.jsonl) into one unique human-labeled pool.
  2. Generate exactly one shuffled twin per unique example: candidate order is
     permuted, sentence text is never touched, selected_index is recomputed to
     point at the same sentence, weight=0.5 (natural stays weight=1.0).
  3. Combine into the full augmented training set.
  4. Run a full audit (counts, index-0 rate, index distribution, candidate-count
     distribution) for natural / shuffled / combined, plus integrity checks
     (pairing, no leakage into the held-out test set, no accidental duplicates).
  5. Propose (but do NOT create) a dev/validation split.

Writes only into finetuning/experiments/experiment2/data/ -- never touches
annotations.jsonl, splits/train.jsonl, splits/test.jsonl, or anything under
finetuning/experiments/experiment1/.

Usage:
    python experiment2_build_augmented_dataset.py
"""

import os
import random
import sys
from collections import Counter

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(_THIS_DIR))))
_SHARED_DIR = os.path.join(_REPO_ROOT, "finetuning", "shared")
if _SHARED_DIR not in sys.path:
	sys.path.insert(0, _SHARED_DIR)

from dataset_io import load_jsonl, write_jsonl_atomic, write_json_atomic  # noqa: E402

DATA_DIR = os.path.join(_REPO_ROOT, "finetuning", "data")
TRAIN_FILE = os.path.join(DATA_DIR, "splits", "train.jsonl")
TEST_FILE = os.path.join(DATA_DIR, "splits", "test.jsonl")

EXP2_DIR = os.path.join(_REPO_ROOT, "finetuning", "experiments", "experiment2")
BATCH2_FILE = os.path.join(EXP2_DIR, "data", "annotations_batch2.jsonl")

NATURAL_FILE = os.path.join(EXP2_DIR, "data", "training_pool_natural.jsonl")
SHUFFLED_FILE = os.path.join(EXP2_DIR, "data", "training_pool_shuffled.jsonl")
AUGMENTED_FILE = os.path.join(EXP2_DIR, "data", "train_augmented.jsonl")
REPORT_FILE = os.path.join(EXP2_DIR, "results", "phase2_construction_report.json")

SEED = 42
DEV_SPLIT_PROPOSED_SIZE = 18


def bucket_of(n_candidates):
	if n_candidates <= 5:
		return "<=5"
	if n_candidates <= 10:
		return "6-10"
	if n_candidates <= 20:
		return "11-20"
	if n_candidates <= 40:
		return "21-40"
	return ">40"


def build_natural_pool():
	train_records = load_jsonl(TRAIN_FILE)
	batch2_records = load_jsonl(BATCH2_FILE)

	train_ids = {str(r["source_id"]) for r in train_records}
	batch2_ids = {str(r["source_id"]) for r in batch2_records}
	overlap = train_ids & batch2_ids
	if overlap:
		raise RuntimeError(f"train.jsonl and batch2 share source_ids -- must not happen: {overlap}")

	natural = []
	for r in train_records:
		natural.append({
			"source_id": r["source_id"],
			"term": r["term"],
			"candidates": r["candidates"],
			"selected_index": r["selected_index"],
			"candidate_count": len(r["candidates"]),
			"candidate_count_bucket": bucket_of(len(r["candidates"])),
			"source_batch": "experiment1_original",
			"weight": 1.0,
		})
	for r in batch2_records:
		natural.append({
			"source_id": r["source_id"],
			"term": r["term"],
			"candidates": r["candidates"],
			"selected_index": r["selected_index"],
			"candidate_count": len(r["candidates"]),
			"candidate_count_bucket": r.get("candidate_count_bucket") or bucket_of(len(r["candidates"])),
			"source_batch": "experiment2_distribution_correction",
			"weight": 1.0,
		})

	ids = [row["source_id"] for row in natural]
	assert len(ids) == len(set(str(i) for i in ids)), "duplicate source_id in combined natural pool"
	return natural


def shuffle_one(rng, row):
	candidates = row["candidates"]
	n = len(candidates)
	original_sentence = candidates[row["selected_index"]]

	perm = list(range(n))
	identity = list(range(n))
	# reroll until it's a genuine reordering (guards the n=2 case, which is 50% identity otherwise)
	while True:
		rng.shuffle(perm)
		if perm != identity or n < 2:
			break

	new_candidates = [candidates[i] for i in perm]
	new_selected_index = perm.index(row["selected_index"])

	assert new_candidates[new_selected_index] == original_sentence, "shuffle lost the selected sentence"
	assert Counter(new_candidates) == Counter(candidates), "shuffle changed the candidate multiset"
	assert new_candidates != candidates, "shuffle produced the identical order"

	return {
		"source_id": row["source_id"],
		"term": row["term"],
		"candidates": new_candidates,
		"selected_index": new_selected_index,
		"candidate_count": n,
		"candidate_count_bucket": row["candidate_count_bucket"],
		"source_batch": row["source_batch"],
		"weight": 0.5,
		"twin_of": row["source_id"],
	}


def audit_group(name, rows):
	n = len(rows)
	idx0 = sum(1 for r in rows if r["selected_index"] == 0)
	idx_counts = Counter(r["selected_index"] for r in rows)
	bucket_counts = Counter(r["candidate_count_bucket"] for r in rows)
	return {
		"group": name,
		"n_rows": n,
		"index0_count": idx0,
		"index0_rate": idx0 / n if n else None,
		"selected_index_distribution_top10": idx_counts.most_common(10),
		"distinct_indices_used": len(idx_counts),
		"candidate_count_bucket_distribution": dict(bucket_counts),
	}


def verify_pairing(natural, shuffled):
	problems = []

	natural_by_id = {str(r["source_id"]): r for r in natural}
	shuffled_by_id = {str(r["source_id"]): r for r in shuffled}

	if set(natural_by_id) != set(shuffled_by_id):
		problems.append({
			"check": "1:1 source_id pairing",
			"natural_only": sorted(set(natural_by_id) - set(shuffled_by_id)),
			"shuffled_only": sorted(set(shuffled_by_id) - set(natural_by_id)),
		})

	mismatched_candidate_sets = []
	mismatched_selected_sentence = []
	unchanged_order = []
	for sid in natural_by_id:
		if sid not in shuffled_by_id:
			continue
		nat = natural_by_id[sid]
		shuf = shuffled_by_id[sid]
		if Counter(nat["candidates"]) != Counter(shuf["candidates"]):
			mismatched_candidate_sets.append(sid)
		nat_sentence = nat["candidates"][nat["selected_index"]]
		shuf_sentence = shuf["candidates"][shuf["selected_index"]]
		if nat_sentence != shuf_sentence:
			mismatched_selected_sentence.append(sid)
		if nat["candidates"] == shuf["candidates"]:
			unchanged_order.append(sid)

	if mismatched_candidate_sets:
		problems.append({"check": "candidate multiset identical", "failing_ids": mismatched_candidate_sets})
	if mismatched_selected_sentence:
		problems.append({"check": "selected sentence identical before/after", "failing_ids": mismatched_selected_sentence})
	if unchanged_order:
		problems.append({"check": "shuffled order differs from natural order", "failing_ids": unchanged_order})

	return problems


def verify_no_test_leakage(all_rows):
	test_ids = {str(r["source_id"]) for r in load_jsonl(TEST_FILE)}
	present = {str(r["source_id"]) for r in all_rows} & test_ids
	return sorted(present)


def verify_no_stray_duplicates(all_rows):
	counts = Counter(str(r["source_id"]) for r in all_rows)
	stray = {sid: c for sid, c in counts.items() if c != 2}
	return stray


def main():
	rng = random.Random(SEED)

	natural = build_natural_pool()
	natural.sort(key=lambda r: str(r["source_id"]))  # deterministic order before shuffling
	shuffled = [shuffle_one(rng, row) for row in natural]

	write_jsonl_atomic(NATURAL_FILE, natural)
	write_jsonl_atomic(SHUFFLED_FILE, shuffled)

	combined = natural + shuffled
	write_jsonl_atomic(AUGMENTED_FILE, combined)

	pairing_problems = verify_pairing(natural, shuffled)
	test_leakage = verify_no_test_leakage(combined)
	stray_duplicates = verify_no_stray_duplicates(combined)

	audits = {
		"natural": audit_group("natural", natural),
		"shuffled": audit_group("shuffled", shuffled),
		"combined": audit_group("combined", combined),
	}

	# Expected index-0 rate under near-uniform random shuffling: roughly the mean of
	# 1/candidate_count across rows, i.e. what you'd get if position carried no signal.
	expected_uniform_idx0_rate = sum(1 / r["candidate_count"] for r in shuffled) / len(shuffled)
	observed_shuffled_idx0_rate = audits["shuffled"]["index0_rate"]
	# Flag only a large, qualitative departure (>3x expected) -- small-n noise around a
	# tiny expected rate is normal and not a sign of anything being wrong.
	unexpected_bias = observed_shuffled_idx0_rate > max(0.05, expected_uniform_idx0_rate * 3)

	report = {
		"seed": SEED,
		"inputs": {
			"experiment1_train_file": TRAIN_FILE,
			"experiment1_train_count": len(load_jsonl(TRAIN_FILE)),
			"batch2_file": BATCH2_FILE,
			"batch2_count": len(load_jsonl(BATCH2_FILE)),
		},
		"unique_training_pool_size": len(natural),
		"shuffled_twin_count": len(shuffled),
		"combined_augmented_count": len(combined),
		"outputs": {
			"natural_file": NATURAL_FILE,
			"shuffled_file": SHUFFLED_FILE,
			"augmented_file": AUGMENTED_FILE,
		},
		"audits": audits,
		"expected_uniform_shuffled_index0_rate": expected_uniform_idx0_rate,
		"observed_shuffled_index0_rate": observed_shuffled_idx0_rate,
		"unexpected_index0_bias_flag": unexpected_bias,
		"integrity_checks": {
			"pairing_problems": pairing_problems,
			"test_set_leakage_source_ids": test_leakage,
			"stray_duplicate_source_ids": stray_duplicates,
		},
		"dev_split_proposal_only_not_created": {
			"proposed_unique_examples": DEV_SPLIT_PROPOSED_SIZE,
			"proposed_dev_rows_natural_plus_shuffled": DEV_SPLIT_PROPOSED_SIZE * 2,
			"note": "Not written to disk. Awaiting approval before creating dev/train split files.",
		},
	}
	write_json_atomic(REPORT_FILE, report)

	print(f"Unique training pool (131 + {len(load_jsonl(BATCH2_FILE))}): {len(natural)}")
	print(f"Shuffled twins: {len(shuffled)}")
	print(f"Combined augmented set: {len(combined)} rows -> {AUGMENTED_FILE}")
	print()
	for key in ("natural", "shuffled", "combined"):
		a = audits[key]
		print(f"[{key}] n={a['n_rows']}  idx0={a['index0_count']} ({a['index0_rate']:.1%})  buckets={a['candidate_count_bucket_distribution']}")
	print()
	print(f"Expected idx0 rate under uniform shuffling: {expected_uniform_idx0_rate:.1%}")
	print(f"Observed shuffled idx0 rate:                {observed_shuffled_idx0_rate:.1%}")
	print(f"Unexpected bias flag: {unexpected_bias}")
	print()
	print(f"Pairing problems: {len(pairing_problems)}")
	print(f"Test-set leakage source_ids: {test_leakage}")
	print(f"Stray duplicate source_ids: {stray_duplicates}")
	print()
	print(f"Full report: {REPORT_FILE}")

	if pairing_problems or test_leakage or stray_duplicates or unexpected_bias:
		print()
		print("!!! ONE OR MORE INTEGRITY CHECKS FAILED -- see report before proceeding. !!!")
		sys.exit(1)


if __name__ == "__main__":
	main()
