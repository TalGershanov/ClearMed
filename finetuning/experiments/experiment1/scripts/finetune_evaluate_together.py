import json
import os
import sys

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

TEST_FILE = os.path.join(_REPO_ROOT, "finetuning", "data", "splits", "test.jsonl")
_EXP1_DIR = os.path.join(_REPO_ROOT, "finetuning", "experiments", "experiment1")
RESULT_FILE = os.path.join(_EXP1_DIR, "results", "finetune_result_together.json")
ENDPOINT_FILE = os.path.join(_EXP1_DIR, "deployment", "dedicated_endpoint.json")
COMPARISON_FILE = os.path.join(_EXP1_DIR, "results", "eval_comparison_together.jsonl")
SUMMARY_FILE = os.path.join(_EXP1_DIR, "results", "eval_summary_together.json")

BOTH_CORRECT = "both_correct"
FINETUNED_IMPROVED = "finetuned_improved"
FINETUNED_REGRESSED = "finetuned_regressed"
BOTH_WRONG = "both_wrong"


def call_finetuned_model(client, model, record):
	try:
		response = client.chat.completions.create(
			model=model,
			response_format={"type": "json_object"},
			messages=[
				{"role": "system", "content": _SYSTEM_PROMPT},
				{"role": "user", "content": user_prompt_for(record)},
			],
			timeout=30,
		)
		payload = json.loads(response.choices[0].message.content)
		index = payload.get("selected_index")
	except Exception:
		return None

	if not isinstance(index, int) or isinstance(index, bool) or not (0 <= index < len(record["candidates"])):
		return None
	return index


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


def main():
	if not os.environ.get("TOGETHER_API_KEY"):
		print("TOGETHER_API_KEY is not set in the environment. Stopping.")
		sys.exit(1)

	result = load_json(RESULT_FILE, None)
	if result is None or not result.get("fine_tuned_model"):
		print(f"No fine_tuned_model found in {RESULT_FILE}. Run finetune_launch_together.py first.")
		sys.exit(1)

	# LoRA fine-tunes are not queryable by their raw model name -- Together requires a
	# dedicated endpoint. If one has been deployed (see together_dedicated_endpoint.py),
	# query it by its endpoint name; otherwise fall back to the raw name (e.g. for a
	# base/non-LoRA model that is directly servable).
	endpoint_info = load_json(ENDPOINT_FILE, None)
	model = endpoint_info["endpoint_name"] if endpoint_info else result["fine_tuned_model"]

	test_records = load_jsonl(TEST_FILE)
	if not test_records:
		print(f"No records found in {TEST_FILE}.")
		sys.exit(1)

	client = Together()

	print(f"Evaluating fine-tuned model {model} on {len(test_records)} held-out records ...")

	comparison = []
	category_counts = {BOTH_CORRECT: 0, FINETUNED_IMPROVED: 0, FINETUNED_REGRESSED: 0, BOTH_WRONG: 0}
	ft_correct = 0
	v7_correct = 0

	for record in test_records:
		candidates = record["candidates"]
		human_index = record["selected_index"]
		v7_index = record.get("current_v7_index")
		ft_index = call_finetuned_model(client, model, record)

		ft_match = ft_index == human_index
		v7_match = v7_index == human_index
		if ft_match:
			ft_correct += 1
		if v7_match:
			v7_correct += 1

		category = classify(ft_match, v7_match)
		category_counts[category] += 1

		comparison.append({
			"source_id": record["source_id"],
			"term": record["term"],
			"candidates": candidates,
			"human_selected_index": human_index,
			"finetuned_selected_index": ft_index,
			"v7_selected_index": v7_index,
			"human_selected_sentence": sentence_at(candidates, human_index),
			"finetuned_selected_sentence": sentence_at(candidates, ft_index),
			"v7_selected_sentence": sentence_at(candidates, v7_index),
			"finetuned_agrees_with_human": ft_match,
			"v7_agrees_with_human": v7_match,
			"category": category,
		})

	write_jsonl_atomic(COMPARISON_FILE, comparison)

	n_total = len(test_records)
	ft_accuracy = ft_correct / n_total
	v7_accuracy = v7_correct / n_total
	delta_pp = (ft_accuracy - v7_accuracy) * 100

	summary = {
		"model": model,
		"n_test_examples": n_total,
		"finetuned_correct": ft_correct,
		"finetuned_accuracy": ft_accuracy,
		"v7_correct": v7_correct,
		"v7_accuracy": v7_accuracy,
		"accuracy_delta_percentage_points": delta_pp,
		"category_counts": category_counts,
	}
	write_json_atomic(SUMMARY_FILE, summary)

	print()
	print("=" * 60)
	print(f"Fine-tuned model accuracy vs human: {ft_correct}/{n_total} = {ft_accuracy:.1%}")
	print(f"V7 accuracy vs human:               {v7_correct}/{n_total} = {v7_accuracy:.1%}")
	print(f"Accuracy delta:                     {delta_pp:+.1f} percentage points")
	print()
	print(f"Both correct:        {category_counts[BOTH_CORRECT]}")
	print(f"Fine-tuned improved: {category_counts[FINETUNED_IMPROVED]}")
	print(f"Fine-tuned regressed:{category_counts[FINETUNED_REGRESSED]}")
	print(f"Both wrong:          {category_counts[BOTH_WRONG]}")
	print()
	print(f"Per-example comparison saved to {COMPARISON_FILE}")
	print(f"Summary saved to {SUMMARY_FILE}")


if __name__ == "__main__":
	main()
