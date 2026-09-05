"""
Experiment 2: single safe workflow --
    create dedicated endpoint -> wait until READY -> evaluate all 50 held-out test
    examples (saving after every example) -> stop the endpoint (always, via a
    finally block) -> verify 0 active replicas.

Does NOT run anything on import. Nothing is created until you execute this file and
it reaches create_endpoint_and_deployment(). No paid resource is created by writing
or reviewing this script.

Uses the exact same evaluation logic as the (now-removed) standalone
finetune_evaluate_together_experiment2.py and the same v2 DMI REST flow as
../../experiment1/scripts/together_dmi_endpoint.py, combined into one
create -> evaluate -> stop lifecycle so the endpoint can never be left running by a
crash, timeout, or failed API call partway through evaluation.

All outputs live under finetuning/experiments/experiment2/ -- nothing in
finetuning/experiments/experiment1/ is read or written.

NOTE: this module's COMPARISON_FILE/SUMMARY_FILE point at the ORIGINAL
(json_object-based, superseded) evaluation run, now named evaluation_initial.* --
preserved as historical data. The current canonical Experiment 2 result is
evaluation_final.* (json_schema-based, 0 format failures), produced by
experiment2_evaluate_jsonschema_full50.py. This module's call_finetuned_model
already uses json_schema (see below), so re-running this file directly would
still overwrite evaluation_initial.*, not evaluation_final.* -- use
experiment2_evaluate_jsonschema_full50.py for a fresh canonical run.

Usage:
    python experiment2_deploy_evaluate_stop.py
"""

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(_THIS_DIR))))
_SERVER_INIT_DIR = os.path.join(_REPO_ROOT, "server_init")
_SHARED_DIR = os.path.join(_REPO_ROOT, "finetuning", "shared")
_DATA_SCRIPTS_DIR = os.path.join(_REPO_ROOT, "finetuning", "scripts", "data")
for _path in (_REPO_ROOT, _SERVER_INIT_DIR, _SHARED_DIR, _DATA_SCRIPTS_DIR):
	if _path not in sys.path:
		sys.path.insert(0, _path)

from dotenv import load_dotenv  # noqa: E402
from together import Together  # noqa: E402

from create_clearmed_db import _SYSTEM_PROMPT  # noqa: E402

from dataset_io import load_jsonl, load_json, write_json_atomic, write_jsonl_atomic  # noqa: E402
from finetune_prepare import user_prompt_for  # noqa: E402

load_dotenv()

TEST_FILE = os.path.join(_REPO_ROOT, "finetuning", "data", "splits", "test.jsonl")  # shared, read-only, untouched

EXP2_DIR = os.path.join(_REPO_ROOT, "finetuning", "experiments", "experiment2")
RESULT_FILE = os.path.join(EXP2_DIR, "results", "finetune_result_together_exp2.json")
ENDPOINT_FILE = os.path.join(EXP2_DIR, "deployment", "dedicated_endpoint_exp2.json")
COMPARISON_FILE = os.path.join(EXP2_DIR, "results", "evaluation_initial.jsonl")
SUMMARY_FILE = os.path.join(EXP2_DIR, "results", "evaluation_initial_summary.json")

API_BASE = "https://api.together.ai"
ENDPOINT_NAME = "clearmed-short-explanation-eval-exp2"
DEPLOYMENT_NAME = "eval"
POLL_SECONDS = 15
READY_TIMEOUT_SECONDS = 25 * 60
STOP_TIMEOUT_SECONDS = 10 * 60

BOTH_CORRECT = "both_correct"
FINETUNED_IMPROVED = "finetuned_improved"
FINETUNED_REGRESSED = "finetuned_regressed"
BOTH_WRONG = "both_wrong"


def _request(method, path, body=None):
	key = os.environ["TOGETHER_API_KEY"]
	url = API_BASE + path
	data = json.dumps(body).encode("utf-8") if body is not None else None
	req = urllib.request.Request(url, data=data, method=method, headers={
		"Authorization": f"Bearer {key}",
		"User-Agent": "curl/8.0",
		"Content-Type": "application/json",
	})
	try:
		with urllib.request.urlopen(req, timeout=30) as resp:
			raw = resp.read()
			return json.loads(raw) if raw else {}
	except urllib.error.HTTPError as e:
		detail = e.read().decode("utf-8", errors="replace")
		raise RuntimeError(f"{method} {path} -> HTTP {e.code}: {detail}") from None


def whoami():
	return _request("GET", "/v1/whoami")


# --- Step 1: create endpoint + deployment -----------------------------------------

def create_endpoint_and_deployment():
	result = load_json(RESULT_FILE, None)
	if result is None or not result.get("job_id"):
		raise RuntimeError(f"No job_id found in {RESULT_FILE}. Run finetune_launch_together_experiment2.py first.")

	client = Together()
	job = client.fine_tuning.retrieve(id=result["job_id"])
	model_object_id = job.model_dump().get("model_object_id")
	if not model_object_id:
		raise RuntimeError("No model_object_id on the Experiment 2 fine-tuning job -- cannot deploy.")

	who = whoami()
	project_id = who["project_id"]
	print(f"Project: {who['project_slug']} ({project_id})")

	model_resource = f"projects/{project_id}/models/{model_object_id}"
	ref = urllib.parse.urlencode({"referenceModel": model_resource})
	configs = _request("GET", f"/v2/projects/{project_id}/configs?{ref}")["data"]
	if not configs:
		raise RuntimeError(f"No deployable configs found for {model_resource}.")
	config = configs[0]
	config_resource = f"projects/{config['projectId']}/configs/{config['id']}"
	selectors = {s["key"]: s["value"] for s in config["selectors"]}
	print(f"Using config {config['id']}: {selectors}")

	# A previous run's endpoint may still exist under this name: full deletion via
	# the API is unreliable for a single-deployment endpoint (known limitation --
	# see stop_deployment_and_verify), so a stopped-but-not-deleted endpoint from an
	# earlier attempt is expected, not an error. Reuse it (restarting its deployment)
	# instead of trying to create a duplicate, which the API rejects with 409.
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
		# Traffic split from the prior run should still route to this deployment,
		# but re-assert it in case it was ever changed.
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
			print(f"  Delete it manually at https://api.together.ai/endpoints")
		raise

	write_json_atomic(ENDPOINT_FILE, {
		"project_id": project_id,
		"endpoint_id": endpoint_id,
		"endpoint_name": endpoint["name"],
		"deployment_id": deployment_id,
	})
	return project_id, endpoint_id, deployment_id, endpoint["name"]


# --- Step 2: wait for READY --------------------------------------------------------

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


# --- Step 3: evaluate the 50 held-out test examples, saving after every example ---

def build_selected_index_schema(n_candidates):
	"""Strict JSON Schema constraining the response to exactly one integer field,
	selected_index, with the dynamic valid range for this record's candidate count.
	Together's docs don't publish which JSON Schema keywords its constrained-decoding
	compiler enforces numerically, so minimum/maximum here are a best-effort
	first line of defense, not a substitute for the local range check below."""
	return {
		"type": "json_schema",
		"json_schema": {
			"name": "selected_index_response",
			"strict": True,
			"schema": {
				"type": "object",
				"properties": {
					"selected_index": {
						"type": "integer",
						"minimum": 0,
						"maximum": n_candidates - 1,
					}
				},
				"required": ["selected_index"],
				"additionalProperties": False,
			},
		},
	}


def call_finetuned_model(client, model, record):
	"""Returns (index_or_None, error_message_or_None). Captures the real failure
	reason (timeout, malformed JSON, out-of-range index, ...) instead of discarding
	it, so a retry pass can diagnose failures rather than guess.

	Uses strict json_schema (not json_object) so the response is constrained to
	exactly {"selected_index": <int>} -- no room for a "reasoning" field, a
	candidate-list dump, or any other shape. Temperature is intentionally left
	unset here (server default), matching the original Experiment 2 evaluation, so
	this change isolates the effect of json_schema from the separate temperature=0
	test run previously."""
	n = len(record["candidates"])
	try:
		response = client.chat.completions.create(
			model=model,
			response_format=build_selected_index_schema(n),
			messages=[
				{"role": "system", "content": _SYSTEM_PROMPT},
				{"role": "user", "content": user_prompt_for(record)},
			],
			timeout=30,
		)
		raw_content = response.choices[0].message.content
		payload = json.loads(raw_content)
		index = payload.get("selected_index")
	except Exception as exc:
		return None, f"{type(exc).__name__}: {exc}"

	if not isinstance(index, int) or isinstance(index, bool) or not (0 <= index < n):
		return None, f"invalid selected_index in model output: {index!r} (raw content: {raw_content!r})"
	return index, None


def sentence_at(candidates, index):
	if index is None or not (0 <= index < len(candidates)):
		return None
	return candidates[index]


def classify(ft_match, v7_match):
	if ft_match and v7_match:
		return BOTH_CORRECT
	if ft_match and not v7_match:
		return FINETUNED_IMPROVED
	if v7_match and not ft_match:
		return FINETUNED_REGRESSED
	return BOTH_WRONG


def index0_stats(indices, human_indices):
	valid = [(i, h) for i, h in zip(indices, human_indices) if i is not None]
	n_idx0 = sum(1 for i, _ in valid if i == 0)
	n_idx0_correct = sum(1 for i, h in valid if i == 0 and i == h)
	return {
		"n_valid_predictions": len(valid),
		"index0_selection_rate": n_idx0 / len(valid) if valid else None,
		"index0_count": n_idx0,
		"accuracy_when_index0_selected": n_idx0_correct / n_idx0 if n_idx0 else None,
	}


def run_evaluation(model_name):
	test_records = load_jsonl(TEST_FILE)
	if not test_records:
		raise RuntimeError(f"No records found in {TEST_FILE}.")

	client = Together()
	print(f"Evaluating Experiment 2 model {model_name} on {len(test_records)} held-out records ...")

	comparison = []
	category_counts = {BOTH_CORRECT: 0, FINETUNED_IMPROVED: 0, FINETUNED_REGRESSED: 0, BOTH_WRONG: 0}
	ft_correct = 0
	v7_correct = 0
	ft_indices, v7_indices, human_indices = [], [], []

	for i, record in enumerate(test_records, start=1):
		candidates = record["candidates"]
		human_index = record["selected_index"]
		v7_index = record.get("current_v7_index")
		ft_index, ft_error = call_finetuned_model(client, model_name, record)

		ft_match = ft_index == human_index
		v7_match = v7_index == human_index
		if ft_match:
			ft_correct += 1
		if v7_match:
			v7_correct += 1

		category = classify(ft_match, v7_match)
		category_counts[category] += 1
		ft_indices.append(ft_index)
		v7_indices.append(v7_index)
		human_indices.append(human_index)

		comparison.append({
			"source_id": record["source_id"],
			"term": record["term"],
			"candidates": candidates,
			"human_selected_index": human_index,
			"finetuned_selected_index": ft_index,
			"finetuned_error": ft_error,
			"v7_selected_index": v7_index,
			"human_selected_sentence": sentence_at(candidates, human_index),
			"finetuned_selected_sentence": sentence_at(candidates, ft_index),
			"v7_selected_sentence": sentence_at(candidates, v7_index),
			"finetuned_agrees_with_human": ft_match,
			"v7_agrees_with_human": v7_match,
			"category": category,
		})

		# Incremental save: rewrite the (growing) file after every single example, so a
		# crash, timeout, or interrupt anywhere in this loop preserves everything
		# completed so far instead of losing the whole run.
		write_jsonl_atomic(COMPARISON_FILE, comparison)
		status = "ok" if ft_error is None else f"FAILED: {ft_error}"
		print(f"  [{i}/{len(test_records)}] saved ({record['term']!r}) -- {status}")

	n_total = len(test_records)
	ft_accuracy = ft_correct / n_total
	v7_accuracy = v7_correct / n_total
	delta_pp = (ft_accuracy - v7_accuracy) * 100

	summary = {
		"model": model_name,
		"n_test_examples": n_total,
		"finetuned_correct": ft_correct,
		"finetuned_accuracy": ft_accuracy,
		"v7_correct": v7_correct,
		"v7_accuracy": v7_accuracy,
		"accuracy_delta_percentage_points": delta_pp,
		"category_counts": category_counts,
		"finetuned_index0_stats": index0_stats(ft_indices, human_indices),
		"v7_index0_stats": index0_stats(v7_indices, human_indices),
	}
	write_json_atomic(SUMMARY_FILE, summary)

	print()
	print("=" * 60)
	print(f"Experiment 2 accuracy vs human: {ft_correct}/{n_total} = {ft_accuracy:.1%}")
	print(f"V7 accuracy vs human:           {v7_correct}/{n_total} = {v7_accuracy:.1%}")
	print(f"Accuracy delta:                 {delta_pp:+.1f} percentage points")
	print(f"Category counts vs V7: {category_counts}")
	print(f"Index-0 stats: {summary['finetuned_index0_stats']}")
	print(f"Per-example comparison saved to {COMPARISON_FILE}")
	print(f"Summary saved to {SUMMARY_FILE}")


# --- Step 4: stop the deployment (always -- called from finally) + verify ---------

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
		return

	deadline = time.time() + STOP_TIMEOUT_SECONDS
	final_state = None
	while time.time() < deadline:
		d = _request("GET", f"/v2/projects/{project_id}/endpoints/{endpoint_id}/deployments/{deployment_id}")
		final_state = d
		state = d["status"]["state"]
		print(f"  state: {state}  ready={d['status'].get('readyReplicas', 0)}")
		if state == "DEPLOYMENT_STATE_STOPPED":
			break
		time.sleep(POLL_SECONDS)

	# Explicit verification: re-read fresh and check both the state string and the
	# actual replica count, rather than trusting the poll loop's last observation.
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


# --- Entry point --------------------------------------------------------------------

def main():
	if not os.environ.get("TOGETHER_API_KEY"):
		print("TOGETHER_API_KEY is not set in the environment. Stopping.")
		sys.exit(1)
	if not os.path.exists(RESULT_FILE):
		print(f"{RESULT_FILE} not found. Run finetune_launch_together_experiment2.py first.")
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
