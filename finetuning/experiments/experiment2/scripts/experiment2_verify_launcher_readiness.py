"""
Phase 2, Step 4: safety/integrity checks on the final Experiment 2 train/dev files,
run before the launcher is considered ready. Purely local -- no network calls.

Usage:
    python experiment2_verify_launcher_readiness.py
"""

import json
import os
import sys
from collections import Counter

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(_THIS_DIR))))
_SHARED_DIR = os.path.join(_REPO_ROOT, "finetuning", "shared")
if _SHARED_DIR not in sys.path:
	sys.path.insert(0, _SHARED_DIR)

from dataset_io import load_jsonl, load_json, write_json_atomic  # noqa: E402
from together.lib.utils.files import check_file  # noqa: E402
from pathlib import Path  # noqa: E402

TEST_FILE = os.path.join(_REPO_ROOT, "finetuning", "data", "splits", "test.jsonl")

EXP2_DIR = os.path.join(_REPO_ROOT, "finetuning", "experiments", "experiment2")
NATURAL_FILE = os.path.join(EXP2_DIR, "data", "training_pool_natural.jsonl")
SHUFFLED_FILE = os.path.join(EXP2_DIR, "data", "training_pool_shuffled.jsonl")
TRAIN_FINAL_FILE = os.path.join(EXP2_DIR, "data", "train_final.jsonl")
TRAIN_MANIFEST_FILE = os.path.join(EXP2_DIR, "data", "train_final_manifest.jsonl")
DEV_FILE = os.path.join(EXP2_DIR, "data", "dev.jsonl")
DEV_MANIFEST_FILE = os.path.join(EXP2_DIR, "data", "dev_manifest.jsonl")
REPORT_FILE = os.path.join(EXP2_DIR, "results", "step4_readiness_report.json")


def strip_weight_and_check(chat_file):
	lines = [json.loads(l) for l in open(chat_file, encoding="utf-8")]
	tmp_path = chat_file + ".no_weight_check.tmp.jsonl"
	with open(tmp_path, "w", encoding="utf-8") as f:
		for l in lines:
			f.write(json.dumps({"messages": l["messages"]}) + "\n")
	try:
		report = check_file(Path(tmp_path))
	finally:
		os.remove(tmp_path)
	weights = [l.get("weight") for l in lines]
	weights_valid = all(isinstance(w, (int, float)) and not isinstance(w, bool) and w >= 0 for w in weights)
	return {
		"conversational_format_check_excluding_weight": report.get("is_check_passed"),
		"conversational_format_message": report.get("message"),
		"all_weights_non_negative_numbers": weights_valid,
		"weight_values_present": sorted(set(weights)),
	}


def main():
	problems = []

	train_manifest = load_jsonl(TRAIN_MANIFEST_FILE)
	dev_manifest = load_jsonl(DEV_MANIFEST_FILE)
	train_chat = load_jsonl(TRAIN_FINAL_FILE)
	dev_chat = load_jsonl(DEV_FILE)

	# 1. train_final.jsonl contains exactly the expected natural + shuffled rows.
	train_natural = [r for r in train_manifest if not r["is_shuffled"]]
	train_shuffled = [r for r in train_manifest if r["is_shuffled"]]
	check1 = {"n_train_rows": len(train_chat), "n_manifest_rows": len(train_manifest),
	          "n_natural": len(train_natural), "n_shuffled": len(train_shuffled)}
	if len(train_chat) != len(train_manifest) or len(train_natural) != 158 or len(train_shuffled) != 158:
		problems.append(("1_expected_row_counts", check1))

	# 2. Shuffled rows are actually included in TRAIN.
	check2 = {"n_shuffled_in_train": len(train_shuffled)}
	if len(train_shuffled) == 0:
		problems.append(("2_shuffled_rows_present_in_train", check2))

	# 3 & 4. Weight correctness.
	bad_natural_weight = [r["source_id"] for r in train_natural if r["weight"] != 1.0]
	bad_shuffled_weight = [r["source_id"] for r in train_shuffled if r["weight"] != 0.5]
	if bad_natural_weight:
		problems.append(("3_natural_weight_1.0", bad_natural_weight))
	if bad_shuffled_weight:
		problems.append(("4_shuffled_weight_0.5", bad_shuffled_weight))

	# 5. No source_id appears in both train and dev.
	train_ids = {str(r["source_id"]) for r in train_manifest}
	dev_ids = {str(r["source_id"]) for r in dev_manifest}
	overlap = sorted(train_ids & dev_ids)
	if overlap:
		problems.append(("5_no_train_dev_overlap", overlap))

	# 6. Natural/shuffled twins always stay together (same split).
	def twins_together(manifest, label):
		by_id = {}
		for r in manifest:
			by_id.setdefault(str(r["source_id"]), []).append(r["is_shuffled"])
		broken = [sid for sid, flags in by_id.items() if sorted(flags) != [False, True]]
		return broken

	broken_train = twins_together(train_manifest, "train")
	broken_dev = twins_together(dev_manifest, "dev")
	if broken_train or broken_dev:
		problems.append(("6_twins_together", {"train": broken_train, "dev": broken_dev}))

	# 7. No held-out test source_id in train or dev.
	test_ids = {str(r["source_id"]) for r in load_jsonl(TEST_FILE)}
	test_leak = sorted((train_ids | dev_ids) & test_ids)
	if test_leak:
		problems.append(("7_no_test_leakage", test_leak))

	# 8. No accidental duplicates beyond the intentional natural/shuffled pair.
	all_ids = [str(r["source_id"]) for r in train_manifest + dev_manifest]
	stray = {sid: c for sid, c in Counter(all_ids).items() if c != 2}
	if stray:
		problems.append(("8_no_stray_duplicates", stray))

	# 9. Human-selected sentence identical between every natural/shuffled pair,
	# re-verified against the original candidate pool for exactly the ids that ended
	# up in train_final.jsonl / dev.jsonl (not just the broader Phase-2 pool).
	natural_pool = {str(r["source_id"]): r for r in load_jsonl(NATURAL_FILE)}
	shuffled_pool = {str(r["source_id"]): r for r in load_jsonl(SHUFFLED_FILE)}
	sentence_mismatches = []
	for sid in train_ids | dev_ids:
		nat, shuf = natural_pool[sid], shuffled_pool[sid]
		nat_sentence = nat["candidates"][nat["selected_index"]]
		shuf_sentence = shuf["candidates"][shuf["selected_index"]]
		if nat_sentence != shuf_sentence:
			sentence_mismatches.append(sid)
	if sentence_mismatches:
		problems.append(("9_selected_sentence_identical", sentence_mismatches))

	# 10. Local dataset validation (excluding the known weight-column gap), no network call.
	train_local_check = strip_weight_and_check(TRAIN_FINAL_FILE)
	dev_local_check = strip_weight_and_check(DEV_FILE)
	if not train_local_check["conversational_format_check_excluding_weight"] or not train_local_check["all_weights_non_negative_numbers"]:
		problems.append(("10_train_local_check", train_local_check))
	if not dev_local_check["conversational_format_check_excluding_weight"] or not dev_local_check["all_weights_non_negative_numbers"]:
		problems.append(("10_dev_local_check", dev_local_check))

	# Final distributions requested: selected_index distribution for natural / shuffled / combined train.
	def index_distribution(rows):
		idx_counts = Counter(r["selected_index"] for r in rows)
		n = len(rows)
		return {
			"n": n,
			"index0_count": idx_counts[0],
			"index0_rate": idx_counts[0] / n if n else None,
			"distribution_top10": idx_counts.most_common(10),
			"candidate_count_bucket_distribution": dict(Counter(r["candidate_count_bucket"] for r in rows)),
		}

	distributions = {
		"train_natural": index_distribution(train_natural),
		"train_shuffled": index_distribution(train_shuffled),
		"train_combined": index_distribution(train_manifest),
	}

	report = {
		"row_counts": check1,
		"weight_checks": {"natural_weight_ok": not bad_natural_weight, "shuffled_weight_ok": not bad_shuffled_weight},
		"train_dev_overlap": overlap,
		"twins_together_broken": {"train": broken_train, "dev": broken_dev},
		"test_leakage": test_leak,
		"stray_duplicates": stray,
		"sentence_mismatches": sentence_mismatches,
		"local_format_checks": {"train": train_local_check, "dev": dev_local_check},
		"selected_index_distributions": distributions,
		"all_checks_passed": len(problems) == 0,
		"failed_checks": problems,
	}
	write_json_atomic(REPORT_FILE, report)

	print("=" * 60)
	print("Step 4 readiness checks")
	print("=" * 60)
	for i, desc in enumerate([
		"1. train_final.jsonl row counts (316 = 158 natural + 158 shuffled)",
		"2. shuffled rows present in train",
		"3. natural train rows weight == 1.0",
		"4. shuffled train rows weight == 0.5",
		"5. no source_id in both train and dev",
		"6. natural/shuffled twins stay together",
		"7. no held-out test source_id in train/dev",
		"8. no stray duplicate source_ids",
		"9. selected sentence identical natural vs shuffled",
		"10. local format check (excl. weight) + weight value validity",
	], start=1):
		failed = any(p[0].startswith(f"{i}_") for p in problems)
		print(f"  [{'FAIL' if failed else 'pass'}] {desc}")

	print()
	print("Selected-index distributions in FINAL train set:")
	for key in ("train_natural", "train_shuffled", "train_combined"):
		d = distributions[key]
		print(f"  {key}: n={d['n']}  idx0={d['index0_count']} ({d['index0_rate']:.1%})")

	print()
	print(f"Full report: {REPORT_FILE}")
	if problems:
		print()
		print("!!! ONE OR MORE CHECKS FAILED -- do not consider the launcher ready. !!!")
		sys.exit(1)
	else:
		print()
		print("All Step 4 checks passed.")


if __name__ == "__main__":
	main()
