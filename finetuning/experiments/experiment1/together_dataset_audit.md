# Together AI LoRA Fine-Tuning Dataset Audit

Analysis only. No dataset, script, or code files were modified while producing this report.
Generated against the repository state on the `ai-short-explanation` branch, using
`annotation/data/annotations.jsonl`, `annotation/data/splits/{train,test}.jsonl`,
`annotation/data/finetune/{train_ft,test_ft}.jsonl`, and `server_init/create_clearmed_db.py`.

## TL;DR

- 181 labeled examples, structurally clean: no duplicates, no invalid indices, no malformed
  records, 0% drift between stored `candidates` and what the current splitting logic would
  produce today.
- Format is already Together-AI-compatible (OpenAI-style `messages` conversational JSONL) and
  already mirrors the exact production V7 prompt — `annotation/data/finetune/train_ft.jsonl` /
  `test_ft.jsonl` can likely be reused as-is.
- **Critical issue**: the annotated set is extremely skewed toward long candidate lists relative
  to the real corpus (median 48 candidates/example vs. median 14 across all 1,017 terms; 0% of
  annotated examples have ≤10 candidates even though that's 31.5% of the real corpus). This was
  produced by the "hard example" difficulty-prioritization built into the annotation tool, and is
  worth an explicit decision before training. See §7.

## 1. Dataset structure

Every one of the 181 records in `annotation/data/annotations.jsonl` has exactly this field set
(verified — one single field-set signature across all 181 rows, no partial/legacy records):

| field | type | notes |
|---|---|---|
| `source_id` | str | MedlinePlus source id |
| `term` | str | medical term/topic name |
| `candidates` | list[str] | output of `_clean_candidate_sentences(simple_explanation)` — verbatim sentences, never rewritten |
| `simple_explanation` | str | original full MedlinePlus text the candidates were split from |
| `current_v7_index` | int | V7's (gpt-4o-mini) pick at annotation time, always present, always in range |
| `v7_source` | str | `"ai"` for all 181 records (no fallback-heuristic picks in this batch) |
| `selected_index` | int | **human ground truth** — always in range |
| `agrees_with_v7` | bool | `current_v7_index == selected_index` |
| `annotated_at` | ISO8601 str | 2026-08-18T11:24 → 2026-08-18T16:59 (single session) |

`candidates` regeneration check: re-running `_clean_candidate_sentences` on the stored
`simple_explanation` for all 181 records reproduces the stored `candidates` list exactly,
0 mismatches. The dataset has not drifted from the current splitting logic.

## 2. Dataset size

| split | count |
|---|---|
| Total labeled (`annotations.jsonl`) | 181 |
| Train (`splits/train.jsonl`) | 131 |
| Dev/validation (separate from test) | **none exists today** |
| Held-out test (`splits/test.jsonl`) | 50 |
| train + test | 181 (all annotations accounted for) |

There is no dedicated dev/validation split. `test.jsonl` was previously wired up as the OpenAI
`validation_file` for the (now platform-blocked) fine-tuning job — intended only for loss-curve
visibility, per your original instruction not to use it for hyperparameter decisions. Because
that job never actually started training (403 before the run began), `test.jsonl` has in
practice **never been touched by any training process**.

## 3. Split integrity

- Duplicate `source_id` within `annotations.jsonl`: **0**.
- Duplicate `term` (case-insensitive) within `annotations.jsonl`: **0**.
- `source_id` overlap between `train.jsonl` and `test.jsonl`: **0** (fully disjoint).
- `len(train) + len(test) == len(annotations)`: 131 + 50 = 181 ✓ (nothing dropped or duplicated
  by the split).
- Candidate-count distribution is consistent between the two splits (train mean 49.2/median 49,
  test mean 46.6/median 46.5) — the split isn't accidentally easier or shorter on one side.
- V7 agreement is consistent between splits: train 92/131 = 70.2%, test 35/50 = 70.0%. Good sign
  the split wasn't cherry-picked.
- One asymmetry worth knowing: the fraction of examples where the human picked index 0 is 51.9%
  in train vs. 34.0% in test — a 17.8-point gap. With only 50 test examples this is plausibly
  sampling noise, but flag it if fine-tuned-model eval numbers look surprising later.
- No data leakage found: the split is a deterministic seeded shuffle (`split_dataset.py`,
  seed=42) over the full annotation set, done once, and both `train_ft.jsonl`/`test_ft.jsonl`
  were built independently from `train.jsonl`/`test.jsonl` respectively — same source records,
  no cross-contamination.

## 4. Label quality / validity

- `selected_index` out of range or non-integer: **0 / 181**.
- `current_v7_index` out of range, non-integer, or missing: **0 / 181** (every record has a V7
  comparison — no null/unavailable cases in this batch).
- Empty or whitespace-only candidate strings: **0**.
- Missing `simple_explanation`: **0**.
- Candidate-count distribution across the 181 labeled records: **min 14, median 48, mean 48.5,
  max 75** (full histogram available via `annotation/finetune_prepare.py`-style tooling if
  needed; omitted here for brevity — see §7 for why this matters).
- `selected_index` position distribution is front-loaded: index 0 chosen in 85/181 (47%) of
  records, tapering off with a long tail up to index 65. Expected — first sentence is often the
  definitional one — but a model could learn "guess 0" as a strong prior; the position skew
  differing between train/test (§3) is the more concrete symptom of this to watch.

No malformed or structurally suspicious records were found.

## 5. Together AI compatibility

Together AI's supervised fine-tuning (both LoRA and full) accepts the same **OpenAI-style
conversational JSONL** format we already use: one JSON object per line, a `messages` array of
`{"role": ..., "content": ...}` objects, starting with `system` or `user` and alternating
`user`/`assistant` after that. By default, training loss is computed only on `assistant`
messages, which is exactly what we want here (we only want the model learning to emit
`{"selected_index": N}`, not to reproduce the prompt).

`annotation/data/finetune/train_ft.jsonl` (131 lines) and `test_ft.jsonl` (50 lines) — built
earlier for the abandoned OpenAI attempt — already match this shape exactly:

- All 181 combined examples have role order `[system, user, assistant]`.
- All assistant `content` values are valid JSON of the form `{"selected_index": N}`.
- Exactly one distinct system prompt is used across all examples (the verbatim `_SYSTEM_PROMPT`
  from `create_clearmed_db.py`, not retyped).

**No reformatting is needed to use these two files for Together AI**, modulo the token-count and
distribution caveats below.

Model check: `Qwen/Qwen3.5-9B` is confirmed as a valid Together AI model identifier supported for
LoRA fine-tuning (and also full fine-tuning).

Token budget (rough chars/4 estimate — re-check with Together's actual tokenizer before
submitting, especially for the longest examples):

| | system | user (mean) | user (max) | total (mean) | total (max) |
|---|---|---|---|---|---|
| train | ~1,643 tok | ~1,160 tok | ~1,678 tok | ~2,813 tok | ~3,331 tok |
| test | ~1,643 tok | ~1,114 tok | ~1,636 tok | ~2,767 tok | ~3,289 tok |

Comfortably inside Qwen3.5-9B's context window — not a blocker. But note the ~1,643-token system
prompt is repeated verbatim in all 181 examples, so a large fraction of every training example's
tokens are fixed boilerplate rather than task-specific signal.

Together's docs describe typical fine-tuning datasets as running to "thousands of examples"; we
have 131 training examples. Not disqualifying — LoRA is specifically suited to small datasets —
but sets expectations: expect higher run-to-run variance than a large dataset would give, keep
LoRA rank modest, and watch for overfitting.

File size (100GB Together limit) is a non-issue at ~1.5MB/~0.5MB for train/test.

## 6. Training/inference consistency

What V7 actually sends today (`server_init/create_clearmed_db.py`):

- **System message**: `_SYSTEM_PROMPT` verbatim (~1,643 tokens, decision-hierarchy instructions
  for picking a standalone, term-defining sentence).
- **User message**: `"Term: {term}\nCandidate sentences (respond with the index of exactly
  one):\n"` followed by `"{i}: {sentence}"` for each `_clean_candidate_sentences(...)` output,
  one per line.
- **Call shape**: `chat.completions.create(model="gpt-4o-mini", response_format={"type":
  "json_object"}, timeout=30)`, expects `{"selected_index": N}`.
- **Fallback**: on any exception or an out-of-range/non-int index, V7 does *not* retry the model —
  it falls back to a deterministic keyword-priority heuristic
  (`_select_short_explanation_fallback`) over the same candidate list.
- **Post-processing**: the chosen sentence is truncated to 30 words (`_truncate_to_max_words`)
  before being stored as `short_explanation`. This truncation happens *after* index selection —
  it doesn't affect what the model is trained to predict (still just an index), but it does mean
  what a patient ultimately sees is a truncated version of whichever sentence gets picked. Keep
  this in mind when eyeballing model outputs qualitatively — comparing raw picked sentences
  without truncation will look different from the actual product output.

`annotation/finetune_prepare.py` (already run once, output present) builds its training examples
by importing `_SYSTEM_PROMPT` directly and reconstructing the user prompt with the identical
string-building logic used here — not a re-implementation. The assistant target is
`{"selected_index": <human label>}`, i.e. the ground truth, not V7's pick. This is already as
close to a production-mirrored training example as it can be; recommend continuing to build any
new training data (e.g. a rebalanced set, see §7) through this same function rather than a new
one.

## 7. Recommendations before fine-tuning (not yet implemented)

1. **CRITICAL — candidate-count distribution mismatch.** Full corpus (1,017 terms, computed via
   `_clean_candidate_sentences` over every term) has median 14 / mean 21.7 candidates, with this
   breakdown: 5.3% have ≤5 candidates, 26.2% have 6–10, 32.9% have 11–20, 17.8% have 21–40, 17.8%
   have >40. The annotated set is nothing like this: median 48 / mean 48.5, **0%** of annotated
   examples have ≤10 candidates, and **74.6%** have >40. This comes directly from
   `annotation/annotate.py`'s `compute_difficulty_score`, whose scoring signals (candidate count,
   category diversity, weak-sentence-start count, similar-length pairs) all correlate with longer
   lists, so the "prefer hard examples" queue you asked for in the original annotation task ended
   up drawing almost exclusively from the long tail. That prioritization was intentional and
   correctly implemented — but the resulting skew is now so extreme that the model would train on
   essentially zero examples resembling the ~64% of real terms that have 1–20 candidates. Before
   fine-tuning, decide explicitly between:
   - (a) treat this as a deliberately "hard-mode" training set and separately evaluate the
     resulting model on a small stratified sample of typical-length terms before any production
     decision, or
   - (b) label a further batch (e.g. 20–30 more examples) specifically drawn from short/typical
     candidate-count terms, to rebalance train/test toward the real production distribution.
2. **MODERATE — no true dev split.** `test.jsonl` has only ever been wired up as an unused
   OpenAI `validation_file` placeholder; nothing has actually trained against it. Recommend
   carving a small dev set (e.g. 15–20 examples) out of `train.jsonl` for Together AI's
   eval-during-training/logging, and keeping `test.jsonl` fully untouched until the one final
   held-out evaluation, consistent with your original instruction.
3. **MINOR — index-0 rate differs between splits.** 51.9% (train) vs. 34.0% (test) chose index 0.
   Likely sampling noise at n=50, but worth a sanity check if eval numbers look off later.
4. **MINOR — verify token counts with Together's real tokenizer**, not the chars/4 estimate used
   here, particularly for the handful of examples with 70+ candidates.
5. **No reformatting needed.** `annotation/data/finetune/train_ft.jsonl` and `test_ft.jsonl` are
   already in Together-compatible conversational format and already mirror the production V7
   prompt exactly (verified in §5/§6). They can likely be reused as-is once the distribution
   decision in (1) is made — no new conversion script is required beyond what
   `annotation/finetune_prepare.py` already does.
6. **Out of scope for this audit**: exact LoRA rank/epoch/learning-rate defaults for
   `Qwen/Qwen3.5-9B` — worth deciding once (1) is resolved.
