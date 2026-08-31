"""
Experiment 3: merge the 37 previously-recovered judgments (from existing V7/
Experiment 2 review) with the 13 freshly collected judgments (from
experiment3_review_needs_review_13.py) into the final human-reviewed Experiment 3
result on the fixed 50-example held-out test set, then compare V7 / Experiment 2 /
Experiment 3 on the same 50 using human-reviewed status throughout (not just
strict index match).

Purely local. Does not train anything, does not call any API.

Reads:
  - finetuning/experiments/experiment3/review/exp3_review_reused_judgments.csv (37 resolved + 13 blank)
  - finetuning/experiments/experiment3/review/exp3_new_judgments_13.jsonl (the 13 fresh judgments)
  - finetuning/experiments/experiment2/review/manual_review_final.csv (V7 + Exp2 human-reviewed status)

Writes:
  - finetuning/experiments/experiment3/review/exp3_final_human_reviewed.csv (all 50, fully judged)
  - finetuning/experiments/experiment3/results/exp3_final_human_reviewed_summary.json

Usage:
    python experiment3_final_human_reviewed_report.py
"""

import csv
import json
import os
import sys
from collections import Counter

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(_THIS_DIR))))
_SHARED_DIR = os.path.join(_REPO_ROOT, "finetuning", "shared")
if _SHARED_DIR not in sys.path:
	sys.path.insert(0, _SHARED_DIR)

from dataset_io import load_jsonl, write_json_atomic  # noqa: E402

EXP3_DIR = os.path.join(_REPO_ROOT, "finetuning", "experiments", "experiment3")
REUSED_REVIEW_CSV = os.path.join(EXP3_DIR, "review", "exp3_review_reused_judgments.csv")
NEW_JUDGMENTS_FILE = os.path.join(EXP3_DIR, "review", "exp3_new_judgments_13.jsonl")
EXP2_REVIEW_CSV = os.path.join(_REPO_ROOT, "finetuning", "experiments", "experiment2", "review", "manual_review_final.csv")

OUT_CSV = os.path.join(EXP3_DIR, "review", "exp3_final_human_reviewed.csv")
OUT_SUMMARY = os.path.join(EXP3_DIR, "results", "exp3_final_human_reviewed_summary.json")

RANK = {"correct": 2, "accepted": 1, "wrong": 0}


def main():
	with open(REUSED_REVIEW_CSV, encoding="utf-8") as f:
		reused_rows = list(csv.DictReader(f))
	new_judgments = {str(j["source_id"]): j["human_review"] for j in load_jsonl(NEW_JUDGMENTS_FILE)}

	missing = [r["term"] for r in reused_rows if r["provenance"] == "new_manual_review_required" and str(r["source_id"]) not in new_judgments]
	if missing:
		print(f"Still missing new judgments for {len(missing)} terms: {missing}")
		print(f"Run experiment3_review_needs_review_13.py to finish reviewing before running this report.")
		sys.exit(1)

	with open(EXP2_REVIEW_CSV, encoding="utf-8") as f:
		exp2_review_by_term = {r["term"]: r for r in csv.DictReader(f)}

	final_rows = []
	for r in reused_rows:
		sid = str(r["source_id"])
		if r["provenance"] == "new_manual_review_required":
			human_review = new_judgments[sid]
			source = "new_review_2026"
		else:
			human_review = r["human_review"]
			source = r["provenance"]

		exp2_row = exp2_review_by_term[r["term"]]
		final_rows.append({
			"source_id": r["source_id"],
			"term": r["term"],
			"human_best_index": r["human_best_index"],
			"exp3_selected_index": r["exp3_selected_index"],
			"exp3_human_review": human_review,
			"exp3_judgment_source": source,
			"v7_selected_index": exp2_row["V7_selected_index"],
			"v7_human_review": exp2_row["human_review on v7"],
			"exp2_selected_index": exp2_row["new_exp2_selected_index"],
			"exp2_human_review": exp2_row["human_review on fine tuning"],
		})

	fields = list(final_rows[0].keys())
	with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
		w = csv.DictWriter(f, fieldnames=fields)
		w.writeheader()
		for r in final_rows:
			w.writerow(r)

	n = len(final_rows)

	def counts_and_acc(status_key):
		c = Counter(r[status_key] for r in final_rows)
		correct, accepted, wrong = c.get("correct", 0), c.get("accepted", 0), c.get("wrong", 0)
		return {
			"correct": correct, "accepted": accepted, "wrong": wrong,
			"strict_accuracy": correct / n,
			"acceptable_inclusive_accuracy": (correct + accepted) / n,
		}

	v7_stats = counts_and_acc("v7_human_review")
	exp2_stats = counts_and_acc("exp2_human_review")
	exp3_stats = counts_and_acc("exp3_human_review")

	genuine_improvements = []
	genuine_regressions = []
	index_changed_both_acceptable = []
	unchanged = []

	for r in final_rows:
		exp2_status, exp3_status = r["exp2_human_review"], r["exp3_human_review"]
		exp2_rank, exp3_rank = RANK[exp2_status], RANK[exp3_status]
		index_changed = r["exp2_selected_index"] != r["exp3_selected_index"]

		if exp2_status == "wrong" and exp3_status in ("correct", "accepted"):
			genuine_improvements.append(r["term"])
		elif exp2_status in ("correct", "accepted") and exp3_status == "wrong":
			genuine_regressions.append(r["term"])
		elif index_changed and exp2_status in ("correct", "accepted") and exp3_status in ("correct", "accepted"):
			index_changed_both_acceptable.append(r["term"])
		else:
			unchanged.append(r["term"])

	summary = {
		"n_examples": n,
		"v7_human_reviewed": v7_stats,
		"experiment2_human_reviewed": exp2_stats,
		"experiment3_human_reviewed": exp3_stats,
		"experiment3_vs_experiment2": {
			"genuine_improvements": {"count": len(genuine_improvements), "terms": genuine_improvements},
			"genuine_regressions": {"count": len(genuine_regressions), "terms": genuine_regressions},
			"index_changed_both_acceptable": {"count": len(index_changed_both_acceptable), "terms": index_changed_both_acceptable},
			"unchanged": {"count": len(unchanged)},
		},
	}
	write_json_atomic(OUT_SUMMARY, summary)

	print(f"Final human-reviewed CSV: {OUT_CSV}")
	print(f"Summary: {OUT_SUMMARY}")
	print()
	print(f"{'System':<15}{'Correct':>10}{'Accepted':>10}{'Wrong':>8}{'Strict':>10}{'Incl.':>10}")
	for name, s in [("V7", v7_stats), ("Experiment 2", exp2_stats), ("Experiment 3", exp3_stats)]:
		print(f"{name:<15}{s['correct']:>10}{s['accepted']:>10}{s['wrong']:>8}{s['strict_accuracy']:>9.1%}{s['acceptable_inclusive_accuracy']:>10.1%}")
	print()
	print(f"Exp3 vs Exp2 (human-reviewed):")
	print(f"  Genuine improvements ({len(genuine_improvements)}): {genuine_improvements}")
	print(f"  Genuine regressions ({len(genuine_regressions)}): {genuine_regressions}")
	print(f"  Index changed, both acceptable ({len(index_changed_both_acceptable)}): {index_changed_both_acceptable}")
	print(f"  Unchanged ({len(unchanged)})")


if __name__ == "__main__":
	main()
