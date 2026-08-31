# ClearMed Fine-Tuning: Short-Explanation Sentence Selection

This directory contains the full history of fine-tuning ClearMed's "short explanation"
selector — the component that, given a medical term and a numbered list of candidate
sentences pulled from its MedlinePlus source text, picks the one sentence that best
stands alone as a definition of the term for a patient. It is a **classification task**:
the model outputs `{"selected_index": N}`, choosing among existing sentences rather than
writing new text.

## Goal

Production ("V7") uses `gpt-4o-mini` with a heuristic fallback. The goal of this work is
to see whether a small, cheaply-hosted open model, fine-tuned on human-labeled examples
of this exact decision, can match or beat V7's accuracy — and, along the way, to run the
project as a rigorous, reproducible ML experimentation exercise: labeled ground truth,
a fixed held-out test set, honest partial-run reporting, root-cause debugging of failure
modes, and clear separation between "what changed" across experiments.

## Shared dataset: 181 human-labeled examples

`data/annotations.jsonl` — 181 examples, each with the term, its full candidate-sentence
list (produced by the exact same `_clean_candidate_sentences` function production uses),
V7's pick, and a **human** ground-truth pick (`selected_index`). Labeled with
`scripts/data/annotate.py`.

### The fixed 131 / 50 split

`data/splits/train.jsonl` (131) and `data/splits/test.jsonl` (50) are a deterministic,
seeded (seed=42) split of the 181, produced once by `scripts/data/split_dataset.py` and
never touched again. **`test.jsonl` is the one artifact every experiment in this
directory treats as sacred** — no experiment's training data, augmentation, or
hyperparameter search is ever allowed to read it. It is the only source of the "human"
and "V7" columns used in every evaluation across both experiments.

## Experiment 1 — baseline LoRA fine-tune

`experiments/experiment1/` — SFT LoRA fine-tune of `Qwen/Qwen3.5-9B` on the 131 training
examples, as-is (no augmentation).

- An initial attempt used OpenAI (`finetune_launch.py`, `finetune_evaluate.py`) but was
  abandoned — the job was blocked (403) before training started. See
  `together_dataset_audit.md` for the audit that preceded the pivot to Together.
- The real run: `finetune_launch_together.py` → `results/finetune_result_together.json`.
  Deployed via `together_dmi_endpoint.py`, evaluated via `finetune_evaluate_together.py`.
- **Result was a partial run**: the Together account balance went negative mid-evaluation
  and the platform auto-stopped the endpoint, so only 24/50 test examples completed.
  `results/eval_summary_together.json` reports this honestly (`INCOMPLETE_RUN`-style
  framing) rather than treating the 26 missing predictions as wrong answers.
- Error analysis on those 24 found a strong **index-0 bias**: the model defaulted to
  picking the first candidate sentence far more often than the human labels justified —
  traced to the training set itself being skewed toward that pattern, compounded by a
  candidate-list-length mismatch against the real corpus (the labeled set skewed toward
  very long candidate lists).

## Experiment 2 — what changed

`experiments/experiment2/` targets the two root causes found in Experiment 1:

1. **Position-bias correction**: every one of the 131 original + 45 newly-labeled
   examples gets one shuffled twin (same sentences, permuted order, `selected_index`
   recomputed to the same sentence, `weight: 0.5` vs. the natural row's `weight: 1.0`) —
   so the model can't learn "the answer is usually near the start."
2. **Distribution correction**: 45 new human-labeled examples (`annotate_experiment2.py`,
   sampled by `experiment2_sample_pool.py` stratified by candidate-count bucket) fill in
   the short/typical-length candidate lists the original 181 barely had any of.

Pipeline: `experiment2_sample_pool.py` → `annotate_experiment2.py` (human labels
`data/annotations_batch2.jsonl`) → `experiment2_build_augmented_dataset.py` (builds the
natural+shuffled pool) → `experiment2_build_train_dev_split.py` (the approved 158/18
train/dev split, source-level, twins always kept together) →
`experiment2_verify_launcher_readiness.py` (10-point integrity audit) →
`finetune_launch_together_experiment2.py` (the real training run, same LoRA
hyperparameters as Experiment 1 — n_epochs=3, lr=1e-5, lora_r=8 — to isolate the dataset
change as the only variable).

Two further findings drove additional investigation, both in `experiment2_deploy_evaluate_stop.py`
and the mini-tests built on top of it:

- The first full evaluation (`results/evaluation_initial.*`) had 26/50 calls return no
  valid prediction — not a billing issue this time, but the model occasionally emitting
  verbose reasoning or a candidate-list dump instead of `{"selected_index": N}`.
  `experiment2_retry_failed_examples.py` recovered 23 of the 26 (47/50 total); 3 never
  recovered after 3 attempts even at `temperature=0`
  (`experiment2_temp0_stability_test.py`).
- Switching `response_format` from loose `json_object` to a **strict `json_schema`**
  (`selected_index` required, `additionalProperties: false`, dynamic min/max) fixed the
  format problem completely: an 11-example probe
  (`experiment2_json_schema_test.py`) and then the full 50-example re-run
  (`experiment2_evaluate_jsonschema_full50.py`) both got **0 format failures**.
  Accuracy itself did not meaningfully change — this was a formatting fix, not an
  accuracy fix; the two remain separate open questions.

### Canonical evaluation

**`experiments/experiment2/results/evaluation_final.jsonl` / `evaluation_final_summary.json`
is the canonical Experiment 2 result** — the full 50-example run using strict
`json_schema`, 0 format failures. `scripts/evaluate/compare_experiments_final.py` reads
this file (not the older one) as Experiment 2's result.

`evaluation_initial.jsonl` / `evaluation_initial_summary.json` are the original
`json_object`-based full-50 run (26 initial format failures, 47/50 after retries) —
**preserved as historical data**, showing the format-reliability problem this project
diagnosed and fixed. Not read by any current script.

## Manual review

Human-in-the-loop review sheets live in `experiments/experiment2/review/`:
- `manual_review_initial.csv` — corresponds to the initial (`evaluation_initial`) run.
- `manual_review_final.csv` — corresponds to the canonical (`evaluation_final`) run, with
  `human_review` / `review_notes` columns left blank for manual judgment (`correct` /
  `acceptable` / `wrong`, etc.) — never filled in automatically.

## Directory structure

```
finetuning/
├── shared/dataset_io.py            generic JSONL/JSON I/O helpers, used everywhere
├── data/                           shared, cross-experiment canonical data
│   ├── annotations.jsonl               the 181 human labels
│   ├── v7_cache.json                   V7-comparison cache used by annotate.py
│   └── splits/{train,test}.jsonl       the fixed 131/50 split
├── scripts/
│   ├── data/                       annotate.py, split_dataset.py, finetune_prepare.py
│   └── evaluate/                   compare_experiments_final.py (cross-experiment)
├── results/
│   └── final_comparison_report.json    Human vs V7 vs Exp1 vs Exp2, one file
└── experiments/
    ├── experiment1/
    │   ├── together_dataset_audit.md   pre-Exp1 corpus audit that justified Exp2
    │   ├── scripts/                    launch/evaluate (OpenAI-abandoned + real Together)
    │   ├── data/                       train_ft.jsonl, test_ft.jsonl
    │   ├── results/                    baseline, trained-model info, eval results
    │   └── deployment/                 dedicated-endpoint metadata
    └── experiment2/
        ├── scripts/                    sampling, annotation, augmentation, split,
        │                               verification, launch, deploy/evaluate/stop,
        │                               retry, and the temp0/json_schema mini-tests
        ├── data/                       candidate pool, batch-2 labels, natural+shuffled
        │                               pool, final train/dev files actually uploaded
        ├── results/                    trained-model info, both eval runs (initial +
        │                               canonical final), all audit/construction reports
        ├── review/                     manual-review CSVs
        └── deployment/                 dedicated-endpoint metadata
```

## Reproducing each stage

| Stage | Script |
|---|---|
| Label the original 181 | `scripts/data/annotate.py` |
| Build the 131/50 split | `scripts/data/split_dataset.py` |
| Prepare Exp1 chat-format training data | `scripts/data/finetune_prepare.py` |
| Launch Exp1 training | `experiments/experiment1/scripts/finetune_launch_together.py` |
| Deploy/evaluate/stop Exp1 | `together_dmi_endpoint.py` + `finetune_evaluate_together.py` |
| Sample Exp2's new 45-example pool | `experiments/experiment2/scripts/experiment2_sample_pool.py` |
| Label the new 45 | `annotate_experiment2.py` |
| Build the natural+shuffled augmentation | `experiment2_build_augmented_dataset.py` |
| Build the approved train/dev split | `experiment2_build_train_dev_split.py` |
| Verify readiness before launch | `experiment2_verify_launcher_readiness.py` |
| Launch Exp2 training | `finetune_launch_together_experiment2.py` |
| Deploy → evaluate all 50 → stop (safe lifecycle) | `experiment2_deploy_evaluate_stop.py` |
| Retry examples that failed to produce valid output | `experiment2_retry_failed_examples.py` |
| Temperature=0 stability probe | `experiment2_temp0_stability_test.py` |
| json_schema format-reliability probe (11 examples) | `experiment2_json_schema_test.py` |
| **Canonical full-50 json_schema evaluation** | `experiment2_evaluate_jsonschema_full50.py` |
| Human vs V7 vs Exp1 vs Exp2 comparison | `scripts/evaluate/compare_experiments_final.py` |

All scripts that call the Together API cost money to run (fine-tuning jobs and dedicated
endpoints are billed). The `*_stop.py`/`*_evaluate_stop.py` scripts always shut down and
verify 0 active replicas in a `finally` block, even on failure.
