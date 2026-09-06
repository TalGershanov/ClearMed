"""
Phase 1, step 1: sample the candidate pool for the Experiment 2 distribution-correction
annotation batch.

Selects new terms from the full ClearMed corpus, stratified by candidate-count bucket
(<=5, 6-10, 11-20), excluding every term already present in finetuning/data/annotations.jsonl
(the 181 existing labels -- which is the superset of the 131 Experiment 1 training examples
and the 50 held-out test examples, so excluding it excludes all three at once).

Candidate sentences are produced with the exact same _clean_candidate_sentences function
production/V7 uses, so the annotation candidates match what ClearMed actually shows.

This script only reads the corpus and existing annotations, and writes the new (unlabeled)
pool file below -- it never touches annotations.jsonl, splits/, or finetune/.

Usage:
    python experiment2_sample_pool.py
"""

import json
import os
import random
import sys

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(_THIS_DIR))))
_SERVER_INIT_DIR = os.path.join(_REPO_ROOT, "server_init")
_SHARED_DIR = os.path.join(_REPO_ROOT, "finetuning", "shared")
for _path in (_REPO_ROOT, _SERVER_INIT_DIR, _SHARED_DIR):
	if _path not in sys.path:
		sys.path.insert(0, _path)

from ai_services import _clean_candidate_sentences  # noqa: E402
from config import JSON_FILE  # noqa: E402

from dataset_io import load_jsonl, write_json_atomic  # noqa: E402

DATA_DIR = os.path.join(_REPO_ROOT, "finetuning", "data")
ANNOTATIONS_FILE = os.path.join(DATA_DIR, "annotations.jsonl")
TEST_FILE = os.path.join(DATA_DIR, "splits", "test.jsonl")
TRAIN_FILE = os.path.join(DATA_DIR, "splits", "train.jsonl")

EXP2_DIR = os.path.join(_REPO_ROOT, "finetuning", "experiments", "experiment2")
POOL_FILE = os.path.join(EXP2_DIR, "data", "candidate_pool.json")
REPORT_FILE = os.path.join(EXP2_DIR, "results", "phase1_sampling_report.json")

SEED = 42
BATCH_NAME = "experiment2_distribution_correction"

# Bucket -> target sample count. 10 + 18 + 17 = 45.
TARGETS = {
	"<=5": 10,
	"6-10": 18,
	"11-20": 17,
}


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


def main():
	with open(JSON_FILE, encoding="utf-8") as f:
		all_terms = json.load(f)["terms"]

	existing = load_jsonl(ANNOTATIONS_FILE)
	excluded_ids = {str(r["source_id"]) for r in existing}

	test_ids = {str(r["source_id"]) for r in load_jsonl(TEST_FILE)}
	train_ids = {str(r["source_id"]) for r in load_jsonl(TRAIN_FILE)}
	assert test_ids <= excluded_ids, "test.jsonl source_ids must be a subset of annotations.jsonl"
	assert train_ids <= excluded_ids, "train.jsonl source_ids must be a subset of annotations.jsonl"

	pools = {"<=5": [], "6-10": [], "11-20": [], "21-40": [], ">40": []}
	skipped_too_few = 0
	for item in all_terms:
		source_id = str(item.get("source_id"))
		if source_id in excluded_ids:
			continue
		sentences = _clean_candidate_sentences(item.get("simple_explanation"))
		if len(sentences) < 2:
			skipped_too_few += 1
			continue
		pools[bucket_of(len(sentences))].append((source_id, item, sentences))

	# Deterministic order before sampling, independent of corpus file ordering.
	for bucket in pools:
		pools[bucket].sort(key=lambda entry: entry[0])

	rng = random.Random(SEED)
	sampled = []
	shortfalls = {}
	for bucket, target in TARGETS.items():
		available = pools[bucket]
		take = min(target, len(available))
		if take < target:
			shortfalls[bucket] = {"target": target, "available": len(available), "taken": take}
		chosen = rng.sample(available, take) if take else []
		for source_id, item, sentences in chosen:
			sampled.append({
				"source_id": item.get("source_id"),
				"term": item.get("term"),
				"candidates": sentences,
				"simple_explanation": item.get("simple_explanation"),
				"candidate_count": len(sentences),
				"candidate_count_bucket": bucket,
				"batch": BATCH_NAME,
			})

	write_json_atomic(POOL_FILE, sampled)

	overlap_with_test = {s["source_id"] for s in sampled} & test_ids
	overlap_with_train = {s["source_id"] for s in sampled} & train_ids
	overlap_with_all_existing = {s["source_id"] for s in sampled} & excluded_ids

	report = {
		"seed": SEED,
		"batch": BATCH_NAME,
		"corpus_file": JSON_FILE,
		"corpus_total_terms": len(all_terms),
		"existing_annotations_excluded": len(excluded_ids),
		"skipped_lt_2_candidates": skipped_too_few,
		"pool_sizes_available_by_bucket": {b: len(pools[b]) for b in pools},
		"targets_by_bucket": TARGETS,
		"shortfalls": shortfalls,
		"sampled_count_by_bucket": {
			b: sum(1 for s in sampled if s["candidate_count_bucket"] == b) for b in TARGETS
		},
		"sampled_total": len(sampled),
		"overlap_with_test_jsonl": sorted(overlap_with_test),
		"overlap_with_train_jsonl": sorted(overlap_with_train),
		"overlap_with_any_existing_annotation": sorted(overlap_with_all_existing),
	}
	write_json_atomic(REPORT_FILE, report)

	print(f"Sampled {len(sampled)} new terms into {POOL_FILE}")
	for b in TARGETS:
		print(f"  {b}: {report['sampled_count_by_bucket'][b]} / target {TARGETS[b]} (pool had {len(pools[b])} available)")
	if shortfalls:
		print(f"SHORTFALLS: {shortfalls}")
	else:
		print("No shortfalls -- all bucket targets fully met.")
	print(f"Overlap with test.jsonl: {len(overlap_with_test)} (must be 0)")
	print(f"Overlap with train.jsonl: {len(overlap_with_train)} (must be 0)")
	print(f"Overlap with any existing annotation: {len(overlap_with_all_existing)} (must be 0)")
	print(f"Report written to {REPORT_FILE}")


if __name__ == "__main__":
	main()
