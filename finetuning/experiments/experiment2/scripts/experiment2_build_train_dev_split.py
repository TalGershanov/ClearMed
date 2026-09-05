"""
Phase 2, Step 1: split the 176-unique Experiment 2 pool (natural + shuffled twins,
352 rows total) into a final train set and a dev/validation set, at the source_id
(unique-example) level, so a natural example and its shuffled twin always stay on
the same side.

Dev allocation (approved), stratified by candidate-count bucket, 18 unique examples:
    >40 candidates: 10
    21-40:           3
    11-20:           2
    6-10:            2
    <=5:             1

Writes two kinds of files per split:
  - train_final.jsonl / dev.jsonl: the exact Together upload format -- ONLY
    {"messages": [...], "weight": <float>} per line. No extra top-level keys, because
    the installed together SDK's local file checker rejects any top-level column
    other than "messages"/"tools" for the conversational format (see Step 2 findings).
  - train_final_manifest.jsonl / dev_manifest.jsonl: a row-aligned (same order, same
    count) side file with source_id/term/bucket/weight/etc. for auditing. Never
    uploaded to Together.

Never touches annotations.jsonl, splits/train.jsonl, splits/test.jsonl, or
data/finetune/.

Usage:
    python experiment2_build_train_dev_split.py
"""

import os
import random
import sys

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(_THIS_DIR))))
_SERVER_INIT_DIR = os.path.join(_REPO_ROOT, "server_init")
_SHARED_DIR = os.path.join(_REPO_ROOT, "finetuning", "shared")
_DATA_SCRIPTS_DIR = os.path.join(_REPO_ROOT, "finetuning", "scripts", "data")
for _path in (_REPO_ROOT, _SERVER_INIT_DIR, _SHARED_DIR, _DATA_SCRIPTS_DIR):
	if _path not in sys.path:
		sys.path.insert(0, _path)

from create_clearmed_db import _SYSTEM_PROMPT  # noqa: E402

from dataset_io import load_jsonl, write_jsonl_atomic, write_json_atomic  # noqa: E402
from finetune_prepare import user_prompt_for  # noqa: E402

import json  # noqa: E402

TEST_FILE = os.path.join(_REPO_ROOT, "finetuning", "data", "splits", "test.jsonl")

EXP2_DIR = os.path.join(_REPO_ROOT, "finetuning", "experiments", "experiment2")
NATURAL_FILE = os.path.join(EXP2_DIR, "data", "training_pool_natural.jsonl")
SHUFFLED_FILE = os.path.join(EXP2_DIR, "data", "training_pool_shuffled.jsonl")

TRAIN_FINAL_FILE = os.path.join(EXP2_DIR, "data", "train_final.jsonl")
TRAIN_MANIFEST_FILE = os.path.join(EXP2_DIR, "data", "train_final_manifest.jsonl")
DEV_FILE = os.path.join(EXP2_DIR, "data", "dev.jsonl")
DEV_MANIFEST_FILE = os.path.join(EXP2_DIR, "data", "dev_manifest.jsonl")
SPLIT_REPORT_FILE = os.path.join(EXP2_DIR, "results", "train_dev_split_report.json")

SEED = 42
DEV_TARGETS = {">40": 10, "21-40": 3, "11-20": 2, "6-10": 2, "<=5": 1}
BUCKET_ORDER = [">40", "21-40", "11-20", "6-10", "<=5"]


def to_chat_line(record):
	return {
		"messages": [
			{"role": "system", "content": _SYSTEM_PROMPT},
			{"role": "user", "content": user_prompt_for(record)},
			{"role": "assistant", "content": json.dumps({"selected_index": record["selected_index"]})},
		],
		"weight": record["weight"],
	}


def to_manifest_line(record, is_shuffled):
	return {
		"source_id": record["source_id"],
		"term": record["term"],
		"candidate_count": record["candidate_count"],
		"candidate_count_bucket": record["candidate_count_bucket"],
		"source_batch": record["source_batch"],
		"is_shuffled": is_shuffled,
		"selected_index": record["selected_index"],
		"weight": record["weight"],
	}


def pick_dev_ids(natural):
	by_bucket = {b: [] for b in BUCKET_ORDER}
	for r in natural:
		by_bucket[r["candidate_count_bucket"]].append(str(r["source_id"]))
	for b in by_bucket:
		by_bucket[b].sort()

	rng = random.Random(SEED)
	dev_ids = set()
	shortfalls = {}
	for b in BUCKET_ORDER:
		target = DEV_TARGETS.get(b, 0)
		available = by_bucket[b]
		take = min(target, len(available))
		if take < target:
			shortfalls[b] = {"target": target, "available": len(available), "taken": take}
		dev_ids.update(rng.sample(available, take))
	return dev_ids, shortfalls


def main():
	natural = load_jsonl(NATURAL_FILE)
	shuffled = load_jsonl(SHUFFLED_FILE)
	assert len(natural) == len(shuffled) == 176, f"expected 176/176, got {len(natural)}/{len(shuffled)}"

	dev_ids, shortfalls = pick_dev_ids(natural)
	assert len(dev_ids) == 18, f"expected 18 dev ids, got {len(dev_ids)}"

	natural_by_id = {str(r["source_id"]): r for r in natural}
	shuffled_by_id = {str(r["source_id"]): r for r in shuffled}
	assert set(natural_by_id) == set(shuffled_by_id), "natural/shuffled source_id sets differ"

	train_ids = sorted(set(natural_by_id) - dev_ids)
	dev_ids_sorted = sorted(dev_ids)

	train_chat, train_manifest = [], []
	for sid in train_ids:
		nat, shuf = natural_by_id[sid], shuffled_by_id[sid]
		train_chat.append(to_chat_line(nat))
		train_manifest.append(to_manifest_line(nat, is_shuffled=False))
		train_chat.append(to_chat_line(shuf))
		train_manifest.append(to_manifest_line(shuf, is_shuffled=True))

	dev_chat, dev_manifest = [], []
	for sid in dev_ids_sorted:
		nat, shuf = natural_by_id[sid], shuffled_by_id[sid]
		dev_chat.append(to_chat_line(nat))
		dev_manifest.append(to_manifest_line(nat, is_shuffled=False))
		dev_chat.append(to_chat_line(shuf))
		dev_manifest.append(to_manifest_line(shuf, is_shuffled=True))

	write_jsonl_atomic(TRAIN_FINAL_FILE, train_chat)
	write_jsonl_atomic(TRAIN_MANIFEST_FILE, train_manifest)
	write_jsonl_atomic(DEV_FILE, dev_chat)
	write_jsonl_atomic(DEV_MANIFEST_FILE, dev_manifest)

	test_ids = {str(r["source_id"]) for r in load_jsonl(TEST_FILE)}
	train_test_leak = sorted(test_ids & set(train_ids))
	dev_test_leak = sorted(test_ids & dev_ids)
	train_dev_overlap = sorted(set(train_ids) & dev_ids)

	report = {
		"seed": SEED,
		"dev_targets_by_bucket": DEV_TARGETS,
		"dev_shortfalls": shortfalls,
		"n_unique_total": len(natural_by_id),
		"n_unique_train": len(train_ids),
		"n_unique_dev": len(dev_ids_sorted),
		"n_train_rows": len(train_chat),
		"n_dev_rows": len(dev_chat),
		"dev_source_ids": dev_ids_sorted,
		"train_test_leak": train_test_leak,
		"dev_test_leak": dev_test_leak,
		"train_dev_overlap": train_dev_overlap,
		"outputs": {
			"train_final": TRAIN_FINAL_FILE,
			"train_manifest": TRAIN_MANIFEST_FILE,
			"dev": DEV_FILE,
			"dev_manifest": DEV_MANIFEST_FILE,
		},
	}
	write_json_atomic(SPLIT_REPORT_FILE, report)

	print(f"Train: {len(train_ids)} unique -> {len(train_chat)} rows -> {TRAIN_FINAL_FILE}")
	print(f"Dev:   {len(dev_ids_sorted)} unique -> {len(dev_chat)} rows -> {DEV_FILE}")
	print(f"Dev shortfalls: {shortfalls or 'none'}")
	print(f"Train/test leak: {train_test_leak}")
	print(f"Dev/test leak: {dev_test_leak}")
	print(f"Train/dev overlap: {train_dev_overlap}")
	print(f"Report: {SPLIT_REPORT_FILE}")

	if train_test_leak or dev_test_leak or train_dev_overlap or shortfalls:
		print("!!! SPLIT INTEGRITY PROBLEM -- see report. !!!")
		sys.exit(1)


if __name__ == "__main__":
	main()
