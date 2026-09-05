"""
Experiment 3: single safe workflow --
    create dedicated endpoint -> wait until READY -> evaluate all 50 held-out test
    examples (saving after every example) -> stop the endpoint (always, via a
    finally block) -> verify 0 active replicas.

This is Experiment 2's canonical evaluation (experiment2_evaluate_jsonschema_full50.py
/ experiment2_deploy_evaluate_stop.py) applied to the Experiment 3 fine-tuned model.
To guarantee the comparison is fair, the actual inference call is not
reimplemented here -- it is imported directly from experiment2_deploy_evaluate_stop
(call_finetuned_model, build_selected_index_schema, classify, sentence_at,
index0_stats, the category constants, and the low-level _request/whoami REST
helpers), so Experiment 3 runs through the byte-identical prompt, strict
json_schema response_format, and unset-temperature (server default) inference
code Experiment 2's canonical run used. Nothing about the request shape is
re-typed by hand here.

What IS Experiment-3-specific (kept in this file, never touching experiment2/'s
own paths):
  - the fine-tuning RESULT_FILE this reads the model_object_id from
  - the endpoint NAME/metadata file used to create/track/stop the deployment
  - the output paths for the per-example comparison + summary

finetuning/data/splits/test.jsonl is opened read-only and never modified.

Does NOT run anything on import. Nothing is created until this file is executed
and reaches create_endpoint_and_deployment().

Usage:
    python experiment3_deploy_evaluate_stop.py
"""

import os
import sys
import time

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(_THIS_DIR))))
_SERVER_INIT_DIR = os.path.join(_REPO_ROOT, "server_init")
_SHARED_DIR = os.path.join(_REPO_ROOT, "finetuning", "shared")
_DATA_SCRIPTS_DIR = os.path.join(_REPO_ROOT, "finetuning", "scripts", "data")
_EXP2_SCRIPTS_DIR = os.path.join(_REPO_ROOT, "finetuning", "experiments", "experiment2", "scripts")
for _path in (_REPO_ROOT, _SERVER_INIT_DIR, _SHARED_DIR, _DATA_SCRIPTS_DIR, _EXP2_SCRIPTS_DIR):
	if _path not in sys.path:
		sys.path.insert(0, _path)

from dotenv import load_dotenv  # noqa: E402
from together import Together  # noqa: E402

import experiment2_deploy_evaluate_stop as exp2_base  # noqa: E402
from dataset_io import load_jsonl, load_json, write_json_atomic, write_jsonl_atomic  # noqa: E402

load_dotenv()

TEST_FILE = exp2_base.TEST_FILE  # finetuning/data/splits/test.jsonl -- shared, read-only, untouched

EXP3_DIR = os.path.join(_REPO_ROOT, "finetuning", "experiments", "experiment3")
RESULT_FILE = os.path.join(EXP3_DIR, "results", "finetune_result_together_exp3.json")
ENDPOINT_FILE = os.path.join(EXP3_DIR, "deployment", "dedicated_endpoint_exp3.json")
COMPARISON_FILE = os.path.join(EXP3_DIR, "results", "evaluation_exp3.jsonl")
SUMMARY_FILE = os.path.join(EXP3_DIR, "results", "evaluation_exp3_summary.json")

API_BASE = exp2_base.API_BASE
ENDPOINT_NAME = "clearmed-short-explanation-eval-exp3"
DEPLOYMENT_NAME = "eval"
POLL_SECONDS = exp2_base.POLL_SECONDS
READY_TIMEOUT_SECONDS = exp2_base.READY_TIMEOUT_SECONDS
STOP_TIMEOUT_SECONDS = exp2_base.STOP_TIMEOUT_SECONDS

_request = exp2_base._request
whoami = exp2_base.whoami


# --- Step 1: create endpoint + deployment (Experiment-3-specific paths only) -----

def create_endpoint_and_deployment():
	result = load_json(RESULT_FILE, None)
	if result is None or not result.get("job_id"):
		raise RuntimeError(f"No job_id found in {RESULT_FILE}. Run finetune_launch_together_experiment3.py first.")

	client = Together()
	job = client.fine_tuning.retrieve(id=result["job_id"])
	model_object_id = job.model_dump().get("model_object_id")
	if not model_object_id:
		raise RuntimeError("No model_object_id on the Experiment 3 fine-tuning job -- cannot deploy.")

	who = whoami()
	project_id = who["project_id"]
	print(f"Project: {who['project_slug']} ({project_id})")

	model_resource = f"projects/{project_id}/models/{model_object_id}"
	import urllib.parse
	ref = urllib.parse.urlencode({"referenceModel": model_resource})
	configs = _request("GET", f"/v2/projects/{project_id}/configs?{ref}")["data"]
	if not configs:
		raise RuntimeError(f"No deployable configs found for {model_resource}.")
	config = configs[0]
	config_resource = f"projects/{config['projectId']}/configs/{config['id']}"
	selectors = {s["key"]: s["value"] for s in config["selectors"]}
	print(f"Using config {config['id']}: {selectors}")

	existing = _request("GET", f"/v2/projects/{project_id}/endpoints")["data"]
	full_name = f"{who['project_slug']}/{ENDPOINT_NAME}"
	match = next((e for e in existing if e["name"] == full_name), None)

	if match:
		endpoint_id = match["id"]
		deployment_id = match["deployments"][0]["id"]
		print(f"Reusing existing endpoint {endpoint_id} / deployment {deployment_id} ({full_name}) ...")
		print("Restarting deployment (autoscaling -> 1/1) ...")
		_request(
			"PATCH",
			f"/v2/projects/{project_id}/endpoints/{endpoint_id}/deployments/{deployment_id}",
			{"autoscaling": {"minReplicas": 1, "maxReplicas": 1}},
		)
		_request(
			"PATCH",
			f"/v2/projects/{project_id}/endpoints/{endpoint_id}",
			{"trafficSplit": [{"deploymentId": deployment_id, "weight": 1}]},
		)
		return project_id, endpoint_id, deployment_id, match["name"]

	print(f"Creating endpoint {ENDPOINT_NAME} ...")
	endpoint = _request("POST", f"/v2/projects/{project_id}/endpoints", {"name": ENDPOINT_NAME})
	endpoint_id = endpoint["id"]
	print(f"  endpoint id: {endpoint_id}, name: {endpoint['name']}")

	try:
		print("Creating deployment ...")
		deployment = _request(
			"POST",
			f"/v2/projects/{project_id}/endpoints/{endpoint_id}/deployments",
			{
				"name": DEPLOYMENT_NAME,
				"model": model_resource,
				"config": config_resource,
				"autoscaling": {"minReplicas": 1, "maxReplicas": 1},
			},
		)
		deployment_id = deployment["id"]
		print(f"  deployment id: {deployment_id}, name: {deployment['name']}")

		print("Routing 100% of traffic to the new deployment ...")
		_request(
			"PATCH",
			f"/v2/projects/{project_id}/endpoints/{endpoint_id}",
			{"trafficSplit": [{"deploymentId": deployment_id, "weight": 1}]},
		)
	except Exception:
		print("Deployment creation failed after the endpoint was created -- attempting to delete the orphaned endpoint ...")
		try:
			_request("DELETE", f"/v2/projects/{project_id}/endpoints/{endpoint_id}")
			print("  orphaned endpoint deleted.")
		except RuntimeError as cleanup_exc:
			print(f"  WARNING: could not auto-delete orphaned endpoint {endpoint_id}: {cleanup_exc}")
			print("  Delete it manually at https://api.together.ai/endpoints")
		raise

	write_json_atomic(ENDPOINT_FILE, {
		"project_id": project_id,
		"endpoint_id": endpoint_id,
		"endpoint_name": endpoint["name"],
		"deployment_id": deployment_id,
	})
	return project_id, endpoint_id, deployment_id, endpoint["name"]


# --- Step 2: wait for READY (identical logic, Experiment-3-scoped) ---------------

def wait_ready(project_id, endpoint_id, deployment_id):
	print("Waiting for the deployment to become READY (first boot can take ~20 minutes) ...")
	deadline = time.time() + READY_TIMEOUT_SECONDS
	while True:
		d = _request("GET", f"/v2/projects/{project_id}/endpoints/{endpoint_id}/deployments/{deployment_id}")
		state = d["status"]["state"]
		print(f"  state: {state}  ready={d['status'].get('readyReplicas', 0)}  msg={d['status'].get('message', '')}")
		if state == "DEPLOYMENT_STATE_READY":
			return
		if state in ("DEPLOYMENT_STATE_FAILED", "DEPLOYMENT_STATE_STOPPED", "DEPLOYMENT_STATE_STOPPING"):
			raise RuntimeError(f"Deployment ended in state {state} before becoming ready.")
		if time.time() > deadline:
			raise RuntimeError("Timed out waiting for READY.")
		time.sleep(POLL_SECONDS)


# --- Step 3: evaluate the 50 held-out test examples ------------------------------
# Reuses exp2_base.call_finetuned_model/build_selected_index_schema/classify/
# sentence_at/index0_stats UNCHANGED -- same prompt, same strict json_schema,
# same unset-temperature behavior as Experiment 2's canonical evaluation.

def run_evaluation(model_name):
	test_records = load_jsonl(TEST_FILE)
	if not test_records:
		raise RuntimeError(f"No records found in {TEST_FILE}.")

	client = Together()
	print(f"Evaluating Experiment 3 model {model_name} (json_schema, no temperature override) "
	      f"on {len(test_records)} held-out records ...")

	comparison = []
	category_counts = {
		exp2_base.BOTH_CORRECT: 0, exp2_base.FINETUNED_IMPROVED: 0,
		exp2_base.FINETUNED_REGRESSED: 0, exp2_base.BOTH_WRONG: 0,
	}
	ft_correct = 0
	v7_correct = 0

	for i, record in enumerate(test_records, start=1):
		candidates = record["candidates"]
		human_index = record["selected_index"]
		v7_index = record.get("current_v7_index")
		ft_index, ft_error = exp2_base.call_finetuned_model(client, model_name, record)

		ft_match = ft_index == human_index
		v7_match = v7_index == human_index
		if ft_match:
			ft_correct += 1
		if v7_match:
			v7_correct += 1

		category = exp2_base.classify(ft_match, v7_match)
		category_counts[category] += 1

		comparison.append({
			"source_id": record["source_id"],
			"term": record["term"],
			"candidates": candidates,
			"human_selected_index": human_index,
			"finetuned_selected_index": ft_index,
			"finetuned_error": ft_error,
			"v7_selected_index": v7_index,
			"human_selected_sentence": exp2_base.sentence_at(candidates, human_index),
			"finetuned_selected_sentence": exp2_base.sentence_at(candidates, ft_index),
			"v7_selected_sentence": exp2_base.sentence_at(candidates, v7_index),
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
		"temperature": "unset (server default, same as Experiment 2's canonical evaluation)",
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
	print(f"Experiment 3 strict accuracy vs human: {ft_correct}/{n_total} = {ft_accuracy_strict:.1%}")
	print(f"V7 strict accuracy vs human:           {v7_correct}/{n_total} = {v7_accuracy_strict:.1%}")
	print(f"Category counts: {category_counts}")
	print(f"Comparison saved to {COMPARISON_FILE}")
	print(f"Summary saved to {SUMMARY_FILE}")

	return comparison


# --- Step 4: stop the deployment (Experiment-3-scoped) + verify -----------------

def stop_deployment_and_verify(project_id, endpoint_id, deployment_id):
	print("Scaling deployment to 0/0 (this is what stops billing) ...")
	try:
		_request(
			"PATCH",
			f"/v2/projects/{project_id}/endpoints/{endpoint_id}/deployments/{deployment_id}",
			{"autoscaling": {"minReplicas": 0, "maxReplicas": 0}},
		)
	except RuntimeError as exc:
		print(f"WARNING: failed to request stop: {exc}")
		print(f"MANUAL ACTION REQUIRED: stop deployment {deployment_id} at https://api.together.ai/endpoints")
		return None

	deadline = time.time() + STOP_TIMEOUT_SECONDS
	while time.time() < deadline:
		d = _request("GET", f"/v2/projects/{project_id}/endpoints/{endpoint_id}/deployments/{deployment_id}")
		state = d["status"]["state"]
		print(f"  state: {state}  ready={d['status'].get('readyReplicas', 0)}")
		if state == "DEPLOYMENT_STATE_STOPPED":
			break
		time.sleep(POLL_SECONDS)

	verify = _request("GET", f"/v2/projects/{project_id}/endpoints/{endpoint_id}/deployments/{deployment_id}")
	state_ok = verify["status"]["state"] == "DEPLOYMENT_STATE_STOPPED"
	replicas_ok = verify["status"].get("readyReplicas", 0) == 0
	if state_ok and replicas_ok:
		print(f"VERIFIED: deployment {deployment_id} is STOPPED with 0 active replicas. Billing has stopped.")
	else:
		print(f"WARNING: could not verify the deployment fully stopped. state={verify['status']}")
		print(f"MANUAL ACTION REQUIRED: check https://api.together.ai/endpoints for {deployment_id}")

	try:
		_request("PATCH", f"/v2/projects/{project_id}/endpoints/{endpoint_id}", {"trafficSplit": []})
		_request("DELETE", f"/v2/projects/{project_id}/endpoints/{endpoint_id}/deployments/{deployment_id}")
		_request("DELETE", f"/v2/projects/{project_id}/endpoints/{endpoint_id}")
		if os.path.exists(ENDPOINT_FILE):
			os.remove(ENDPOINT_FILE)
		print("Deployment and endpoint fully deleted.")
	except RuntimeError as exc:
		print("Stopped (billing halted), but full record deletion via the API failed (known limitation")
		print("for a single-deployment endpoint's empty traffic split):")
		print(f"  {exc}")
		print("Safe to leave as-is, or delete manually at https://api.together.ai/endpoints")

	return verify


def main():
	if not os.environ.get("TOGETHER_API_KEY"):
		print("TOGETHER_API_KEY is not set in the environment. Stopping.")
		sys.exit(1)
	if not os.path.exists(RESULT_FILE):
		print(f"{RESULT_FILE} not found. Run finetune_launch_together_experiment3.py first.")
		sys.exit(1)
	if not os.path.exists(TEST_FILE):
		print(f"{TEST_FILE} not found.")
		sys.exit(1)

	project_id, endpoint_id, deployment_id, endpoint_name = create_endpoint_and_deployment()
	try:
		wait_ready(project_id, endpoint_id, deployment_id)
		run_evaluation(endpoint_name)
	finally:
		stop_deployment_and_verify(project_id, endpoint_id, deployment_id)


if __name__ == "__main__":
	main()
