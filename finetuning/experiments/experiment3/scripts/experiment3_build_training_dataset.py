"""
Experiment 3: build the training dataset by EXTENDING Experiment 2's approved
training data, not replacing it.

Base (carried over unchanged, byte-for-byte, from Experiment 2):
  - The 158 unique natural examples that were actually used in Experiment 2's
    final training run (i.e. training_pool_natural.jsonl minus the 18 held-out
    dev source_ids from train_dev_split_report.json) -- NOT the full 176-example
    pool, which also included the 18 dev examples that were deliberately excluded
    from training.
  - Their 158 existing shuffled twins from training_pool_shuffled.jsonl, reused
    as-is. These are NOT regenerated -- reusing the exact Experiment 2 permutations
    is what "preserve all Experiment 2 training examples actually used" requires.

Addition (new in Experiment 3):
  - The 50 human annotations in experiment3/data/annotations_batch3.jsonl
    (best_index is the ground-truth selected_index; acceptable_indices and
    difficulty are preserved as metadata, not used as training targets).
  - One freshly generated shuffled twin per new example, using the identical
    shuffle strategy/weighting as Experiment 2 (weight 0.5, permute candidate
    order, recompute selected_index to the same sentence, reroll on an identity
    permutation), applied with the same fixed seed for reproducibility.

Outputs (all under finetuning/experiments/experiment3/, nothing in experiment1/
or experiment2/ is modified):
  - data/experiment3_natural_pool.jsonl       208 unique natural examples (full
                                               metadata + candidate text)
  - data/experiment3_new_batch_shuffled.jsonl  the 50 NEW shuffled twins only
  - data/experiment3_train_augmented.jsonl    full-metadata combined pool: 208
                                               natural + 158 (carried-over Exp2
                                               shuffled) + 50 (new Exp3 shuffled)
                                               = 416 rows
  - data/experiment3_train_final.jsonl        the same 416 rows in the exact
                                               Together upload format ({"messages":
                                               [...], "weight": w}) -- extends
                                               Experiment 2's train_final.jsonl
  - data/experiment3_train_manifest.jsonl     416 rows, row-aligned with
                                               train_final.jsonl, with a
                                               `provenance` field that is always
                                               one of: experiment1_original,
                                               experiment2_added_annotations,
                                               experiment2_shuffled_augmentation,
                                               experiment3_new_annotations,
                                               experiment3_shuffled_augmentation
  - results/experiment3_dataset_audit.json    the full audit described below

Does NOT touch annotations.jsonl, splits/train.jsonl, splits/test.jsonl, or
anything under finetuning/experiments/experiment1/ or experiment2/.
Does NOT call Together, does NOT launch training, does NOT create an endpoint.

Usage:
    python experiment3_build_training_dataset.py
"""

import json
import os
import random
import sys
from collections import Counter

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(_THIS_DIR))))
_SERVER_INIT_DIR = os.path.join(_REPO_ROOT, "server_init")
_SHARED_DIR = os.path.join(_REPO_ROOT, "finetuning", "shared")
_DATA_SCRIPTS_DIR = os.path.join(_REPO_ROOT, "finetuning", "scripts", "data")
for _path in (_REPO_ROOT, _SERVER_INIT_DIR, _SHARED_DIR, _DATA_SCRIPTS_DIR):
	if _path not in sys.path:
		sys.path.insert(0, _path)

from create_clearmed_db import _SYSTEM_PROMPT  # noqa: E402
from finetune_prepare import user_prompt_for  # noqa: E402

from dataset_io import load_jsonl, write_jsonl_atomic, write_json_atomic  # noqa: E402

FINETUNING_DIR = os.path.join(_REPO_ROOT, "finetuning")
TEST_FILE = os.path.join(FINETUNING_DIR, "data", "splits", "test.jsonl")

EXP2_DIR = os.path.join(FINETUNING_DIR, "experiments", "experiment2")
EXP2_NATURAL_FILE = os.path.join(EXP2_DIR, "data", "training_pool_natural.jsonl")
EXP2_SHUFFLED_FILE = os.path.join(EXP2_DIR, "data", "training_pool_shuffled.jsonl")
EXP2_TRAIN_FINAL_FILE = os.path.join(EXP2_DIR, "data", "train_final.jsonl")
EXP2_TRAIN_MANIFEST_FILE = os.path.join(EXP2_DIR, "data", "train_final_manifest.jsonl")
EXP2_SPLIT_REPORT_FILE = os.path.join(EXP2_DIR, "results", "train_dev_split_report.json")

EXP3_DIR = os.path.join(FINETUNING_DIR, "experiments", "experiment3")
BATCH3_FILE = os.path.join(EXP3_DIR, "data", "annotations_batch3.jsonl")

NATURAL_POOL_FILE = os.path.join(EXP3_DIR, "data", "experiment3_natural_pool.jsonl")
NEW_SHUFFLED_FILE = os.path.join(EXP3_DIR, "data", "experiment3_new_batch_shuffled.jsonl")
TRAIN_AUGMENTED_FILE = os.path.join(EXP3_DIR, "data", "experiment3_train_augmented.jsonl")
TRAIN_FINAL_FILE = os.path.join(EXP3_DIR, "data", "experiment3_train_final.jsonl")
TRAIN_MANIFEST_FILE = os.path.join(EXP3_DIR, "data", "experiment3_train_manifest.jsonl")
AUDIT_FILE = os.path.join(EXP3_DIR, "results", "experiment3_dataset_audit.json")

SEED = 42  # identical to Experiment 2's shuffle seed -- same augmentation policy


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


# --- Step 1: reconstruct the exact Experiment 2 "used in training" subset -----

def load_exp2_used_subset():
	natural = load_jsonl(EXP2_NATURAL_FILE)
	shuffled = load_jsonl(EXP2_SHUFFLED_FILE)
	assert len(natural) == len(shuffled) == 176, (
		f"expected Experiment 2's full pool to still be 176/176, got {len(natural)}/{len(shuffled)}"
	)

	split_report = json.load(open(EXP2_SPLIT_REPORT_FILE, encoding="utf-8"))
	dev_ids = set(split_report["dev_source_ids"])
	assert len(dev_ids) == 18, f"expected 18 Experiment 2 dev ids, got {len(dev_ids)}"

	natural_by_id = {str(r["source_id"]): r for r in natural}
	shuffled_by_id = {str(r["source_id"]): r for r in shuffled}

	used_ids = sorted(set(natural_by_id) - dev_ids)
	assert len(used_ids) == 158, f"expected 158 Experiment 2 training ids, got {len(used_ids)}"

	exp2_natural_used = [natural_by_id[sid] for sid in used_ids]
	exp2_shuffled_used = [shuffled_by_id[sid] for sid in used_ids]
	return exp2_natural_used, exp2_shuffled_used, used_ids, dev_ids


# --- Step 2: build the 50 new Experiment 3 natural examples + their twins -----

def build_exp3_natural_pool():
	records = load_jsonl(BATCH3_FILE)
	assert len(records) == 50, f"expected 50 Experiment 3 annotations, got {len(records)}"

	natural = []
	for r in records:
		candidates = r["candidates"]
		best_index = r["best_index"]
		natural.append({
			"source_id": r["source_id"],
			"term": r["term"],
			"candidates": candidates,
			"selected_index": best_index,
			"candidate_count": len(candidates),
			"candidate_count_bucket": bucket_of(len(candidates)),
			"source_batch": "experiment3_new_annotations",
			"weight": 1.0,
			# Experiment-3-specific metadata, preserved but not used as training targets.
			"acceptable_indices": r.get("acceptable_indices", []),
			"difficulty": r.get("difficulty"),
			"domain": r.get("domain"),
			"failure_mode_bucket": r.get("bucket"),
		})

	ids = [row["source_id"] for row in natural]
	assert len(ids) == len(set(str(i) for i in ids)), "duplicate source_id within the new Experiment 3 batch"
	return natural


def shuffle_one(rng, row):
	candidates = row["candidates"]
	n = len(candidates)
	original_sentence = candidates[row["selected_index"]]

	perm = list(range(n))
	identity = list(range(n))
	while True:
		rng.shuffle(perm)
		if perm != identity or n < 2:
			break

	new_candidates = [candidates[i] for i in perm]
	new_selected_index = perm.index(row["selected_index"])

	assert new_candidates[new_selected_index] == original_sentence, "shuffle lost the selected sentence"
	assert Counter(new_candidates) == Counter(candidates), "shuffle changed the candidate multiset"
	assert new_candidates != candidates, "shuffle produced the identical order"

	twin = dict(row)
	twin["candidates"] = new_candidates
	twin["selected_index"] = new_selected_index
	twin["weight"] = 0.5
	twin["twin_of"] = row["source_id"]
	return twin


# --- Chat-format + manifest rows, identical shape to Experiment 2 -------------

def to_chat_line(record):
	return {
		"messages": [
			{"role": "system", "content": _SYSTEM_PROMPT},
			{"role": "user", "content": user_prompt_for(record)},
			{"role": "assistant", "content": json.dumps({"selected_index": record["selected_index"]})},
		],
		"weight": record["weight"],
	}


def provenance_of(record, is_shuffled):
	if record["source_batch"] == "experiment3_new_annotations":
		return "experiment3_shuffled_augmentation" if is_shuffled else "experiment3_new_annotations"
	if record["source_batch"] == "experiment1_original":
		return "experiment2_shuffled_augmentation" if is_shuffled else "experiment1_original"
	if record["source_batch"] == "experiment2_distribution_correction":
		return "experiment2_shuffled_augmentation" if is_shuffled else "experiment2_added_annotations"
	raise ValueError(f"Unrecognized source_batch: {record['source_batch']!r}")


def to_manifest_line(record, is_shuffled):
	return {
		"source_id": record["source_id"],
		"term": record["term"],
		"candidate_count": record["candidate_count"],
		"candidate_count_bucket": record["candidate_count_bucket"],
		"source_batch": record["source_batch"],
		"provenance": provenance_of(record, is_shuffled),
		"is_shuffled": is_shuffled,
		"selected_index": record["selected_index"],
		"weight": record["weight"],
		"acceptable_indices": record.get("acceptable_indices") if record["source_batch"] == "experiment3_new_annotations" else None,
		"difficulty": record.get("difficulty") if record["source_batch"] == "experiment3_new_annotations" else None,
	}


# --- Audit ---------------------------------------------------------------------

def audit_and_compare(natural_pool, new_shuffled, exp2_shuffled_used, train_augmented, train_final_chat, manifest, used_ids, dev_ids):
	problems = []

	# 1. Duplicate source_id checks (unique-example level).
	unique_ids = [str(r["source_id"]) for r in natural_pool]
	dup_ids = [sid for sid, c in Counter(unique_ids).items() if c > 1]
	if dup_ids:
		problems.append({"check": "no duplicate source_ids in natural pool", "failing_ids": dup_ids})

	# 2. Overlap with the fixed held-out test set.
	test_ids = {str(r["source_id"]) for r in load_jsonl(TEST_FILE)}
	overlap_test = sorted(set(unique_ids) & test_ids)
	if overlap_test:
		problems.append({"check": "no overlap with held-out test.jsonl", "failing_ids": overlap_test})

	# 3. Index validity: every selected_index (and every message's assistant JSON)
	#    must be a valid index into that row's own candidate list.
	bad_index_rows = []
	for r in train_augmented:
		n = len(r["candidates"])
		if not (0 <= r["selected_index"] < n):
			bad_index_rows.append({"source_id": r["source_id"], "is_shuffled": "twin_of" in r, "selected_index": r["selected_index"], "n_candidates": n})
	if bad_index_rows:
		problems.append({"check": "selected_index within candidate range", "failing_rows": bad_index_rows})

	# 4. JSONL structural validity of the Together-upload chat file.
	structural_bad = []
	for i, row in enumerate(train_final_chat):
		msgs = row.get("messages")
		ok = (
			isinstance(msgs, list) and len(msgs) == 3
			and [m["role"] for m in msgs] == ["system", "user", "assistant"]
			and isinstance(row.get("weight"), (int, float))
			and set(row.keys()) == {"messages", "weight"}
		)
		if ok:
			try:
				parsed = json.loads(msgs[2]["content"])
				ok = isinstance(parsed, dict) and set(parsed.keys()) == {"selected_index"} and isinstance(parsed["selected_index"], int)
			except (json.JSONDecodeError, KeyError):
				ok = False
		if not ok:
			structural_bad.append(i)
	if structural_bad:
		problems.append({"check": "train_final.jsonl structural validity", "failing_row_indices": structural_bad})

	# 5. Shuffle-pairing integrity for the 50 NEW twins specifically.
	exp3_natural_by_id = {str(r["source_id"]): r for r in natural_pool if r["source_batch"] == "experiment3_new_annotations"}
	exp3_shuffled_by_id = {str(r["source_id"]): r for r in new_shuffled}
	pairing_problems = []
	if set(exp3_natural_by_id) != set(exp3_shuffled_by_id):
		pairing_problems.append("1:1 pairing mismatch between new natural and new shuffled sets")
	for sid, nat in exp3_natural_by_id.items():
		shuf = exp3_shuffled_by_id.get(sid)
		if shuf is None:
			continue
		if Counter(nat["candidates"]) != Counter(shuf["candidates"]):
			pairing_problems.append(f"{sid}: candidate multiset changed by shuffling")
		if nat["candidates"][nat["selected_index"]] != shuf["candidates"][shuf["selected_index"]]:
			pairing_problems.append(f"{sid}: selected sentence identity not preserved across shuffle")
		if nat["candidates"] == shuf["candidates"]:
			pairing_problems.append(f"{sid}: shuffled order identical to natural order")
	if pairing_problems:
		problems.append({"check": "new-batch shuffle pairing integrity", "failing": pairing_problems})

	# 6. Compare against Experiment 2's actual train_final.jsonl / manifest: every
	#    Experiment 2 training record must still be represented, unchanged, in the
	#    Experiment 3 combined file. Compared by content (candidate multiset +
	#    selected sentence + weight + is_shuffled), not list position.
	exp2_manifest = load_jsonl(EXP2_TRAIN_MANIFEST_FILE)
	exp2_chat = load_jsonl(EXP2_TRAIN_FINAL_FILE)
	assert len(exp2_manifest) == len(exp2_chat) == 316

	def fingerprint_chat_row(row):
		msgs = row["messages"]
		return (msgs[1]["content"], msgs[2]["content"], row["weight"])

	exp2_fingerprints = Counter(fingerprint_chat_row(r) for r in exp2_chat)
	exp3_fingerprints = Counter(fingerprint_chat_row(r) for r in train_final_chat)

	missing_exp2_rows = list((exp2_fingerprints - exp3_fingerprints).elements())
	exp2_still_represented = len(missing_exp2_rows) == 0
	if not exp2_still_represented:
		problems.append({
			"check": "every Experiment 2 train_final.jsonl row still present in Experiment 3's file",
			"missing_count": len(missing_exp2_rows),
		})

	exp2_source_ids_in_manifest = {str(r["source_id"]) for r in exp2_manifest}
	assert exp2_source_ids_in_manifest == set(used_ids), "reconstructed Exp2 used-id set doesn't match Exp2's own manifest"

	# 7. Contribution counts by experiment / natural vs shuffled.
	prov_counts = Counter(m["provenance"] for m in manifest)
	is_shuffled_counts = Counter(m["is_shuffled"] for m in manifest)

	# 8. Candidate-count distribution (bucketed), over the full combined pool.
	bucket_counts = Counter(r["candidate_count_bucket"] for r in train_augmented)

	# 9. Difficulty distribution, for the 50 new Experiment 3 annotations only.
	difficulty_counts = Counter(r["difficulty"] for r in natural_pool if r["source_batch"] == "experiment3_new_annotations")

	report = {
		"seed": SEED,
		"totals": {
			"final_training_examples_total_rows": len(train_augmented),
			"natural_rows": sum(1 for r in train_augmented if "twin_of" not in r),
			"shuffled_rows": sum(1 for r in train_augmented if "twin_of" in r),
			"unique_examples": len(natural_pool),
		},
		"contribution_by_provenance": dict(prov_counts),
		"contribution_by_experiment": {
			"experiment1_total_rows": prov_counts.get("experiment1_original", 0) + sum(
				1 for m in manifest if m["provenance"] == "experiment2_shuffled_augmentation"
				and m["source_batch"] == "experiment1_original"
			),
			"experiment2_total_rows": prov_counts.get("experiment2_added_annotations", 0) + sum(
				1 for m in manifest if m["provenance"] == "experiment2_shuffled_augmentation"
				and m["source_batch"] == "experiment2_distribution_correction"
			),
			"experiment3_total_rows": prov_counts.get("experiment3_new_annotations", 0) + prov_counts.get("experiment3_shuffled_augmentation", 0),
		},
		"is_shuffled_row_counts": {str(k): v for k, v in is_shuffled_counts.items()},
		"duplicate_source_id_check": {"duplicates_found": dup_ids},
		"held_out_test_set_overlap_check": {"overlap_source_ids": overlap_test},
		"index_validity_check": {"invalid_rows": bad_index_rows},
		"jsonl_structural_validity_check": {"invalid_row_indices": structural_bad},
		"new_batch_shuffle_pairing_check": {"problems": pairing_problems},
        "candidate_count_bucket_distribution_combined_pool": dict(bucket_counts),
		"difficulty_distribution_new_50": dict(difficulty_counts),
		"experiment2_base_reconstruction": {
			"exp2_used_training_ids_count": len(used_ids),
			"exp2_dev_excluded_ids_count": len(dev_ids),
			"exp2_used_ids_match_exp2_manifest": exp2_source_ids_in_manifest == set(used_ids),
		},
		"experiment2_vs_experiment3_comparison": {
			"exp2_train_final_row_count": len(exp2_chat),
			"exp3_train_final_row_count": len(train_final_chat),
			"every_exp2_row_still_represented_in_exp3": exp2_still_represented,
			"missing_exp2_row_count": len(missing_exp2_rows),
			"exp3_extends_exp2_rather_than_rebuilding": exp2_still_represented and len(train_final_chat) == len(exp2_chat) + 100,
		},
		"all_checks_passed": len(problems) == 0,
		"problems": problems,
	}
	return report


def main():
	exp2_natural_used, exp2_shuffled_used, used_ids, dev_ids = load_exp2_used_subset()
	exp3_natural = build_exp3_natural_pool()

	overlap = set(str(r["source_id"]) for r in exp2_natural_used) & set(str(r["source_id"]) for r in exp3_natural)
	if overlap:
		raise RuntimeError(f"Experiment 2 used-ids and new Experiment 3 ids overlap -- must not happen: {overlap}")

	rng = random.Random(SEED)
	exp3_natural_sorted = sorted(exp3_natural, key=lambda r: str(r["source_id"]))
	exp3_shuffled = [shuffle_one(rng, row) for row in exp3_natural_sorted]

	natural_pool = exp2_natural_used + exp3_natural_sorted
	write_jsonl_atomic(NATURAL_POOL_FILE, natural_pool)
	write_jsonl_atomic(NEW_SHUFFLED_FILE, exp3_shuffled)

	train_augmented = natural_pool + exp2_shuffled_used + exp3_shuffled
	write_jsonl_atomic(TRAIN_AUGMENTED_FILE, train_augmented)

	train_final_chat = [to_chat_line(r) for r in train_augmented]
	write_jsonl_atomic(TRAIN_FINAL_FILE, train_final_chat)

	manifest = []
	for r in natural_pool:
		manifest.append(to_manifest_line(r, is_shuffled=False))
	for r in exp2_shuffled_used:
		manifest.append(to_manifest_line(r, is_shuffled=True))
	for r in exp3_shuffled:
		manifest.append(to_manifest_line(r, is_shuffled=True))
	write_jsonl_atomic(TRAIN_MANIFEST_FILE, manifest)

	report = audit_and_compare(
		natural_pool, exp3_shuffled, exp2_shuffled_used, train_augmented, train_final_chat, manifest, used_ids, dev_ids
	)
	write_json_atomic(AUDIT_FILE, report)

	print(f"Experiment 2 base reused unchanged: {len(exp2_natural_used)} natural + {len(exp2_shuffled_used)} shuffled = {len(exp2_natural_used) + len(exp2_shuffled_used)} rows")
	print(f"Experiment 3 new: {len(exp3_natural_sorted)} natural + {len(exp3_shuffled)} shuffled = {len(exp3_natural_sorted) + len(exp3_shuffled)} rows")
	print(f"Combined: {len(train_augmented)} rows ({len(natural_pool)} unique) -> {TRAIN_AUGMENTED_FILE}")
	print(f"Together upload format -> {TRAIN_FINAL_FILE}")
	print(f"Manifest -> {TRAIN_MANIFEST_FILE}")
	print()
	print("=== AUDIT ===")
	print(json.dumps(report, indent=2)[:4000])
	print(f"... full report at {AUDIT_FILE}")
	print()
	print(f"ALL CHECKS PASSED: {report['all_checks_passed']}")
	if not report["all_checks_passed"]:
		print("!!! ONE OR MORE INTEGRITY CHECKS FAILED -- see report. !!!")
		sys.exit(1)


if __name__ == "__main__":
	main()
