# Why Experiment 3 regressed vs. Experiment 2

**Result being explained**: Experiment 3 (42.0%, 21/50) scored 8 points below Experiment 2
(50.0%, 25/50) on the identical 50-example held-out test set, despite adding 50 new,
carefully curated disease/condition examples on top of Experiment 2's exact training data.
Net: 2 improved, 6 regressed, 42 unchanged.

All analysis below is purely local (test-set predictions + training-data files already on
disk). Nothing was retrained or re-evaluated to produce this document.

## Finding 1: the regression is concentrated in the largest candidate-list stratum

The held-out test set has no examples with 20 or fewer candidates -- it is 18/50 (36%)
`21-40` and **32/50 (64%) `>40`** candidates. Accuracy by bucket:

| Candidate-count bucket | n | Exp2 accuracy | Exp3 accuracy | Delta |
|---|---:|---:|---:|---:|
| 21-40 | 18 | 33% (6/18) | 39% (7/18) | **+6pp** |
| \>40 | 32 | 59% (19/32) | 44% (14/32) | **-15pp** |

Experiment 3 actually did slightly *better* on the 21-40 stratum. The entire net regression
comes from the `>40` stratum, which happens to be nearly two-thirds of this test set.

## Finding 2: it is not a reversion to raw index-0/positional bias

Experiment 1's original failure mode was picking index 0 almost regardless of content. If
that had resurfaced, Experiment 3 should show a *higher* index-0 selection rate on the test
set than Experiment 2. It doesn't:

| | Exp2 | Exp3 |
|---|---:|---:|
| Index-0 selected (of 50 predictions) | 50% (25/50) | 48% (24/50) |
| Accuracy when index-0 was selected | 56% (14/25) | 54% (13/24) |

Nearly identical. Whatever changed, it is not simply "the model reverted to guessing the
first candidate."

## Finding 3: the new "generic-vs-functional" training bucket didn't deliver its intended contrastive signal

Experiment 3's 50 new examples were deliberately sampled so that 20 of them (the
`generic_vs_functional` bucket) would contain a plausible generic-definition-style lead
sentence ("X is a type of Y") *alongside* a more substantive functional explanation
elsewhere in the candidate list -- specifically to teach the model that a definitional-
sounding sentence is not automatically the best answer (this was Experiment 2's error
analysis's #1 recommendation, covering 35.7% of Experiment 2's errors).

In practice, once these 50 terms were actually human-labeled, the annotator (you) judged
the generic-sounding lead sentence to genuinely be the best available answer far more often
than not:

| | idx0 (or near-0) selection rate in human labels |
|---|---:|
| Experiment 2's 158-example base (all buckets) | 55.7% |
| **New 50 batch, `generic_vs_functional` bucket specifically** | **65% (13/20)** |
| New 50 batch, `related_fact_vs_explanation` bucket | 67% (10/15) |
| New 50 batch, overall (all 50) | 60% (30/50) |

Rather than teaching "don't reflexively prefer the generic-sounding sentence," the batch's
actual ground truth mostly reinforced the opposite: for a majority of these specific
disease/condition terms, the short, generic-sounding definition genuinely *is* the correct
explanation. This is a legitimate, defensible per-term judgment (many of these terms --
Rheumatoid Arthritis, Osteoarthritis, Neuroblastoma, Dual Diagnosis, Ebola, Oral Cancer,
Kaposi Sarcoma, Hodgkin Lymphoma, Wilms Tumor -- really are best explained by their opening
definition sentence). But it means the *sampling heuristic* (a regex looking for
"definition-like lead + functional sentence present somewhere else") selected terms that
structurally *resembled* the Experiment 2 failure pattern without reliably reproducing the
underlying *contrast* (generic-sounds-right-but-isn't) that made those failures instructive.

Three of the six regressed test examples show exactly this signature -- Experiment 3 chose
a short, generic-sounding sentence where Experiment 2 had correctly chosen a longer,
functional/mechanistic one that matches the human label:

| Term | Human/Exp2 pick (correct) | Exp3's new pick (wrong) |
|---|---|---|
| Chronic Myeloid Leukemia | "In CML, the bone marrow makes abnormal granulocytes..." | "Chronic myeloid leukemia (CML) **is a type of** chronic leukemia." |
| Eosinophilic Esophagitis | "If you have EoE, white blood cells called eosinophils build up in your esophagus." | "Eosinophilic esophagitis (EoE) **is a chronic disease of** the esophagus." |
| Radiation Exposure | "But too much radiation can damage tissues by changing cell structure and damaging DNA." | "Radiation **is energy**." |

## Finding 4: the remaining three regressions look like plain noise on very large, redundant lists

The other three regressions (Heart Health Tests, Heart Surgery, HIV: PrEP and PEP) don't
fit the generic-definition pattern -- e.g. Heart Surgery's new pick ("Minimally invasive
heart surgery uses small cuts between the ribs," index 43 of 53) is *too specific*, the
opposite direction. These look like ordinary instability when discriminating among very
large (45-63 candidate), highly redundant lists, not a single clean bias. This is
consistent with training-data composition: the new 50 examples skew toward `hard`
difficulty (18/50 = 36%, by your own annotation) and toward long lists, without adding any
short-list (<=20 candidate) diversity at all (0 of the 50 fall below 21 candidates) --
so the model got more exposure to hard, long-list judgment calls, but not more exposure to
the short/typical lists production actually mostly serves.

## What this does and doesn't show

- This does **not** show Experiment 3 is uniformly worse. It slightly improved on the
  21-40 bucket, and both of its two improvements (Opioid Use Disorder Treatment, Inhalants)
  are genuine corrections of real Experiment 2 errors.
- It does **not** prove the new data is bad in general -- only that it under-delivered on
  its single most-targeted failure mode (`generic_vs_functional`), specifically because
  the sampling heuristic and the actual human judgment didn't agree as often as assumed.
- The held-out test set is a demanding, non-representative stress test for this specific
  question: it is 64% `>40`-candidate examples, while production's real candidate-list
  distribution skews short (the reason Experiment 2 added short-list examples in the first
  place). A regression concentrated entirely in the test set's `>40` stratum says less
  about typical production performance than it would if the regression were spread evenly.

## Suggested direction for Experiment 4 (not started, no action taken)

1. When re-sampling a "generic-vs-functional" contrastive batch, filter candidates *after*
   labeling, not before: keep only examples where the human label actually lands on the
   non-generic/functional sentence, discarding ones where the generic lead turned out to be
   genuinely correct (this doesn't need new terms, just re-triaging the labels already
   collected in `annotations_batch3.jsonl`).
2. Any future distribution-correction batch should include some short/typical
   (<=20 candidate) examples too, not exclusively long lists, to avoid narrowing the
   training mix's length diversity even as candidate-list realism for the *content* problem
   is prioritized.
