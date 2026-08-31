"""
Manual Dedicated Model Inference (v2) endpoint lifecycle for evaluating the
clearmed short-explanation fine-tune.

Together's v1 dedicated-endpoints API (client.endpoints.create) no longer
accepts new endpoints (endpoints_v1_create_access_disabled), and the v2
management surface (client.beta.endpoints / client.beta.models) isn't present
yet in the installed together==2.9.0 SDK or CLI. This script talks to the v2
REST API directly (https://api.together.ai/v2/...) with the stdlib so no
extra dependency is required.

Usage:
    python together_dmi_endpoint.py create-and-wait
    python together_dmi_endpoint.py stop
"""

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(_THIS_DIR))))

from dotenv import load_dotenv  # noqa: E402
from together import Together  # noqa: E402

load_dotenv()

_EXP1_DIR = os.path.join(_REPO_ROOT, "finetuning", "experiments", "experiment1")
RESULT_FILE = os.path.join(_EXP1_DIR, "results", "finetune_result_together.json")
ENDPOINT_FILE = os.path.join(_EXP1_DIR, "deployment", "dedicated_endpoint.json")

API_BASE = "https://api.together.ai"
POLL_SECONDS = 15
READY_TIMEOUT_SECONDS = 25 * 60


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


def create_and_wait():
	result = json.load(open(RESULT_FILE, encoding="utf-8"))
	job_id = result["job_id"]

	client = Together()
	job = client.fine_tuning.retrieve(id=job_id)
	model_object_id = job.model_dump().get("model_object_id")
	if not model_object_id:
		print("No model_object_id on the fine-tuning job -- cannot deploy.")
		sys.exit(1)

	who = whoami()
	project_id = who["project_id"]
	project_slug = who["project_slug"]
	print(f"Project: {project_slug} ({project_id})")

	model_resource = f"projects/{project_id}/models/{model_object_id}"

	ref = urllib.parse.urlencode({"referenceModel": model_resource})
	configs = _request("GET", f"/v2/projects/{project_id}/configs?{ref}")["data"]
	if not configs:
		print(f"No deployable configs found for {model_resource}.")
		sys.exit(1)
	config = configs[0]
	config_resource = f"projects/{config['projectId']}/configs/{config['id']}"
	selectors = {s["key"]: s["value"] for s in config["selectors"]}
	print(f"Using config {config['id']}: {selectors}")

	endpoint_name = "clearmed-short-explanation-eval"
	print(f"Creating endpoint {endpoint_name} ...")
	endpoint = _request("POST", f"/v2/projects/{project_id}/endpoints", {"name": endpoint_name})
	endpoint_id = endpoint["id"]
	print(f"  endpoint id: {endpoint_id}, name: {endpoint['name']}")

	print("Creating deployment ...")
	deployment = _request(
		"POST",
		f"/v2/projects/{project_id}/endpoints/{endpoint_id}/deployments",
		{
			"name": "eval",
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

	print("Waiting for the deployment to become READY (first boot can take ~20 minutes) ...")
	deadline = time.time() + READY_TIMEOUT_SECONDS
	while True:
		d = _request("GET", f"/v2/projects/{project_id}/endpoints/{endpoint_id}/deployments/{deployment_id}")
		state = d["status"]["state"]
		print(f"  state: {state}  ready={d['status'].get('readyReplicas', 0)}  msg={d['status'].get('message', '')}")
		if state == "DEPLOYMENT_STATE_READY":
			break
		if state in ("DEPLOYMENT_STATE_FAILED", "DEPLOYMENT_STATE_STOPPED", "DEPLOYMENT_STATE_STOPPING"):
			print(f"Deployment ended in state {state} before becoming ready.")
			sys.exit(1)
		if time.time() > deadline:
			print("Timed out waiting for READY.")
			sys.exit(1)
		time.sleep(POLL_SECONDS)

	with open(ENDPOINT_FILE, "w", encoding="utf-8") as f:
		json.dump({
			"project_id": project_id,
			"endpoint_id": endpoint_id,
			"endpoint_name": endpoint["name"],
			"deployment_id": deployment_id,
		}, f, indent=2)

	print(f"Endpoint ready: {endpoint['name']}")
	print(f"Saved endpoint info to {ENDPOINT_FILE}")
	print()
	print("Next: run the evaluation, then come back and run:")
	print(f"  python {os.path.basename(__file__)} stop")


def stop():
	if not os.path.exists(ENDPOINT_FILE):
		print(f"No {ENDPOINT_FILE} found -- nothing to stop.")
		sys.exit(1)
	info = json.load(open(ENDPOINT_FILE, encoding="utf-8"))
	project_id = info["project_id"]
	endpoint_id = info["endpoint_id"]
	deployment_id = info["deployment_id"]

	print("Scaling deployment to 0/0 (this is what stops billing) ...")
	_request(
		"PATCH",
		f"/v2/projects/{project_id}/endpoints/{endpoint_id}/deployments/{deployment_id}",
		{"autoscaling": {"minReplicas": 0, "maxReplicas": 0}},
	)

	while True:
		d = _request("GET", f"/v2/projects/{project_id}/endpoints/{endpoint_id}/deployments/{deployment_id}")
		state = d["status"]["state"]
		print(f"  state: {state}")
		if state == "DEPLOYMENT_STATE_STOPPED":
			break
		time.sleep(POLL_SECONDS)

	print("Deployment stopped -- billing has stopped.")

	try:
		_request("PATCH", f"/v2/projects/{project_id}/endpoints/{endpoint_id}", {"trafficSplit": []})
		_request("DELETE", f"/v2/projects/{project_id}/endpoints/{endpoint_id}/deployments/{deployment_id}")
		_request("DELETE", f"/v2/projects/{project_id}/endpoints/{endpoint_id}")
		os.remove(ENDPOINT_FILE)
		print("Deployment and endpoint fully deleted.")
	except RuntimeError as exc:
		print("Stopped, but full deletion via the API failed (this is a known API limitation")
		print("for a single-deployment endpoint's empty traffic split):")
		print(f"  {exc}")
		print("Billing is already stopped -- this is safe to leave as-is, or delete manually at:")
		print("  https://api.together.ai/endpoints")


def main():
	if len(sys.argv) != 2 or sys.argv[1] not in ("create-and-wait", "stop"):
		print("Usage: python together_dmi_endpoint.py [create-and-wait|stop]")
		sys.exit(1)
	if sys.argv[1] == "create-and-wait":
		create_and_wait()
	else:
		stop()


if __name__ == "__main__":
	main()
