"""
Experiment 3: safety/integrity checks on the Experiment 3 launcher and its training
file, run before the launcher is considered ready. Purely local -- no network calls,
no Together/OpenAI API usage.

Checks performed:
  1. experiment3_train_final.jsonl has exactly 416 rows (208 natural + 208 shuffled).
  2. Every row is valid Together conversational-chat JSONL (messages array, roles,
     assistant content is exactly {"selected_index": <int>}).
  3. Natural rows carry weight 1.0, shuffled rows carry weight 0.5.
  4. Zero overlap between the Experiment 3 training pool (and the validation file it
     will be launched with) and the fixed held-out finetuning/data/splits/test.jsonl.
  5. The Experiment 3 launcher's BASE_MODEL constant matches Experiment 2's exactly.
  6. Every other hyperparameter the launchers share (lora flag/lora_r/n_epochs/
     learning_rate/n_evals/upload-check behavior) is byte-identical between the two
     launcher modules -- imported and compared directly, not re-typed.
  7. Every WRITE path the Experiment 3 launcher uses (TRAIN_FILE upload source,
     RESULT_FILE) lives only under finetuning/experiments/experiment3/ -- none of
     them collide with any known Experiment 1 or Experiment 2 file path, so this
     launcher cannot overwrite an Experiment 1/2 artifact.
  8. The one path the Experiment 3 launcher deliberately reuses from Experiment 2
     (VALIDATION_FILE = experiment2/data/dev.jsonl) is confirmed to be read-only
     from Experiment 3's perspective: it does not appear as a write target anywhere
     in this launcher's source.

Usage:
    python experiment3_verify_launcher_readiness.py
"""

import importlib.util
import inspect
import json
import os
import sys
from collections import Counter

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(_THIS_DIR))))
_SHARED_DIR = os.path.join(_REPO_ROOT, "finetuning", "shared")
if _SHARED_DIR not in sys.path:
	sys.path.insert(0, _SHARED_DIR)

from dataset_io import load_jsonl, write_json_atomic  # noqa: E402
from together.lib.utils.files import check_file  # noqa: E402
from pathlib import Path  # noqa: E402

FINETUNING_DIR = os.path.join(_REPO_ROOT, "finetuning")
TEST_FILE = os.path.join(FINETUNING_DIR, "data", "splits", "test.jsonl")

EXP1_DIR = os.path.join(FINETUNING_DIR, "experiments", "experiment1")
EXP2_DIR = os.path.join(FINETUNING_DIR, "experiments", "experiment2")
EXP3_DIR = os.path.join(FINETUNING_DIR, "experiments", "experiment3")

TRAIN_FINAL_FILE = os.path.join(EXP3_DIR, "data", "experiment3_train_final.jsonl")
TRAIN_MANIFEST_FILE = os.path.join(EXP3_DIR, "data", "experiment3_train_manifest.jsonl")
EXP2_DEV_FILE = os.path.join(EXP2_DIR, "data", "dev.jsonl")
EXP2_DEV_MANIFEST_FILE = os.path.join(EXP2_DIR, "data", "dev_manifest.jsonl")

EXP2_LAUNCHER_FILE = os.path.join(EXP2_DIR, "scripts", "finetune_launch_together_experiment2.py")
EXP3_LAUNCHER_FILE = os.path.join(EXP3_DIR, "scripts", "finetune_launch_together_experiment3.py")

REPORT_FILE = os.path.join(EXP3_DIR, "results", "experiment3_launcher_readiness_report.json")

EXPECTED_TOTAL_ROWS = 416
EXPECTED_NATURAL_ROWS = 208
EXPECTED_SHUFFLED_ROWS = 208

SHARED_HYPERPARAM_ATTRS = ["BASE_MODEL", "N_EPOCHS", "LEARNING_RATE", "LORA_R", "N_EVALS", "UPLOAD_CHECK"]


def _load_module(path, name):
	spec = importlib.util.spec_from_file_location(name, path)
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


def strip_weight_and_check(chat_file):
	lines = [json.loads(l) for l in open(chat_file, encoding="utf-8")]
	tmp_path = chat_file + ".no_weight_check.tmp.jsonl"
	with open(tmp_path, "w", encoding="utf-8") as f:
		for l in lines:
			f.write(json.dumps({"messages": l["messages"]}) + "\n")
	try:
		report = check_file(Path(tmp_path))
	finally:
		os.remove(tmp_path)
	weights = [l.get("weight") for l in lines]
	weights_valid = all(isinstance(w, (int, float)) and not isinstance(w, bool) and w >= 0 for w in weights)
	return {
		"conversational_format_check_excluding_weight": report.get("is_check_passed"),
		"conversational_format_message": report.get("message"),
		"all_weights_non_negative_numbers": weights_valid,
		"weight_values_present": sorted(set(weights)),
	}


def collect_known_exp12_paths():
	"""Every file path any Experiment 1 or Experiment 2 script is known to WRITE to,
	so we can assert Experiment 3's write targets never collide with them."""
	paths = set()
	for root_dir in (EXP1_DIR, EXP2_DIR):
		for dirpath, _dirnames, filenames in os.walk(root_dir):
			for fn in filenames:
				paths.add(os.path.abspath(os.path.join(dirpath, fn)))
	return paths


def main():
	problems = []

	# --- 1. Row counts -----------------------------------------------------
	manifest = load_jsonl(TRAIN_MANIFEST_FILE)
	chat = load_jsonl(TRAIN_FINAL_FILE)
	natural = [r for r in manifest if not r["is_shuffled"]]
	shuffled = [r for r in manifest if r["is_shuffled"]]
	check1 = {
		"n_train_rows": len(chat), "n_manifest_rows": len(manifest),
		"n_natural": len(natural), "n_shuffled": len(shuffled),
	}
	if (len(chat) != EXPECTED_TOTAL_ROWS or len(manifest) != EXPECTED_TOTAL_ROWS
			or len(natural) != EXPECTED_NATURAL_ROWS or len(shuffled) != EXPECTED_SHUFFLED_ROWS):
		problems.append(("1_expected_row_counts", check1))

	# --- 2 & format. JSONL/chat structural validity -------------------------
	local_check = strip_weight_and_check(TRAIN_FINAL_FILE)
	if not local_check["conversational_format_check_excluding_weight"] or not local_check["all_weights_non_negative_numbers"]:
		problems.append(("2_train_local_format_check", local_check))

	# --- 3. Weight correctness ----------------------------------------------
	bad_natural_weight = [r["source_id"] for r in natural if r["weight"] != 1.0]
	bad_shuffled_weight = [r["source_id"] for r in shuffled if r["weight"] != 0.5]
	if bad_natural_weight:
		problems.append(("3a_natural_weight_1.0", bad_natural_weight))
	if bad_shuffled_weight:
		problems.append(("3b_shuffled_weight_0.5", bad_shuffled_weight))

	# --- 4. Zero overlap with the held-out test set (train file AND the
	#        validation file the launcher will actually upload) ------------
	test_ids = {str(r["source_id"]) for r in load_jsonl(TEST_FILE)}
	train_ids = {str(r["source_id"]) for r in manifest}
	dev_manifest = load_jsonl(EXP2_DEV_MANIFEST_FILE)
	dev_ids = {str(r["source_id"]) for r in dev_manifest}
	train_test_leak = sorted(train_ids & test_ids)
	dev_test_leak = sorted(dev_ids & test_ids)
	train_dev_overlap = sorted(train_ids & dev_ids)
	if train_test_leak or dev_test_leak:
		problems.append(("4_no_test_leakage", {"train": train_test_leak, "dev": dev_test_leak}))
	if train_dev_overlap:
		problems.append(("4b_no_train_dev_overlap", train_dev_overlap))

	# --- 5 & 6. Hyperparameter equality against Experiment 2's launcher ----
	exp2_mod = _load_module(EXP2_LAUNCHER_FILE, "exp2_launcher_readonly")
	exp3_mod = _load_module(EXP3_LAUNCHER_FILE, "exp3_launcher_readonly")

	hyperparam_comparison = {}
	mismatches = []
	for attr in SHARED_HYPERPARAM_ATTRS:
		exp2_val = getattr(exp2_mod, attr)
		exp3_val = getattr(exp3_mod, attr)
		hyperparam_comparison[attr] = {"experiment2": exp2_val, "experiment3": exp3_val, "match": exp2_val == exp3_val}
		if exp2_val != exp3_val:
			mismatches.append(attr)
	if mismatches:
		problems.append(("5_6_hyperparameters_preserved", mismatches))

	# --- 7. Every WRITE path Experiment 3's launcher touches lives only
	#        under experiment3/, and never collides with a known Exp1/Exp2 file. --
	exp3_write_paths = {os.path.abspath(exp3_mod.RESULT_FILE)}
	exp3_train_upload_path = os.path.abspath(exp3_mod.TRAIN_FILE)
	known_exp12_paths = collect_known_exp12_paths()

	outside_exp3 = [p for p in exp3_write_paths if not p.startswith(os.path.abspath(EXP3_DIR) + os.sep)]
	collisions = sorted((exp3_write_paths | {exp3_train_upload_path}) & known_exp12_paths)
	if outside_exp3:
		problems.append(("7a_exp3_write_paths_scoped", outside_exp3))
	if collisions:
		problems.append(("7b_no_exp1_exp2_path_collision", collisions))

	# --- 8. VALIDATION_FILE (deliberately == Experiment 2's dev.jsonl) is
	#        never referenced as a write target in the launcher's source. ---
	launcher_source = inspect.getsource(exp3_mod)
	validation_is_exp2_dev = os.path.abspath(exp3_mod.VALIDATION_FILE) == os.path.abspath(EXP2_DEV_FILE)
	# The only write call in the launcher; VALIDATION_FILE must never appear as its argument.
	write_call_snippets = [line.strip() for line in launcher_source.splitlines() if "write_json_atomic(" in line]
	validation_file_written = any("VALIDATION_FILE" in line for line in write_call_snippets)
	if not validation_is_exp2_dev:
		problems.append(("8a_validation_file_is_exp2_dev_as_documented", exp3_mod.VALIDATION_FILE))
	if validation_file_written:
		problems.append(("8b_validation_file_never_written", write_call_snippets))

	report = {
		"row_counts": check1,
		"local_format_check": local_check,
		"weight_checks": {"natural_weight_ok": not bad_natural_weight, "shuffled_weight_ok": not bad_shuffled_weight},
		"test_leakage": {"train": train_test_leak, "dev": dev_test_leak},
		"train_dev_overlap": train_dev_overlap,
		"hyperparameter_comparison_vs_experiment2": hyperparam_comparison,
		"experiment3_write_paths": sorted(exp3_write_paths),
		"experiment3_train_upload_path": exp3_train_upload_path,
		"write_path_collisions_with_exp1_exp2": collisions,
		"validation_file_reused_from_experiment2": {
			"path": exp3_mod.VALIDATION_FILE,
			"confirmed_read_only_in_launcher": not validation_file_written,
		},
		"all_checks_passed": len(problems) == 0,
		"failed_checks": problems,
	}
	write_json_atomic(REPORT_FILE, report)

	print("=" * 60)
	print("Experiment 3 launcher readiness checks")
	print("=" * 60)
	descriptions = [
		"1. experiment3_train_final.jsonl row counts (416 = 208 natural + 208 shuffled)",
		"2. local chat-format structural validity (excl. weight) + weight value validity",
		"3a. natural rows weight == 1.0",
		"3b. shuffled rows weight == 0.5",
		"4. no held-out test source_id in train or validation file",
		"4b. no overlap between Experiment 3 train ids and the reused Experiment 2 dev ids",
		"5/6. shared hyperparameters identical to Experiment 2's launcher",
		"7a. Experiment 3 write paths scoped to experiment3/",
		"7b. no write-path collision with any Experiment 1/2 file",
		"8a. VALIDATION_FILE is Experiment 2's dev.jsonl, as documented",
		"8b. VALIDATION_FILE never appears as a write target",
	]
	codes = ["1_", "2_", "3a_", "3b_", "4_", "4b_", "5_6_", "7a_", "7b_", "8a_", "8b_"]
	for code, desc in zip(codes, descriptions):
		failed = any(p[0].startswith(code) for p in problems)
		print(f"  [{'FAIL' if failed else 'pass'}] {desc}")

	print()
	print("Hyperparameter comparison vs. Experiment 2:")
	for attr, vals in hyperparam_comparison.items():
		print(f"  {attr}: exp2={vals['experiment2']!r}  exp3={vals['experiment3']!r}  match={vals['match']}")

	print()
	print(f"Full report: {REPORT_FILE}")
	if problems:
		print()
		print("!!! ONE OR MORE CHECKS FAILED -- do not consider the launcher ready. !!!")
		sys.exit(1)
	else:
		print()
		print("All readiness checks passed. Launcher is ready (not launched).")


if __name__ == "__main__":
	main()
