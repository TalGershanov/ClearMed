"""
Experiment 3: run the exact canonical V7 selector (production's
_select_short_explanation_index_ai, gpt-4o-mini) on the 50 newly annotated
Experiment 3 terms, as a baseline/reference -- NOT as ground truth and NOT as
training data.

*** THIS SCRIPT MAKES PAID OPENAI API CALLS (one per example) WHEN RUN. ***
It is committed here unexecuted. See the readiness-check section of this
docstring / the accompanying dry-run output for what was validated WITHOUT
calling the API.

What it sends to V7, per example: ONLY `term` and `candidates` (the exact same
two inputs production passes to _select_short_explanation_index_ai). It never
reads or sends best_index or acceptable_indices -- those are read afterward,
locally, only to LABEL V7's independent answer as correct/accepted/wrong. V7's
answer never modifies annotations_batch3.jsonl; that file is opened read-only.

This script is intentionally self-contained: it does NOT read from or write to
finetuning/data/v7_cache.json (the shared cache used by the original 181-example
annotation tool). That cache holds no entries for these 50 terms anyway (verified
separately), and keeping this baseline run isolated avoids any side effect on the
shared annotation pipeline's state.

Output (both under finetuning/experiments/experiment3/results/, nothing written
to data/ or to the training dataset):
  - v7_baseline_batch3.jsonl         one row per example: source_id, term,
                                      v7_selected_index, human_best_index,
                                      human_acceptable_indices, difficulty,
                                      failure_mode_bucket, domain, status
                                      (correct / accepted / wrong / no_prediction)
  - v7_baseline_batch3_summary.json  strict accuracy, acceptable-inclusive
                                      accuracy, correct/accepted/wrong/failed
                                      counts, easy-vs-hard breakdown, per-bucket
                                      breakdown

Saves incrementally (one line per completed example) and resumes: re-running
skips any source_id already present in v7_baseline_batch3.jsonl, so an
interrupted run never re-spends on already-answered examples.

Usage:
    python experiment3_v7_baseline_evaluate.py
"""

import os
import sys
from collections import Counter

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(_THIS_DIR))))
_SERVER_INIT_DIR = os.path.join(_REPO_ROOT, "server_init")
_SHARED_DIR = os.path.join(_REPO_ROOT, "finetuning", "shared")
for _path in (_REPO_ROOT, _SERVER_INIT_DIR, _SHARED_DIR):
	if _path not in sys.path:
		sys.path.insert(0, _path)

from dotenv import load_dotenv  # noqa: E402
from ai_services import _select_short_explanation_index_ai  # noqa: E402

from dataset_io import load_jsonl, write_jsonl_atomic, write_json_atomic  # noqa: E402

load_dotenv()

EXP3_DIR = os.path.join(_REPO_ROOT, "finetuning", "experiments", "experiment3")
BATCH3_FILE = os.path.join(EXP3_DIR, "data", "annotations_batch3.jsonl")

RESULTS_FILE = os.path.join(EXP3_DIR, "results", "v7_baseline_batch3.jsonl")
SUMMARY_FILE = os.path.join(EXP3_DIR, "results", "v7_baseline_batch3_summary.json")


def classify(v7_index, best_index, acceptable_indices):
	if v7_index is None:
		return "no_prediction"
	if v7_index == best_index:
		return "correct"
	if v7_index in (acceptable_indices or []):
		return "accepted"
	return "wrong"


def run_baseline(records, results):
	done_ids = {str(r["source_id"]) for r in results}
	remaining = [r for r in records if str(r["source_id"]) not in done_ids]
	print(f"{len(results)} already evaluated. {len(remaining)} remaining.")

	for i, r in enumerate(remaining, start=1):
		term = r["term"]
		candidates = r["candidates"]  # exact same list production would pass -- no human labels included

		v7_index = _select_short_explanation_index_ai(candidates, term=term)

		row = {
			"source_id": r["source_id"],
			"term": term,
			"v7_selected_index": v7_index,
			"human_best_index": r["best_index"],
			"human_acceptable_indices": r.get("acceptable_indices", []),
			"difficulty": r.get("difficulty"),
			"failure_mode_bucket": r.get("bucket"),
			"domain": r.get("domain"),
			"status": classify(v7_index, r["best_index"], r.get("acceptable_indices", [])),
		}
		results.append(row)
		write_jsonl_atomic(RESULTS_FILE, results)
		print(f"  [{i}/{len(remaining)}] {term!r}: v7={v7_index} human_best={r['best_index']} -> {row['status']}")

	return results


def breakdown_by(results, key):
	out = {}
	for value in sorted({r[key] for r in results if r[key] is not None}):
		subset = [r for r in results if r[key] == value]
		valid = [r for r in subset if r["status"] != "no_prediction"]
		correct = sum(1 for r in valid if r["status"] == "correct")
		accepted = sum(1 for r in valid if r["status"] in ("correct", "accepted"))
		out[value] = {
			"n": len(subset),
			"n_valid": len(valid),
			"strict_accuracy": correct / len(valid) if valid else None,
			"acceptable_inclusive_accuracy": accepted / len(valid) if valid else None,
		}
	return out


def build_summary(results):
	n_total = len(results)
	valid = [r for r in results if r["status"] != "no_prediction"]
	n_valid = len(valid)
	status_counts = Counter(r["status"] for r in results)

	correct = status_counts.get("correct", 0)
	accepted = status_counts.get("accepted", 0)
	wrong = status_counts.get("wrong", 0)
	failed = status_counts.get("no_prediction", 0)

	summary = {
		"n_total_examples": n_total,
		"n_valid_predictions": n_valid,
		"n_failed_predictions": failed,
		"status_counts": {"correct": correct, "accepted": accepted, "wrong": wrong, "no_prediction": failed},
		"strict_accuracy": correct / n_valid if n_valid else None,
		"acceptable_inclusive_accuracy": (correct + accepted) / n_valid if n_valid else None,
		"by_difficulty": breakdown_by(results, "difficulty"),
		"by_failure_mode_bucket": breakdown_by(results, "failure_mode_bucket"),
	}
	return summary


def main():
	if not os.environ.get("OPENAI_API_KEY"):
		print("OPENAI_API_KEY is not set in the environment. Stopping -- this script makes paid OpenAI calls.")
		sys.exit(1)

	records = load_jsonl(BATCH3_FILE)
	if len(records) != 50:
		print(f"Expected 50 records in {BATCH3_FILE}, found {len(records)}. Stopping.")
		sys.exit(1)

	results = load_jsonl(RESULTS_FILE)
	results = run_baseline(records, results)

	summary = build_summary(results)
	write_json_atomic(SUMMARY_FILE, summary)

	print()
	print("=" * 60)
	print(f"n_valid: {summary['n_valid_predictions']} / {summary['n_total_examples']}  (failed: {summary['n_failed_predictions']})")
	print(f"Strict accuracy: {summary['strict_accuracy']:.1%}" if summary["strict_accuracy"] is not None else "Strict accuracy: n/a")
	print(f"Acceptable-inclusive accuracy: {summary['acceptable_inclusive_accuracy']:.1%}" if summary["acceptable_inclusive_accuracy"] is not None else "n/a")
	print(f"Status counts: {summary['status_counts']}")
	print(f"By difficulty: {summary['by_difficulty']}")
	print(f"By failure-mode bucket: {summary['by_failure_mode_bucket']}")
	print()
	print(f"Per-example results: {RESULTS_FILE}")
	print(f"Summary: {SUMMARY_FILE}")


if __name__ == "__main__":
	main()
