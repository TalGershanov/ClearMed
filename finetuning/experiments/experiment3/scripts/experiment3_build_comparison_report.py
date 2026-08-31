"""
Experiment 3: build the cross-experiment (V7 / Experiment 2 / Experiment 3)
per-example comparison file and final report, from already-saved local results.

Purely local -- reads:
  - finetuning/data/splits/test.jsonl                              (human + V7)
  - finetuning/experiments/experiment2/results/evaluation_final.jsonl  (Exp2, canonical)
  - finetuning/experiments/experiment3/results/evaluation_exp3.jsonl   (Exp3, this run)

Writes only under finetuning/experiments/experiment3/:
  - results/exp3_vs_exp2_vs_v7_comparison.jsonl  one row per held-out example
  - results/exp3_vs_exp2_vs_v7_summary.json      aggregate report
  - review/manual_review_exp3.csv                blank human_review column,
                                                  same shape as Experiment 2's,
                                                  for the accepted-inclusive
                                                  accuracy this script cannot
                                                  compute on its own

Usage:
    python experiment3_build_comparison_report.py
"""

import csv
import os
import sys
from collections import Counter

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(_THIS_DIR))))
_SHARED_DIR = os.path.join(_REPO_ROOT, "finetuning", "shared")
if _SHARED_DIR not in sys.path:
	sys.path.insert(0, _SHARED_DIR)

from dataset_io import load_jsonl, write_jsonl_atomic, write_json_atomic  # noqa: E402

TEST_FILE = os.path.join(_REPO_ROOT, "finetuning", "data", "splits", "test.jsonl")
EXP2_EVAL_FILE = os.path.join(_REPO_ROOT, "finetuning", "experiments", "experiment2", "results", "evaluation_final.jsonl")

EXP3_DIR = os.path.join(_REPO_ROOT, "finetuning", "experiments", "experiment3")
EXP3_EVAL_FILE = os.path.join(EXP3_DIR, "results", "evaluation_exp3.jsonl")

COMPARISON_FILE = os.path.join(EXP3_DIR, "results", "exp3_vs_exp2_vs_v7_comparison.jsonl")
SUMMARY_FILE = os.path.join(EXP3_DIR, "results", "exp3_vs_exp2_vs_v7_summary.json")
REVIEW_CSV_FILE = os.path.join(EXP3_DIR, "review", "manual_review_exp3.csv")

SAME = "same"
IMPROVED = "improved"
REGRESSED = "regressed"


def status_vs_exp2(exp3_correct, exp2_correct):
	if exp3_correct == exp2_correct:
		return SAME
	return IMPROVED if exp3_correct else REGRESSED


def main():
	test_records = load_jsonl(TEST_FILE)
	exp2_rows = {str(r["source_id"]): r for r in load_jsonl(EXP2_EVAL_FILE)}
	exp3_rows = {str(r["source_id"]): r for r in load_jsonl(EXP3_EVAL_FILE)}

	missing_exp2 = [str(r["source_id"]) for r in test_records if str(r["source_id"]) not in exp2_rows]
	missing_exp3 = [str(r["source_id"]) for r in test_records if str(r["source_id"]) not in exp3_rows]
	if missing_exp2 or missing_exp3:
		raise RuntimeError(f"Missing rows -- exp2: {missing_exp2}, exp3: {missing_exp3}. Both evaluations must cover all 50.")

	comparison = []
	for record in test_records:
		sid = str(record["source_id"])
		e2 = exp2_rows[sid]
		e3 = exp3_rows[sid]

		human_index = record["selected_index"]
		v7_index = record.get("current_v7_index")
		exp2_index = e2["finetuned_selected_index"]
		exp3_index = e3["finetuned_selected_index"]

		exp2_correct = exp2_index == human_index
		exp3_correct = exp3_index == human_index
		v7_correct = v7_index == human_index

		comparison.append({
			"source_id": record["source_id"],
			"term": record["term"],
			"human_best_index": human_index,
			"v7_selected_index": v7_index,
			"v7_correct": v7_correct,
			"experiment2_selected_index": exp2_index,
			"experiment2_correct": exp2_correct,
			"experiment3_selected_index": exp3_index,
			"experiment3_correct": exp3_correct,
			"experiment3_vs_experiment2": status_vs_exp2(exp3_correct, exp2_correct),
		})

	write_jsonl_atomic(COMPARISON_FILE, comparison)

	n = len(comparison)
	n_v7_correct = sum(1 for r in comparison if r["v7_correct"])
	n_exp2_correct = sum(1 for r in comparison if r["experiment2_correct"])
	n_exp3_correct = sum(1 for r in comparison if r["experiment3_correct"])
	status_counts = Counter(r["experiment3_vs_experiment2"] for r in comparison)
	improved_terms = [r["term"] for r in comparison if r["experiment3_vs_experiment2"] == IMPROVED]
	regressed_terms = [r["term"] for r in comparison if r["experiment3_vs_experiment2"] == REGRESSED]

	summary = {
		"n_examples": n,
		"v7_accuracy_strict": n_v7_correct / n,
		"experiment2_accuracy_strict": n_exp2_correct / n,
		"experiment3_accuracy_strict": n_exp3_correct / n,
		"experiment3_minus_experiment2_percentage_points": (n_exp3_correct - n_exp2_correct) / n * 100,
		"experiment3_minus_v7_percentage_points": (n_exp3_correct - n_v7_correct) / n * 100,
		"exp3_vs_exp2_status_counts": dict(status_counts),
		"exp3_improvements_over_exp2": {"count": status_counts.get(IMPROVED, 0), "terms": improved_terms},
		"exp3_regressions_vs_exp2": {"count": status_counts.get(REGRESSED, 0), "terms": regressed_terms},
	}
	write_json_atomic(SUMMARY_FILE, summary)

	fields = [
		"term", "candidate_count",
		"human_selected_index", "human_selected_sentence",
		"V7_selected_index", "V7_selected_sentence",
		"exp2_selected_index", "exp2_selected_sentence",
		"exp3_selected_index", "exp3_selected_sentence",
		"valid_prediction", "exact_match_human", "comparison_vs_v7", "vs_exp2",
		"all_candidates",
		"human_review", "review_notes",
	]
	with open(REVIEW_CSV_FILE, "w", newline="", encoding="utf-8") as f:
		w = csv.DictWriter(f, fieldnames=fields)
		w.writeheader()
		for record in test_records:
			sid = str(record["source_id"])
			e2, e3 = exp2_rows[sid], exp3_rows[sid]
			all_candidates = " | ".join(f"{i}: {s}" for i, s in enumerate(record["candidates"]))
			w.writerow({
				"term": record["term"],
				"candidate_count": len(record["candidates"]),
				"human_selected_index": e3["human_selected_index"],
				"human_selected_sentence": e3["human_selected_sentence"],
				"V7_selected_index": e3["v7_selected_index"],
				"V7_selected_sentence": e3["v7_selected_sentence"],
				"exp2_selected_index": e2["finetuned_selected_index"],
				"exp2_selected_sentence": e2["finetuned_selected_sentence"] or "",
				"exp3_selected_index": e3["finetuned_selected_index"],
				"exp3_selected_sentence": e3["finetuned_selected_sentence"] or "",
				"valid_prediction": e3["finetuned_selected_index"] is not None,
				"exact_match_human": e3["finetuned_agrees_with_human"],
				"comparison_vs_v7": e3["category"],
				"vs_exp2": status_vs_exp2(e3["finetuned_agrees_with_human"], e2["finetuned_agrees_with_human"]),
				"all_candidates": all_candidates,
				"human_review": "",
				"review_notes": "",
			})

	print(f"Comparison file: {COMPARISON_FILE}")
	print(f"Summary: {SUMMARY_FILE}")
	print(f"Manual-review CSV (blank, for accepted-inclusive accuracy): {REVIEW_CSV_FILE}")
	print()
	print(f"V7 strict accuracy:          {n_v7_correct}/{n} = {n_v7_correct/n:.1%}")
	print(f"Experiment 2 strict accuracy: {n_exp2_correct}/{n} = {n_exp2_correct/n:.1%}")
	print(f"Experiment 3 strict accuracy: {n_exp3_correct}/{n} = {n_exp3_correct/n:.1%}")
	print(f"Exp3 vs Exp2: {dict(status_counts)}")
	print(f"  improvements ({status_counts.get(IMPROVED, 0)}): {improved_terms}")
	print(f"  regressions ({status_counts.get(REGRESSED, 0)}): {regressed_terms}")


if __name__ == "__main__":
	main()
