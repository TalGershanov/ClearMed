"""
Experiment 2: full 50-example evaluation using the updated strict json_schema
inference (response_format = build_selected_index_schema(n), no temperature
override -- same server-default temperature as the original Experiment 2
evaluation). Everything else (model, prompts, test set, candidate generation) is
unchanged from the original run.

This run is CANONICAL: saved as evaluation_final.* (results) / manual_review_final.csv
(review), distinct from the original json_object-based run (now preserved as
evaluation_initial.* / manual_review_initial.csv, historical only) and the two
11/12-example mini-tests. compare_experiments_final.py reads evaluation_final.jsonl
as Experiment 2's result.

Same create -> wait READY -> evaluate -> finally: stop + verify lifecycle as
experiment2_deploy_evaluate_stop.py. Reuses call_finetuned_model (json_schema, no
temperature) from that module directly, so this test isolates only "full 50 run"
vs. "mini-test run" -- the inference call itself is identical code.

Usage:
    python experiment2_evaluate_jsonschema_full50.py
"""

import csv
import os
import sys

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(_THIS_DIR))))
_SHARED_DIR = os.path.join(_REPO_ROOT, "finetuning", "shared")
if _SHARED_DIR not in sys.path:
	sys.path.insert(0, _SHARED_DIR)

import experiment2_deploy_evaluate_stop as base  # noqa: E402
from dataset_io import load_jsonl, write_jsonl_atomic, write_json_atomic  # noqa: E402
from together import Together  # noqa: E402

EXP2_DIR = os.path.join(_REPO_ROOT, "finetuning", "experiments", "experiment2")
COMPARISON_FILE = os.path.join(EXP2_DIR, "results", "evaluation_final.jsonl")
SUMMARY_FILE = os.path.join(EXP2_DIR, "results", "evaluation_final_summary.json")
REVIEW_CSV_FILE = os.path.join(EXP2_DIR, "review", "manual_review_final.csv")


def run_full_evaluation(model_name):
	test_records = load_jsonl(base.TEST_FILE)
	if not test_records:
		raise RuntimeError(f"No records found in {base.TEST_FILE}.")

	client = Together()
	print(f"Evaluating {model_name} (json_schema, no temperature override) on {len(test_records)} held-out records ...")

	comparison = []
	category_counts = {base.BOTH_CORRECT: 0, base.FINETUNED_IMPROVED: 0, base.FINETUNED_REGRESSED: 0, base.BOTH_WRONG: 0}
	ft_correct = 0
	v7_correct = 0

	for i, record in enumerate(test_records, start=1):
		candidates = record["candidates"]
		human_index = record["selected_index"]
		v7_index = record.get("current_v7_index")
		ft_index, ft_error = base.call_finetuned_model(client, model_name, record)

		ft_match = ft_index == human_index
		v7_match = v7_index == human_index
		if ft_match:
			ft_correct += 1
		if v7_match:
			v7_correct += 1

		category = base.classify(ft_match, v7_match)
		category_counts[category] += 1

		comparison.append({
			"source_id": record["source_id"],
			"term": record["term"],
			"candidates": candidates,
			"human_selected_index": human_index,
			"finetuned_selected_index": ft_index,
			"finetuned_error": ft_error,
			"v7_selected_index": v7_index,
			"human_selected_sentence": base.sentence_at(candidates, human_index),
			"finetuned_selected_sentence": base.sentence_at(candidates, ft_index),
			"v7_selected_sentence": base.sentence_at(candidates, v7_index),
			"finetuned_agrees_with_human": ft_match,
			"v7_agrees_with_human": v7_match,
			"category": category,
		})

		write_jsonl_atomic(COMPARISON_FILE, comparison)
		status = "ok" if ft_error is None else f"FAILED: {ft_error}"
		print(f"  [{i}/{len(test_records)}] saved ({record['term']!r}) -- {status}")

	n_total = len(test_records)
	n_valid = sum(1 for r in comparison if r["finetuned_selected_index"] is not None)
	n_null = n_total - n_valid
	ft_accuracy_strict = ft_correct / n_total
	v7_accuracy_strict = v7_correct / n_total

	summary = {
		"model": model_name,
		"response_format": "json_schema (strict, selected_index required, additionalProperties=false, dynamic min/max)",
		"temperature": "unset (server default, same as original Experiment 2 evaluation)",
		"n_test_examples": n_total,
		"n_valid_predictions": n_valid,
		"n_null_format_failures": n_null,
		"finetuned_correct_strict": ft_correct,
		"finetuned_accuracy_strict": ft_accuracy_strict,
		"v7_correct_strict": v7_correct,
		"v7_accuracy_strict": v7_accuracy_strict,
		"accuracy_delta_percentage_points": (ft_accuracy_strict - v7_accuracy_strict) * 100,
		"category_counts": category_counts,
	}
	write_json_atomic(SUMMARY_FILE, summary)

	print()
	print("=" * 60)
	print(f"Valid predictions: {n_valid}/{n_total}")
	print(f"Null/format failures: {n_null}")
	print(f"Fine-tuned strict accuracy: {ft_correct}/{n_total} = {ft_accuracy_strict:.1%}")
	print(f"V7 strict accuracy:         {v7_correct}/{n_total} = {v7_accuracy_strict:.1%}")
	print(f"Category counts: {category_counts}")
	print(f"Comparison saved to {COMPARISON_FILE}")
	print(f"Summary saved to {SUMMARY_FILE}")

	return comparison


def build_manual_review_csv(comparison):
	fields = [
		"term", "candidate_count",
		"human_selected_index", "human_selected_sentence",
		"V7_selected_index", "V7_selected_sentence",
		"new_exp2_selected_index", "new_exp2_selected_sentence",
		"valid_prediction", "exact_match_human", "comparison_vs_v7",
		"all_candidates",
		"human_review", "review_notes",
	]
	with open(REVIEW_CSV_FILE, "w", newline="", encoding="utf-8") as f:
		w = csv.DictWriter(f, fieldnames=fields)
		w.writeheader()
		for r in comparison:
			all_candidates = " | ".join(f"{i}: {s}" for i, s in enumerate(r["candidates"]))
			w.writerow({
				"term": r["term"],
				"candidate_count": len(r["candidates"]),
				"human_selected_index": r["human_selected_index"],
				"human_selected_sentence": r["human_selected_sentence"],
				"V7_selected_index": r["v7_selected_index"],
				"V7_selected_sentence": r["v7_selected_sentence"],
				"new_exp2_selected_index": r["finetuned_selected_index"],
				"new_exp2_selected_sentence": r["finetuned_selected_sentence"] or "",
				"valid_prediction": r["finetuned_selected_index"] is not None,
				"exact_match_human": r["finetuned_agrees_with_human"],
				"comparison_vs_v7": r["category"],
				"all_candidates": all_candidates,
				"human_review": "",
				"review_notes": "",
			})
	print(f"Manual-review CSV written to {REVIEW_CSV_FILE}")


def main():
	if not os.environ.get("TOGETHER_API_KEY"):
		print("TOGETHER_API_KEY is not set in the environment. Stopping.")
		sys.exit(1)

	project_id, endpoint_id, deployment_id, endpoint_name = base.create_endpoint_and_deployment()
	try:
		base.wait_ready(project_id, endpoint_id, deployment_id)
		comparison = run_full_evaluation(endpoint_name)
	finally:
		base.stop_deployment_and_verify(project_id, endpoint_id, deployment_id)

	build_manual_review_csv(comparison)


if __name__ == "__main__":
	main()
