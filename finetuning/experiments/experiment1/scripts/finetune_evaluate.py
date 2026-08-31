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
from openai import OpenAI  # noqa: E402

from create_clearmed_db import _SYSTEM_PROMPT  # noqa: E402

from dataset_io import load_jsonl, load_json, write_jsonl_atomic  # noqa: E402
from finetune_prepare import user_prompt_for  # noqa: E402

load_dotenv()

TEST_FILE = os.path.join(_REPO_ROOT, "finetuning", "data", "splits", "test.jsonl")
_EXP1_DIR = os.path.join(_REPO_ROOT, "finetuning", "experiments", "experiment1")
RESULT_FILE = os.path.join(_EXP1_DIR, "results", "finetune_result.json")
BASELINE_FILE = os.path.join(_EXP1_DIR, "results", "baseline_result.json")
COMPARISON_FILE = os.path.join(_EXP1_DIR, "results", "eval_comparison.jsonl")


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
	except Exception as exc:
		print(f"  call failed for term {record['term']!r}: {exc}")
		return None

	if not isinstance(index, int) or isinstance(index, bool) or not (0 <= index < len(record["candidates"])):
		print(f"  invalid index from fine-tuned model for term {record['term']!r}: {index!r}")
		return None
	return index


def main():
	if not os.environ.get("OPENAI_API_KEY"):
		print("OPENAI_API_KEY is not set in the environment. Stopping.")
		sys.exit(1)

	result = load_json(RESULT_FILE, None)
	if result is None or not result.get("fine_tuned_model"):
		print(f"No fine_tuned_model found in {RESULT_FILE}. Run finetune_launch.py first.")
		sys.exit(1)
	model = result["fine_tuned_model"]

	baseline = load_json(BASELINE_FILE, None)
	if baseline is None:
		print(f"No baseline found in {BASELINE_FILE}. Run finetune_prepare.py first.")
		sys.exit(1)

	test_records = load_jsonl(TEST_FILE)
	if not test_records:
		print(f"No records found in {TEST_FILE}.")
		sys.exit(1)

	client = OpenAI()

	print(f"Evaluating fine-tuned model {model} on {len(test_records)} held-out records ...")
	comparison = []
	ft_correct = 0
	for i, record in enumerate(test_records, start=1):
		ft_index = call_finetuned_model(client, model, record)
		human = record["selected_index"]
		v7 = record.get("current_v7_index")
		ft_match = ft_index == human
		if ft_match:
			ft_correct += 1
		comparison.append({
			"source_id": record["source_id"],
			"term": record["term"],
			"human_selected_index": human,
			"current_v7_index": v7,
			"v7_matches_human": v7 == human,
			"finetuned_index": ft_index,
			"finetuned_matches_human": ft_match,
		})
		print(f"  [{i}/{len(test_records)}] {record['term']!r}: human={human} v7={v7} finetuned={ft_index}")

	write_jsonl_atomic(COMPARISON_FILE, comparison)

	ft_total = len(test_records)
	ft_accuracy = ft_correct / ft_total
	baseline_correct = baseline["correct"]
	baseline_total = baseline["total"]
	baseline_accuracy = baseline["accuracy"]
	delta = ft_accuracy - baseline_accuracy
	delta_examples = ft_correct - baseline_correct

	print()
	print("=" * 60)
	print(f"V7 baseline (held-out {baseline_total}):        {baseline_correct}/{baseline_total} = {baseline_accuracy:.1%}")
	print(f"Fine-tuned model (held-out {ft_total}):    {ft_correct}/{ft_total} = {ft_accuracy:.1%}")
	print(f"Delta:                                {delta_examples:+d} examples ({delta:+.1%})")
	if abs(delta_examples) < 4:
		print(
			f"NOTE: with only {ft_total} test examples, each example is ~{100 / ft_total:.1f} "
			f"percentage points. A {delta_examples:+d}-example difference is within noise "
			f"(roughly need a 3-4 example swing to be confident)."
		)
	print(f"Comparison saved to {COMPARISON_FILE}")


if __name__ == "__main__":
	main()
