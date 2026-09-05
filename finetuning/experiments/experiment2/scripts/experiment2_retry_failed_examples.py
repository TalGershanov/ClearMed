"""
Experiment 2: retry just the examples that failed (returned no valid prediction) in
the previous full-50 create->evaluate->stop run.

Reuses the same v2 DMI create/wait/stop lifecycle from experiment2_deploy_evaluate_stop
(same finally-protected shutdown, same verify-stopped check), but only re-queries the
rows in evaluation_initial.jsonl (base.COMPARISON_FILE) where finetuned_selected_index is null,
updating them in place. Every retried row now also records the real failure reason
(finetuned_error) if it fails again, instead of silently discarding it.

Does NOT touch Experiment 1 files. Does NOT run on import -- nothing is created
until this script is executed and reaches create_endpoint_and_deployment().

Usage:
    python experiment2_retry_failed_examples.py
"""

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

MAX_ATTEMPTS_PER_EXAMPLE = 3


def retry_failed(model_name):
	comparison = load_jsonl(base.COMPARISON_FILE)
	if not comparison:
		raise RuntimeError(f"No comparison file found at {base.COMPARISON_FILE}. Run the full eval first.")

	failed_indices = [i for i, r in enumerate(comparison) if r["finetuned_selected_index"] is None]
	print(f"{len(failed_indices)} / {len(comparison)} rows need a retry.")
	if not failed_indices:
		print("Nothing to retry.")
		return comparison

	client = Together()
	still_failed = []

	for pos in failed_indices:
		row = comparison[pos]
		record = {
			"source_id": row["source_id"],
			"term": row["term"],
			"candidates": row["candidates"],
			"selected_index": row["human_selected_index"],
			"current_v7_index": row["v7_selected_index"],
		}

		ft_index, ft_error = None, None
		for attempt in range(1, MAX_ATTEMPTS_PER_EXAMPLE + 1):
			ft_index, ft_error = base.call_finetuned_model(client, model_name, record)
			if ft_index is not None:
				break
			print(f"  attempt {attempt}/{MAX_ATTEMPTS_PER_EXAMPLE} FAILED for {row['term']!r}: {ft_error}")

		human_index = row["human_selected_index"]
		v7_index = row["v7_selected_index"]
		ft_match = ft_index == human_index
		v7_match = v7_index == human_index
		row["finetuned_selected_index"] = ft_index
		row["finetuned_error"] = ft_error
		row["finetuned_selected_sentence"] = base.sentence_at(row["candidates"], ft_index)
		row["finetuned_agrees_with_human"] = ft_match
		row["category"] = base.classify(ft_match, v7_match)

		if ft_index is None:
			still_failed.append(row["term"])
		else:
			print(f"  recovered {row['term']!r}: ft={ft_index} human={human_index} v7={v7_index} -> {row['category']}")

		# Incremental save after every retried row.
		write_jsonl_atomic(base.COMPARISON_FILE, comparison)

	print()
	print(f"Still failed after up to {MAX_ATTEMPTS_PER_EXAMPLE} attempts: {len(still_failed)}: {still_failed}")
	return comparison


def recompute_summary(model_name, comparison):
	valid = [r for r in comparison if r["finetuned_selected_index"] is not None]
	n_total = len(comparison)
	n_valid = len(valid)

	ft_correct = sum(1 for r in valid if r["finetuned_agrees_with_human"])
	v7_correct = sum(1 for r in valid if r["v7_selected_index"] == r["human_selected_index"])
	idx0_count = sum(1 for r in valid if r["finetuned_selected_index"] == 0)
	idx0_correct = sum(1 for r in valid if r["finetuned_selected_index"] == 0 and r["finetuned_agrees_with_human"])

	from collections import Counter
	category_counts = Counter(r["category"] for r in valid)

	summary = {
		"model": model_name,
		"INCOMPLETE_RUN": n_valid < n_total,
		"n_test_examples_total": n_total,
		"n_completed": n_valid,
		"n_failed_calls": n_total - n_valid,
		"finetuned_correct": ft_correct,
		"finetuned_accuracy": ft_correct / n_valid if n_valid else None,
		"v7_correct": v7_correct,
		"v7_accuracy": v7_correct / n_valid if n_valid else None,
		"accuracy_delta_percentage_points": ((ft_correct - v7_correct) / n_valid * 100) if n_valid else None,
		"category_counts": dict(category_counts),
		"index0_selection_rate": idx0_count / n_valid if n_valid else None,
		"accuracy_when_index0_selected": idx0_correct / idx0_count if idx0_count else None,
	}
	write_json_atomic(base.SUMMARY_FILE, summary)
	return summary


def main():
	if not os.environ.get("TOGETHER_API_KEY"):
		print("TOGETHER_API_KEY is not set in the environment. Stopping.")
		sys.exit(1)
	if not os.path.exists(base.RESULT_FILE):
		print(f"{base.RESULT_FILE} not found. Run finetune_launch_together_experiment2.py first.")
		sys.exit(1)
	if not os.path.exists(base.COMPARISON_FILE):
		print(f"{base.COMPARISON_FILE} not found. Run the full eval first.")
		sys.exit(1)

	project_id, endpoint_id, deployment_id, endpoint_name = base.create_endpoint_and_deployment()
	try:
		base.wait_ready(project_id, endpoint_id, deployment_id)
		comparison = retry_failed(endpoint_name)
		summary = recompute_summary(endpoint_name, comparison)
	finally:
		base.stop_deployment_and_verify(project_id, endpoint_id, deployment_id)

	print()
	print("=" * 60)
	print(f"Final: {summary['n_completed']}/{summary['n_test_examples_total']} completed")
	if summary["n_completed"]:
		print(f"Fine-tuned accuracy: {summary['finetuned_correct']}/{summary['n_completed']} = {summary['finetuned_accuracy']:.1%}")
		print(f"V7 accuracy (same subset): {summary['v7_correct']}/{summary['n_completed']} = {summary['v7_accuracy']:.1%}")
		print(f"Category counts: {summary['category_counts']}")
	print(f"Summary saved to {base.SUMMARY_FILE}")


if __name__ == "__main__":
	main()
