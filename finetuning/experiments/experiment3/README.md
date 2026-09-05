# Experiment 3 — disease/condition-priority hard-negative batch

**Status: data collection in progress. No training has been launched.**

## Purpose

Experiment 3 targets the two error clusters found in the canonical Experiment 2
evaluation's error analysis (`../experiment2/review/error_analysis.md`), which together
account for 71.4% of Experiment 2's wrong picks:

1. **generic-vs-functional** (35.7%): the model prefers a generic, definitional-sounding
   sentence ("X is a type of Y") over a more substantive functional/mechanistic one.
2. **related-fact-vs-explanation** (35.7%): the model picks a topically-relevant but
   off-target sentence (cause, severity, future risk, composition) instead of a sentence
   that actually explains the term.

## Sampling (done)

`scripts/experiment3_sample_pool.py` builds an ~80-100 term candidate pool from the 790
still-unused MedlinePlus terms (excluding all 226 terms already in `annotations.jsonl` +
`annotations_batch2.jsonl`), classifies each by domain (disease/condition vs. other
medical vs. general informational -- content-based, verified by manually reading
`short_description` text rather than title keywords) and by failure-mode bucket, then
selects 50 for annotation with a strong preference for disease/condition terms and the
five target failure-mode buckets. See `results/sampling_report.json` for exact counts:
45/50 disease/condition, 5/50 other medically-meaningful terms, 0/50 general
informational.

Output: `data/candidate_pool_selected_50.json` (read-only from here on; never modified by
the annotation tool).

## Annotation (in progress)

`scripts/annotate_experiment3.py` labels the 50 selected terms. See the tool's own
docstring for exact behavior. Output: `data/annotations_batch3.jsonl`.

## Critical requirement: Experiment 3 extends Experiment 2, it does not replace it

The 50 new Experiment 3 annotations are an **addition** to the existing training set, not
a standalone dataset. When the Experiment 3 training pipeline is eventually built (not yet
started), it must:

- Include all of Experiment 2's approved training data (the 131 original + 45 batch-2
  examples and their shuffled twins, i.e. everything currently flowing into
  `experiments/experiment2/data/` via `experiment2_build_augmented_dataset.py` and
  `experiment2_build_train_dev_split.py`) as the base.
- Add the new 50 Experiment 3 examples (and, following the Experiment 2 precedent, their
  shuffled twins at `weight: 0.5`) on top of that base -- not train on the 50 alone.
- Continue to treat `finetuning/data/splits/test.jsonl` (the fixed 50-example held-out
  set) as sacred: never included in training/augmentation for any experiment.
- Reuse the same isolate-one-variable discipline as Experiments 1-2: keep hyperparameters
  fixed unless a hyperparameter change is itself the thing being tested, so any accuracy
  delta can be attributed to the added data rather than a confound.

This requirement is recorded here so it is not lost before the Experiment 3 training
pipeline is actually built and launched (which requires separate explicit approval, per
the same cost-control rules as Experiments 1-2).
