"""
Experiment 3, step 1: build the initial 80-100 term candidate pool, then select
~50 for human annotation, prioritizing disease/condition terms and specific
Experiment 2 failure-mode patterns (see error_analysis.md).

Classification is content-based, not title-keyword-only: each candidate term is
judged by (a) its MedlinePlus `categories` metadata, (b) regex patterns for
disease-defining language actually present in its short_description/candidate
sentences (e.g. "is a disorder that", "occurs when", "is a type of cancer"), and
(c) explicit deprioritization patterns for lifestyle/how-to/administrative
framing. This script's output is a PROPOSAL -- the final ~50 must still be
manually reviewed against their actual text before annotation, which is done as
a separate inspection pass (see experiment3_disease_classification_report.json
and the manual spot-check notes in the sampling report).

Excludes every term already present in either annotations.jsonl (181) or
experiment2's annotations_batch2.jsonl (45) -- 226 terms total, which covers the
131 Experiment 1 training examples, the 45 Experiment 2 additions, and (since
splits/test.jsonl is a subset of annotations.jsonl) the 50 held-out test
examples, all at once.

Usage:
    python experiment3_sample_pool.py
"""

import json
import os
import random
import re
import sys
from collections import Counter

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(_THIS_DIR))))
_SERVER_INIT_DIR = os.path.join(_REPO_ROOT, "server_init")
_SHARED_DIR = os.path.join(_REPO_ROOT, "finetuning", "shared")
for _path in (_REPO_ROOT, _SERVER_INIT_DIR, _SHARED_DIR):
	if _path not in sys.path:
		sys.path.insert(0, _path)

from create_clearmed_db import _clean_candidate_sentences  # noqa: E402
from config import JSON_FILE  # noqa: E402

from dataset_io import load_jsonl, write_json_atomic  # noqa: E402

FINETUNING_DIR = os.path.join(_REPO_ROOT, "finetuning")
ANNOTATIONS_FILE = os.path.join(FINETUNING_DIR, "data", "annotations.jsonl")
BATCH2_FILE = os.path.join(FINETUNING_DIR, "experiments", "experiment2", "data", "annotations_batch2.jsonl")

EXP3_DIR = os.path.join(FINETUNING_DIR, "experiments", "experiment3")
POOL_FILE = os.path.join(EXP3_DIR, "data", "candidate_pool_80_100.json")
SELECTION_FILE = os.path.join(EXP3_DIR, "data", "candidate_pool_selected_50.json")
REPORT_FILE = os.path.join(EXP3_DIR, "results", "sampling_report.json")

SEED = 42
INITIAL_POOL_TARGET = 90
FINAL_SELECTION_TARGET = 50

# --- Content-based classification -------------------------------------------

# Real disease/condition-associated MedlinePlus categories. Membership alone is
# NOT sufficient (e.g. "Diagnostic Tests" or "Brain and Nerves" apply to many
# non-disease topics too) -- used only as one signal among several.
DISEASE_LEANING_CATEGORIES = {
	"Infections", "Cancers", "Genetics/Birth Defects", "Metabolic Problems",
	"Mental Health and Behavior", "Immune System", "Substance Use and Disorders",
}
# Categories that, when present, lean strongly toward the deprioritized
# "general informational / lifestyle / administrative" bucket.
INFORMATIONAL_LEANING_CATEGORIES = {
	"Wellness and Lifestyle", "Health System", "Safety Issues",
	"Social/Family Issues", "Personal Health Issues", "Disasters",
	"Food and Nutrition",
}

_DISEASE_DEFINING_PATTERNS = [
	r"\bis an?\s+(rare\s+|common\s+|chronic\s+|acute\s+|genetic\s+|viral\s+|bacterial\s+|fungal\s+|autoimmune\s+|inherited\s+)*"
	r"(disease|disorder|condition|syndrome|infection|illness)\b",
	r"\bis a type of (cancer|infection|disease|disorder|arthritis|diabetes)\b",
	r"\b(cancer|carcinoma|leukemia|lymphoma|tumor|melanoma)\b.{0,40}\b(that|which)\s+(begins|starts|forms|develops|grows)\b",
	r"\boccurs when\b",
	r"\bhappens when\b",
	r"\bis caused by (a |an )?(virus|bacteria|infection|mutation|problem)\b",
]
_INFORMATIONAL_TITLE_PATTERNS = [
	r"^how to\b", r"^guide to\b", r"^understanding\b", r"^living with\b",
	r"^coping with\b", r"^evaluating\b", r"^tips for\b", r"^caring for\b",
	r"\band (young people|older adults|children)\b",
]

_disease_re = re.compile("|".join(_DISEASE_DEFINING_PATTERNS), re.IGNORECASE)
_informational_title_re = re.compile("|".join(_INFORMATIONAL_TITLE_PATTERNS), re.IGNORECASE)

# Manually verified by reading short_description/simple_explanation text (not
# guessed from the title): these are treatment/prevention MODALITIES, not the
# diseases they discuss, so the disease-defining regex false-positives on
# language like "diphtheria is a serious infection" that appears inside an
# article whose actual subject is the vaccine/drug/therapy, not the disease.
_TREATMENT_MODALITY_TITLE_RE = re.compile(
	r"\b(chemotherapy|medicines|vaccine|vaccines|gene therapy|drug therapy)\b", re.IGNORECASE
)
# Manually verified: "Pregnancy and X" titles in this corpus are consistently
# advisory/safety-guidance articles (medicine safety, infection-avoidance tips,
# staying away from substances), not a diagnosis themselves.
_PREGNANCY_GUIDANCE_TITLE_RE = re.compile(r"^pregnancy and\b", re.IGNORECASE)
# Manually verified false positives that don't fit a clean general pattern:
# physiological-parameter/overview topics whose surrounding text triggers the
# disease regex via mentions of the diseases they relate to, without the term
# itself naming one.
_MANUAL_DOMAIN_OVERRIDES = {
	"Body Weight": "other_medical",
	"Blood Glucose": "other_medical",
	"Mental Health": "general_informational",
	"Marijuana": "other_medical",
	# "X and Pregnancy" tips/awareness articles (as opposed to "Tumors and
	# Pregnancy", which is genuine medical content about real tumor risk/
	# treatment during pregnancy, not advisory framing -- kept as-is):
	"Infections and Pregnancy": "general_informational",
	"Animal Diseases and Your Health": "general_informational",
	"Germs and Hygiene": "general_informational",
}


def classify_domain(term, short_description, candidates, categories):
	"""Returns one of 'disease_condition', 'other_medical', 'general_informational'.
	Content-based: checks actual explanation text for disease-defining language,
	not just the term string. A handful of confirmed false positives (found by
	manually reading borderline results from an earlier pass) are corrected via
	explicit, documented overrides rather than a blind broader regex."""
	if term in _MANUAL_DOMAIN_OVERRIDES:
		return _MANUAL_DOMAIN_OVERRIDES[term]
	if _TREATMENT_MODALITY_TITLE_RE.search(term):
		return "other_medical"
	if _PREGNANCY_GUIDANCE_TITLE_RE.search(term):
		return "general_informational"

	text_to_check = " ".join([short_description or ""] + candidates[:4])

	if _informational_title_re.search(term):
		return "general_informational"

	disease_hit = bool(_disease_re.search(text_to_check))
	cats = set(categories or [])
	disease_cat_hit = bool(cats & DISEASE_LEANING_CATEGORIES)
	informational_cat_hit = bool(cats & INFORMATIONAL_LEANING_CATEGORIES) and not disease_cat_hit

	if disease_hit:
		return "disease_condition"
	if informational_cat_hit and not disease_cat_hit:
		return "general_informational"
	if disease_cat_hit:
		return "disease_condition"
	# Ambiguous: neither a clear disease-defining sentence nor a clear
	# lifestyle/admin category. Treat as "other medical" (e.g. a test, a
	# procedure, an anatomical/physiological topic) pending manual review.
	return "other_medical"


# --- Failure-mode structural signals -----------------------------------------

_GENERIC_LEAD_RE = re.compile(
	r"^\s*[\w\s\-,()]+?\s+is\s+an?\s+([\w\-]+\s+)?(type|kind|form)\s+of\b", re.IGNORECASE
)
_FUNCTIONAL_RE = re.compile(
	r"\b(causes?|happens when|affects?|helps? you|can lead to|results? in|relearn|damage[sd]?|"
	r"leads? to|makes? it (hard|difficult)|prevents?|allows? (you|people))\b", re.IGNORECASE
)
_RELATED_FACT_RE = re.compile(
	r"\bis caused by\b|\brange[sd]? from\b|\bmild to severe\b|\brisk of\b|\bincreases? (your |the )?risk\b|"
	r"\brisk factor\b|\bcontains?\b|\bmade up of\b|\bproperties\b", re.IGNORECASE
)


def failure_mode_signals(term, candidates):
	n = len(candidates)
	first_two = candidates[:2]
	generic_lead = any(_GENERIC_LEAD_RE.search(s) for s in first_two)
	has_functional = any(_FUNCTIONAL_RE.search(s) for s in candidates)
	has_related_fact = any(_RELATED_FACT_RE.search(s) for s in candidates)
	is_compound = bool(re.search(r"\band\b|,", term))
	n_questions = sum(1 for s in candidates if s.strip().endswith("?"))
	faq_heavy = n > 0 and (n_questions / n) >= 0.15 and n_questions >= 3

	return {
		"n_candidates": n,
		"generic_definition_lead": generic_lead and has_functional,
		"related_fact_distractor": has_related_fact and not (generic_lead and has_functional),
		"is_compound_term": is_compound,
		"faq_heavy": faq_heavy,
		"n_questions": n_questions,
	}


def assign_bucket(domain, signals):
	if signals["is_compound_term"]:
		return "compound_multi_part"
	if signals["faq_heavy"]:
		return "rare_failure_mode"
	if signals["generic_definition_lead"]:
		return "generic_vs_functional"
	if signals["related_fact_distractor"]:
		return "related_fact_vs_explanation"
	if signals["n_candidates"] >= 45:
		return "other_hard_case"
	return "unclassified"


BUCKET_TARGETS = {
	"generic_vs_functional": 20,
	"related_fact_vs_explanation": 15,
	"compound_multi_part": 7,
	"other_hard_case": 4,
	"rare_failure_mode": 4,
}
DOMAIN_PRIORITY = {"disease_condition": 0, "other_medical": 1, "general_informational": 2}


def main():
	with open(JSON_FILE, encoding="utf-8") as f:
		all_terms = json.load(f)["terms"]

	existing = load_jsonl(ANNOTATIONS_FILE) + load_jsonl(BATCH2_FILE)
	excluded_ids = {str(r["source_id"]) for r in existing}
	assert len(excluded_ids) == 226, f"expected 226 excluded terms, got {len(excluded_ids)}"

	candidates_pool = []
	skipped_too_few = 0
	for item in all_terms:
		source_id = str(item.get("source_id"))
		if source_id in excluded_ids:
			continue
		sentences = _clean_candidate_sentences(item.get("simple_explanation"))
		if len(sentences) < 2:
			skipped_too_few += 1
			continue

		term = item.get("term") or ""
		categories = item.get("categories") or []
		domain = classify_domain(term, item.get("short_description"), sentences, categories)
		signals = failure_mode_signals(term, sentences)
		bucket = assign_bucket(domain, signals)

		candidates_pool.append({
			"source_id": item.get("source_id"),
			"term": term,
			"candidates": sentences,
			"categories": categories,
			"candidate_count": len(sentences),
			"domain": domain,
			"bucket": bucket,
			"signals": signals,
		})

	print(f"Corpus: {len(all_terms)} terms, excluded {len(excluded_ids)}, "
	      f"skipped {skipped_too_few} (<2 candidates), remaining pool: {len(candidates_pool)}")

	domain_counts = Counter(c["domain"] for c in candidates_pool)
	bucket_counts = Counter(c["bucket"] for c in candidates_pool)
	print("Domain distribution across all unused terms:", dict(domain_counts))
	print("Bucket distribution across all unused terms:", dict(bucket_counts))

	# --- Build a generous per-bucket shortlist from the FULL unused pool (not a
	# single global top-N cut, which would starve small buckets before bucket
	# balancing even happens). Each bucket gets ~2x its final target as headroom,
	# always sorted disease-domain first, richer (longer) candidate lists next.
	rng = random.Random(SEED)

	def bucket_sort_key(c):
		return (DOMAIN_PRIORITY.get(c["domain"], 3), -c["candidate_count"], str(c["source_id"]))

	by_bucket_full = {}
	for c in candidates_pool:
		by_bucket_full.setdefault(c["bucket"], []).append(c)
	for items in by_bucket_full.values():
		rng.shuffle(items)  # break ties fairly before the stable sort below
		items.sort(key=bucket_sort_key)

	shortlist = []
	shortlist_ids = set()
	for bucket, target in BUCKET_TARGETS.items():
		headroom = max(target * 2, target + 6)
		for c in by_bucket_full.get(bucket, [])[:headroom]:
			if str(c["source_id"]) not in shortlist_ids:
				shortlist.append(c)
				shortlist_ids.add(str(c["source_id"]))

	# Top up to INITIAL_POOL_TARGET with the next-best disease-domain
	# "unclassified" or other-bucket items, for general depth/safety margin.
	leftover = [c for c in candidates_pool if str(c["source_id"]) not in shortlist_ids]
	leftover.sort(key=bucket_sort_key)
	for c in leftover:
		if len(shortlist) >= INITIAL_POOL_TARGET:
			break
		shortlist.append(c)
		shortlist_ids.add(str(c["source_id"]))

	initial_pool = shortlist
	write_json_atomic(POOL_FILE, initial_pool)
	print(f"Initial pool: {len(initial_pool)} terms -> {POOL_FILE}")

	# --- Narrow to ~50, respecting bucket guidelines as soft targets, always
	# preferring disease/condition terms over weaker non-disease ones. Pulls
	# from the shortlist (which already has 2x headroom per bucket), so a
	# bucket losing items to domain reclassification still has real
	# disease-domain alternatives to fall back on.
	by_bucket = {}
	for c in initial_pool:
		by_bucket.setdefault(c["bucket"], []).append(c)
	for items in by_bucket.values():
		items.sort(key=bucket_sort_key)

	selected = []
	selected_ids = set()
	for bucket, target in BUCKET_TARGETS.items():
		for c in by_bucket.get(bucket, [])[:target]:
			selected.append(c)
			selected_ids.add(str(c["source_id"]))

	# Fill remaining slots up to FINAL_SELECTION_TARGET from leftover shortlist
	# items, still prioritizing disease/condition domain first.
	remaining = [c for c in initial_pool if str(c["source_id"]) not in selected_ids]
	remaining.sort(key=bucket_sort_key)
	for c in remaining:
		if len(selected) >= FINAL_SELECTION_TARGET:
			break
		selected.append(c)
		selected_ids.add(str(c["source_id"]))

	# --- Manual editorial swaps, made after reading the actual short_description
	# of every automatically-selected term. Both replaced terms turned out to be
	# weaker (a basic-science-education topic and a risk-awareness/advisory
	# article) than stronger disease/condition compound-term alternatives found
	# by reading the broader unused pool -- applied here rather than generalized
	# into a regex, since these are one-off editorial judgments, not a pattern.
	MANUAL_SWAPS = {
		"Genes and Gene Therapy": "Dandruff, Cradle Cap, and Other Scalp Conditions",
		"Smoking and Youth": "Dizziness and Vertigo",
	}
	by_term_full = {c["term"]: c for c in candidates_pool}
	for i, c in enumerate(selected):
		if c["term"] in MANUAL_SWAPS:
			replacement_term = MANUAL_SWAPS[c["term"]]
			replacement = by_term_full.get(replacement_term)
			if replacement is None:
				raise RuntimeError(f"Manual swap target {replacement_term!r} not found in unused pool.")
			replacement = dict(replacement)
			replacement["bucket"] = c["bucket"]  # keep it in the same failure-mode slot
			selected[i] = replacement
			print(f"Manual swap: {c['term']!r} -> {replacement_term!r} (verified stronger disease/condition example)")

	write_json_atomic(SELECTION_FILE, selected)
	print(f"Final selection: {len(selected)} terms -> {SELECTION_FILE}")

	sel_domain_counts = Counter(c["domain"] for c in selected)
	sel_bucket_counts = Counter(c["bucket"] for c in selected)

	report = {
		"seed": SEED,
		"corpus_total_terms": len(all_terms),
		"excluded_already_used": len(excluded_ids),
		"skipped_lt_2_candidates": skipped_too_few,
		"unused_pool_size": len(candidates_pool),
		"unused_pool_domain_distribution": dict(domain_counts),
		"unused_pool_bucket_distribution": dict(bucket_counts),
		"initial_pool_size": len(initial_pool),
		"final_selection_size": len(selected),
		"final_selection_domain_distribution": dict(sel_domain_counts),
		"final_selection_bucket_distribution": dict(sel_bucket_counts),
		"bucket_targets": BUCKET_TARGETS,
	}
	write_json_atomic(REPORT_FILE, report)

	print()
	print("Final selection domain distribution:", dict(sel_domain_counts))
	print("Final selection bucket distribution:", dict(sel_bucket_counts))
	print(f"Report: {REPORT_FILE}")


if __name__ == "__main__":
	main()
