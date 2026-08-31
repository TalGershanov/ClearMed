"""
Experiment 3: classify each of the 50 Experiment 3 test-set predictions using ONLY
human judgments that already exist -- never inferring accepted/wrong from model
output, and never asking for a fresh review of anything already judged.

The held-out test set (finetuning/data/splits/test.jsonl) is the same fixed 50
examples used for V7, Experiment 2, and Experiment 3. Two kinds of explicit human
judgment already exist for these exact 50 examples:

  1. human_selected_index itself (the original ground-truth label) -- if
     Experiment 3 picked this index, it is correct by definition. No review
     needed.
  2. finetuning/experiments/experiment2/review/manual_review_final.csv -- your
     completed manual review of the canonical Experiment 2 run. For each of the
     50 terms, this records an explicit verdict (correct/accepted/wrong) on TWO
     specific candidate sentences: whichever one V7 selected for that term
     (human_review on v7), and whichever one Experiment 2 selected for that term
     (human_review on fine tuning). These are judgments on specific SENTENCES
     (identified by index), not blanket judgments on the whole candidate list --
     so they only transfer to Experiment 3 when Experiment 3 happened to select
     that exact same index for that exact same term.

Other artifacts checked and found NOT to contain reusable index-level judgments
for this 50-example test set:
  - finetuning/experiments/experiment2/review/manual_review_initial.csv has no
    human_review column at all (never reviewed -- superseded before review
    happened).
  - finetuning/experiments/experiment3/data/annotations_batch3.jsonl's
    acceptable_indices only exists for the 50 NEW Experiment 3 terms, which are
    a disjoint set from this fixed 50-example test set -- not applicable here.
  - finetuning/experiments/experiment2/review/error_analysis.md is prose derived
    from manual_review_final.csv, not an independent judgment source.

Classification rule per test example:
  - Experiment 3's selected_index == human_best_index         -> correct, provenance=human_best_index
  - Experiment 3's selected_index == V7's or Exp2's index AND
    that index has an explicit reviewed verdict                -> reuse that verdict, provenance=reused_exp2_review
  - otherwise (no existing judgment covers this exact index)   -> needs_review, provenance=new_manual_review_required

`reused_other_existing_review` is included as a provenance value/column for
completeness (per the requested schema) but is never populated by this script,
since no other index-level review artifact for this test set was found -- see
above.

Writes:
  finetuning/experiments/experiment3/review/exp3_review_reused_judgments.csv

Does not modify any existing annotation, review, or test-set file.

Usage:
    python experiment3_reuse_existing_review.py
"""

import csv
import os
import sys

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(_THIS_DIR))))
_SHARED_DIR = os.path.join(_REPO_ROOT, "finetuning", "shared")
if _SHARED_DIR not in sys.path:
	sys.path.insert(0, _SHARED_DIR)

from dataset_io import load_jsonl  # noqa: E402

TEST_FILE = os.path.join(_REPO_ROOT, "finetuning", "data", "splits", "test.jsonl")
EXP2_REVIEW_FINAL_CSV = os.path.join(_REPO_ROOT, "finetuning", "experiments", "experiment2", "review", "manual_review_final.csv")
EXP3_EVAL_FILE = os.path.join(_REPO_ROOT, "finetuning", "experiments", "experiment3", "results", "evaluation_exp3.jsonl")

OUT_CSV = os.path.join(_REPO_ROOT, "finetuning", "experiments", "experiment3", "review", "exp3_review_reused_judgments.csv")

VALID_VERDICTS = {"correct", "accepted", "wrong"}

PROVENANCE_HUMAN_BEST = "human_best_index"
PROVENANCE_REUSED_EXP2 = "reused_exp2_review"
PROVENANCE_REUSED_OTHER = "reused_other_existing_review"
PROVENANCE_NEEDS_REVIEW = "new_manual_review_required"


def load_exp2_review_lookup():
	with open(EXP2_REVIEW_FINAL_CSV, encoding="utf-8") as f:
		rows = list(csv.DictReader(f))
	by_term = {}
	for r in rows:
		v7_verdict = r["human_review on v7"].strip().lower()
		ft_verdict = r["human_review on fine tuning"].strip().lower()
		if v7_verdict not in VALID_VERDICTS or ft_verdict not in VALID_VERDICTS:
			raise RuntimeError(f"Unexpected/blank review verdict for term {r['term']!r}: v7={v7_verdict!r} ft={ft_verdict!r}")
		by_term[r["term"]] = {
			"v7_index": r["V7_selected_index"],
			"v7_verdict": v7_verdict,
			"exp2_index": r["new_exp2_selected_index"],
			"exp2_verdict": ft_verdict,
		}
	return by_term


def classify(term, human_best_index, exp3_index, review_lookup):
	if exp3_index == human_best_index:
		return "correct", PROVENANCE_HUMAN_BEST

	entry = review_lookup.get(term)
	if entry is None:
		raise RuntimeError(f"No Experiment 2 review entry found for term {term!r} -- unexpected for a fixed 50-example test set.")

	exp3_index_str = str(exp3_index)
	if exp3_index_str == entry["v7_index"]:
		return entry["v7_verdict"], PROVENANCE_REUSED_EXP2
	if exp3_index_str == entry["exp2_index"]:
		return entry["exp2_verdict"], PROVENANCE_REUSED_EXP2

	return "needs_review", PROVENANCE_NEEDS_REVIEW


def main():
	test_records = load_jsonl(TEST_FILE)
	exp3_by_id = {str(r["source_id"]): r for r in load_jsonl(EXP3_EVAL_FILE)}
	review_lookup = load_exp2_review_lookup()

	rows = []
	for record in test_records:
		sid = str(record["source_id"])
		term = record["term"]
		human_best_index = record["selected_index"]
		e3 = exp3_by_id[sid]
		exp3_index = e3["finetuned_selected_index"]

		status, provenance = classify(term, human_best_index, exp3_index, review_lookup)

		rows.append({
			"source_id": record["source_id"],
			"term": term,
			"candidate_count": len(record["candidates"]),
			"human_best_index": human_best_index,
			"human_best_sentence": record["candidates"][human_best_index],
			"exp3_selected_index": exp3_index,
			"exp3_selected_sentence": e3["finetuned_selected_sentence"] or "",
			"status": status,
			"provenance": provenance,
			"human_review": status if provenance != PROVENANCE_NEEDS_REVIEW else "",
			"review_notes": "" if provenance != PROVENANCE_NEEDS_REVIEW else "NEEDS NEW REVIEW -- Exp3's pick was never previously judged for this term.",
			"all_candidates": " | ".join(f"{i}: {s}" for i, s in enumerate(record["candidates"])),
		})

	fields = [
		"source_id", "term", "candidate_count",
		"human_best_index", "human_best_sentence",
		"exp3_selected_index", "exp3_selected_sentence",
		"status", "provenance", "human_review", "review_notes",
		"all_candidates",
	]
	with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
		w = csv.DictWriter(f, fieldnames=fields)
		w.writeheader()
		for r in rows:
			w.writerow(r)

	n = len(rows)
	n_auto_correct = sum(1 for r in rows if r["provenance"] == PROVENANCE_HUMAN_BEST)
	n_reused_exp2 = sum(1 for r in rows if r["provenance"] == PROVENANCE_REUSED_EXP2)
	n_reused_other = sum(1 for r in rows if r["provenance"] == PROVENANCE_REUSED_OTHER)
	n_needs_review = sum(1 for r in rows if r["provenance"] == PROVENANCE_NEEDS_REVIEW)
	n_classified = n_auto_correct + n_reused_exp2 + n_reused_other

	print(f"Total test examples: {n}")
	print(f"  classified as 'correct' (matches human_best_index):      {n_auto_correct}")
	print(f"  reused from Experiment 2's manual review (V7/Exp2 pick):  {n_reused_exp2}")
	print(f"  reused from another existing review artifact:             {n_reused_other}")
	print(f"  TOTAL classified from existing judgments:                 {n_classified}/{n}")
	print(f"  genuinely need a NEW manual judgment:                     {n_needs_review}/{n}")
	print()
	print("Terms needing a new judgment:")
	for r in rows:
		if r["provenance"] == PROVENANCE_NEEDS_REVIEW:
			print(f"  - {r['term']!r}: Exp3 picked [{r['exp3_selected_index']}] (human best was [{r['human_best_index']}])")
	print()
	print(f"Full file: {OUT_CSV}")


if __name__ == "__main__":
	main()
