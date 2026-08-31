"""
Experiment 2: json_schema-only format-reliability test. NOT run yet.

Isolates the effect of switching response_format from json_object to a strict
json_schema (selected_index required, additionalProperties: false, dynamic
min/max) from the separate, previously-run temperature=0 test. Temperature is
intentionally left unset here (server default), matching the ORIGINAL Experiment 2
evaluation -- so any change in format-validity rate vs. that original run can be
attributed to json_schema alone, not to temperature.

Selection (see experiment2_json_schema_test_selection.json, built by hand in the
prior turn), 11 examples:
  - 3 examples that NEVER produced a valid prediction in the original run, even
    after 3 retries (persistent format failures)
  - 8 examples that initially failed but eventually succeeded on retry in the
    original run (intermittent format failures), in test-file order

Reuses the exact same v2 DMI create/wait/stop lifecycle as
experiment2_deploy_evaluate_stop.py (same finally-protected shutdown, same
verify-stopped check) and the same model + call_finetuned_model (now using
json_schema, no temperature override).

Does NOT run on import. Nothing is created until this script is executed and
reaches create_endpoint_and_deployment().

Usage (after approval):
    python experiment2_json_schema_test.py
"""

import os
import sys

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(_THIS_DIR))))
_SHARED_DIR = os.path.join(_REPO_ROOT, "finetuning", "shared")
if _SHARED_DIR not in sys.path:
	sys.path.insert(0, _SHARED_DIR)

import experiment2_deploy_evaluate_stop as base  # noqa: E402
from dataset_io import load_jsonl, load_json, write_jsonl_atomic, write_json_atomic  # noqa: E402
from together import Together  # noqa: E402

_EXP2_RESULTS_DIR = os.path.join(_REPO_ROOT, "finetuning", "experiments", "experiment2", "results")
SELECTION_FILE = os.path.join(_EXP2_RESULTS_DIR, "json_schema_test_selection.json")
RESULTS_FILE = os.path.join(_EXP2_RESULTS_DIR, "json_schema_test_results.jsonl")
SUMMARY_FILE = os.path.join(_EXP2_RESULTS_DIR, "json_schema_test_summary.json")


def run_test(model_name):
	selection = load_json(SELECTION_FILE, None)
	if not selection:
		raise RuntimeError(f"No selection found at {SELECTION_FILE}. Build it first.")

	test_records = {r["term"]: r for r in load_jsonl(base.TEST_FILE)}
	client = Together()

	results = []
	for row in selection:
		record = test_records[row["term"]]
		new_index, error = base.call_finetuned_model(client, model_name, record)

		valid = new_index is not None
		matches_human = valid and new_index == row["human_selected_index"]
		prev = row["previous_exp2_final_index"]
		matches_previous = (new_index == prev) if (valid and prev is not None) else None

		result = {
			"group": row["group"],
			"source_id": row["source_id"],
			"term": row["term"],
			"human_selected_index": row["human_selected_index"],
			"v7_selected_index": row["v7_selected_index"],
			"previous_exp2_final_index": prev,
			"previous_exp2_final_valid": row["previous_exp2_final_valid"],
			"new_selected_index": new_index,
			"new_valid": valid,
			"new_error": error,
			"matches_human": matches_human,
			"matches_previous_exp2_final": matches_previous,
		}
		results.append(result)
		write_jsonl_atomic(RESULTS_FILE, results)
		print(f"  [{row['group']}] {row['term']!r}: new={new_index} valid={valid} matches_human={matches_human} matches_prev={matches_previous}")
		if error:
			print(f"    error: {error}")

	n = len(results)
	n_valid = sum(1 for r in results if r["new_valid"])
	n_matches_human = sum(1 for r in results if r["matches_human"])

	summary = {
		"model": model_name,
		"response_format": "json_schema (strict, selected_index required, additionalProperties=false, dynamic min/max)",
		"temperature": "unset (server default, same as original Experiment 2 evaluation)",
		"n_examples": n,
		"n_valid": n_valid,
		"n_matches_human": n_matches_human,
		"by_group": {
			group: {
				"n": sum(1 for r in results if r["group"] == group),
				"n_valid": sum(1 for r in results if r["group"] == group and r["new_valid"]),
			}
			for group in sorted(set(r["group"] for r in results))
		},
	}
	write_json_atomic(SUMMARY_FILE, summary)
	print()
	print(f"Valid with json_schema: {n_valid}/{n}")
	print(f"By group: {summary['by_group']}")
	print(f"Results saved to {RESULTS_FILE}")
	print(f"Summary saved to {SUMMARY_FILE}")


def main():
	if not os.environ.get("TOGETHER_API_KEY"):
		print("TOGETHER_API_KEY is not set in the environment. Stopping.")
		sys.exit(1)
	if not os.path.exists(SELECTION_FILE):
		print(f"{SELECTION_FILE} not found.")
		sys.exit(1)

	project_id, endpoint_id, deployment_id, endpoint_name = base.create_endpoint_and_deployment()
	try:
		base.wait_ready(project_id, endpoint_id, deployment_id)
		run_test(endpoint_name)
	finally:
		base.stop_deployment_and_verify(project_id, endpoint_id, deployment_id)


if __name__ == "__main__":
	main()
