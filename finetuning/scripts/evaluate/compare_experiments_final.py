"""
Final Human vs V7 vs Experiment 1 vs Experiment 2 comparison.

Purely local aggregation over already-saved per-example comparison files -- no API
calls, no model queries. Safe to run any time; sections for a model whose comparison
file doesn't exist yet are reported as "not available" rather than erroring.

Inputs (all keyed by source_id against the same 50-example held-out test set):
  - finetuning/data/splits/test.jsonl                                    (human + V7,
    always available)
  - finetuning/experiments/experiment1/results/eval_comparison_together.jsonl
    (Experiment 1; only 24/50 have a valid finetuned_selected_index due to the
    mid-run billing cutoff -- accuracy below is computed over those valid
    predictions only, reported as such)
  - finetuning/experiments/experiment2/results/evaluation_final.jsonl
    (Experiment 2's CANONICAL result: the full 50-example run using strict
    json_schema output constraints, 0 format failures. The earlier
    evaluation_initial.jsonl -- json_object mode, 26 initial format failures --
    is preserved as historical data but is no longer read here.)

Usage:
    python compare_experiments_final.py
"""

import os
import sys
from collections import Counter

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(_THIS_DIR)))
_SHARED_DIR = os.path.join(_REPO_ROOT, "finetuning", "shared")
if _SHARED_DIR not in sys.path:
	sys.path.insert(0, _SHARED_DIR)

from dataset_io import load_jsonl, write_json_atomic  # noqa: E402

_FINETUNING_DIR = os.path.join(_REPO_ROOT, "finetuning")
TEST_FILE = os.path.join(_FINETUNING_DIR, "data", "splits", "test.jsonl")
EXP1_COMPARISON_FILE = os.path.join(_FINETUNING_DIR, "experiments", "experiment1", "results", "eval_comparison_together.jsonl")
EXP2_COMPARISON_FILE = os.path.join(_FINETUNING_DIR, "experiments", "experiment2", "results", "evaluation_final.jsonl")
REPORT_FILE = os.path.join(_FINETUNING_DIR, "results", "final_comparison_report.json")

BOTH_CORRECT = "both_correct"
FINETUNED_IMPROVED = "finetuned_improved"
FINETUNED_REGRESSED = "finetuned_regressed"
BOTH_WRONG = "both_wrong"


def classify(model_match, v7_match):
	if model_match and v7_match:
		return BOTH_CORRECT
	if model_match and not v7_match:
		return FINETUNED_IMPROVED
	if v7_match and not model_match:
		return FINETUNED_REGRESSED
	return BOTH_WRONG


def summarize(name, indices_by_id, human_by_id, v7_by_id):
	valid_ids = [sid for sid in indices_by_id if indices_by_id[sid] is not None]
	n_valid = len(valid_ids)
	n_total = len(human_by_id)
	if n_valid == 0:
		return {"model": name, "available": False}

	correct = sum(1 for sid in valid_ids if indices_by_id[sid] == human_by_id[sid])
	category_counts = Counter()
	idx0_count = 0
	idx0_correct = 0
	for sid in valid_ids:
		pred = indices_by_id[sid]
		human = human_by_id[sid]
		v7 = v7_by_id[sid]
		model_match = pred == human
		v7_match = v7 == human
		category_counts[classify(model_match, v7_match)] += 1
		if pred == 0:
			idx0_count += 1
			if pred == human:
				idx0_correct += 1

	return {
		"model": name,
		"available": True,
		"n_test_examples_total": n_total,
		"n_valid_predictions": n_valid,
		"partial_run_warning": n_valid < n_total,
		"correct": correct,
		"accuracy_over_valid": correct / n_valid,
		"category_counts_vs_v7": dict(category_counts),
		"index0_selection_rate": idx0_count / n_valid,
		"index0_count": idx0_count,
		"accuracy_when_index0_selected": (idx0_correct / idx0_count) if idx0_count else None,
	}


def main():
	test_records = load_jsonl(TEST_FILE)
	if not test_records:
		print(f"No records found in {TEST_FILE}.")
		sys.exit(1)

	human_by_id = {str(r["source_id"]): r["selected_index"] for r in test_records}
	v7_by_id = {str(r["source_id"]): r.get("current_v7_index") for r in test_records}

	# V7 "predictions" for the summarize() helper are just its own stored index.
	v7_indices_by_id = dict(v7_by_id)

	exp1_rows = load_jsonl(EXP1_COMPARISON_FILE)
	exp1_by_id = {str(r["source_id"]): r["finetuned_selected_index"] for r in exp1_rows} if exp1_rows else {}
	# Ensure every test source_id is represented (None if missing from the comparison file).
	exp1_indices_by_id = {sid: exp1_by_id.get(sid) for sid in human_by_id}

	exp2_rows = load_jsonl(EXP2_COMPARISON_FILE)
	exp2_by_id = {str(r["source_id"]): r["finetuned_selected_index"] for r in exp2_rows} if exp2_rows else {}
	exp2_indices_by_id = {sid: exp2_by_id.get(sid) for sid in human_by_id}

	results = {
		"v7": summarize("v7", v7_indices_by_id, human_by_id, v7_by_id),
		"experiment1": summarize("experiment1", exp1_indices_by_id, human_by_id, v7_by_id),
		"experiment2": summarize("experiment2", exp2_indices_by_id, human_by_id, v7_by_id),
	}
	write_json_atomic(REPORT_FILE, results)

	print("=" * 70)
	print("Human vs V7 vs Experiment 1 vs Experiment 2 -- held-out test set (n=50)")
	print("=" * 70)
	for key in ("v7", "experiment1", "experiment2"):
		r = results[key]
		print()
		print(f"[{key}]")
		if not r["available"]:
			print("  not available yet (no comparison file / no valid predictions)")
			continue
		warn = "  (PARTIAL RUN -- not all 50 completed)" if r["partial_run_warning"] else ""
		print(f"  accuracy vs human: {r['correct']}/{r['n_valid_predictions']} = {r['accuracy_over_valid']:.1%}{warn}")
		if key != "v7":
			print(f"  vs V7: {r['category_counts_vs_v7']}")
		print(f"  index-0 selection rate: {r['index0_selection_rate']:.1%} ({r['index0_count']}/{r['n_valid_predictions']})")
		acc0 = r["accuracy_when_index0_selected"]
		print(f"  accuracy when index-0 selected: {acc0:.1%}" if acc0 is not None else "  accuracy when index-0 selected: n/a (never selected index 0)")

	print()
	print(f"Full report: {REPORT_FILE}")


if __name__ == "__main__":
	main()
