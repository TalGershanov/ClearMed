import argparse
import datetime
import hashlib
import json
import os
import random
import sys

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(_THIS_DIR)))
_SERVER_INIT_DIR = os.path.join(_REPO_ROOT, "server_init")
_SHARED_DIR = os.path.join(_REPO_ROOT, "finetuning", "shared")
for _path in (_REPO_ROOT, _SERVER_INIT_DIR, _SHARED_DIR):
	if _path not in sys.path:
		sys.path.insert(0, _path)

from ai_services import _clean_candidate_sentences, _select_short_explanation_index_ai  # noqa: E402
from config import JSON_FILE  # noqa: E402

from dataset_io import load_jsonl, write_jsonl_atomic, load_json, write_json_atomic  # noqa: E402

DATA_DIR = os.path.join(_REPO_ROOT, "finetuning", "data")
ANNOTATIONS_FILE = os.path.join(DATA_DIR, "annotations.jsonl")
V7_CACHE_FILE = os.path.join(DATA_DIR, "v7_cache.json")

# Fixed seed only to break ties between equal-difficulty terms with some variety;
# queue order is otherwise deterministic (score descending) so resuming is predictable.
_TIE_BREAK_SEED = 42

_WEAK_STARTS = (
	"but ", "it ", "it's ", "they ", "this ", "these ", "one ", "another ",
	"in that case", "however", "so ", "also ", "then ", "as a ",
)
_DEFINE_KEYWORDS = ("is a ", "is an ", "are a ", "are an ", "refers to", "means ", "is the ", "are the ")
_CATEGORY_BUCKETS = {
	"define": _DEFINE_KEYWORDS,
	"treatment": ("treat", "therapy", "medicine", "medication", "surgery"),
	"diagnosis": ("test", "diagnos", "screen"),
	"symptom": ("symptom", "sign of", "feel ", "pain"),
}


def compute_difficulty_score(sentences):
	if len(sentences) < 2:
		return -1

	score = min(len(sentences), 6)

	weak_count = sum(1 for s in sentences if s.strip().lower().startswith(_WEAK_STARTS))
	score += weak_count * 2

	question_count = sum(1 for s in sentences if s.strip().endswith("?"))
	score += question_count * 2

	hit_buckets = set()
	for s in sentences:
		low = s.lower()
		for name, keywords in _CATEGORY_BUCKETS.items():
			if any(k in low for k in keywords):
				hit_buckets.add(name)
	if len(hit_buckets) >= 2:
		score += 3

	word_counts = [len(s.split()) for s in sentences]
	similar_pairs = sum(
		1
		for i in range(len(word_counts))
		for j in range(i + 1, len(word_counts))
		if abs(word_counts[i] - word_counts[j]) <= 3
	)
	if similar_pairs >= 2:
		score += 2

	first_has_definition = any(k in sentences[0].lower() for k in _DEFINE_KEYWORDS)
	other_has_definition = any(k in s.lower() for s in sentences[1:6] for k in _DEFINE_KEYWORDS)
	if not first_has_definition and other_has_definition:
		score += 2

	return score


def build_queue(all_terms, annotated_ids):
	scored = []
	for item in all_terms:
		source_id = str(item.get("source_id"))
		if source_id in annotated_ids:
			continue
		sentences = _clean_candidate_sentences(item.get("simple_explanation"))
		score = compute_difficulty_score(sentences)
		if score < 0:
			continue
		scored.append((score, item, sentences))
	random.Random(_TIE_BREAK_SEED).shuffle(scored)
	scored.sort(key=lambda entry: entry[0], reverse=True)
	return scored


def fingerprint(sentences):
	joined = "␟".join(sentences)
	return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16]


def get_v7_choice(source_id, term, sentences, cache, no_ai):
	key = str(source_id)
	fp = fingerprint(sentences)
	cached = cache.get(key)
	if cached and cached.get("fingerprint") == fp:
		return cached.get("index"), cached.get("source")

	if no_ai:
		return None, "skipped"

	index = _select_short_explanation_index_ai(sentences, term=term)
	source = "ai" if index is not None else "unavailable"
	cache[key] = {"fingerprint": fp, "index": index, "source": source}
	write_json_atomic(V7_CACHE_FILE, cache)
	return index, source


def make_record(item, sentences, v7_index, v7_source, selected_index):
	return {
		"source_id": item.get("source_id"),
		"term": item.get("term"),
		"candidates": sentences,
		"simple_explanation": item.get("simple_explanation"),
		"current_v7_index": v7_index,
		"v7_source": v7_source,
		"selected_index": selected_index,
		"agrees_with_v7": (v7_index == selected_index) if v7_index is not None else None,
		"annotated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
	}


def print_item(term, sentences, v7_index, v7_source, progress, target):
	print("-" * 60)
	print(f"Progress: {progress} / {target}")
	print()
	print(f"TERM: {term}")
	print()
	print("Candidates:")
	for i, s in enumerate(sentences):
		print(f"[{i}] {s}")
	print()
	if v7_index is not None:
		print(f"V7 selected: [{v7_index}]")
	else:
		print(f"V7 selected: unavailable ({v7_source})")
	print()


def run_annotation(all_terms, terms_by_id, annotations, annotated_ids, v7_cache, args):
	queue = build_queue(all_terms, annotated_ids)
	if not queue:
		print("No more candidate terms to annotate.")
		return

	print(f"{len(annotations)} existing annotations loaded. {len(queue)} candidate terms available.")

	idx = 0
	while idx < len(queue):
		score, item, sentences = queue[idx]
		term = item.get("term")
		source_id = item.get("source_id")

		v7_index, v7_source = get_v7_choice(source_id, term, sentences, v7_cache, args.no_ai)
		print_item(term, sentences, v7_index, v7_source, len(annotations), args.target)

		try:
			choice = input("Your choice (index / u=undo / q=quit): ").strip().lower()
		except EOFError:
			break

		if choice == "q":
			print("Exiting. All answers so far are saved.")
			break

		if choice == "u":
			if not annotations:
				print("Nothing to undo.")
				continue
			last = annotations.pop()
			write_jsonl_atomic(ANNOTATIONS_FILE, annotations)
			annotated_ids.discard(str(last["source_id"]))
			print(f"Undid annotation for '{last['term']}'.")

			undone_item = terms_by_id.get(str(last["source_id"]))
			if undone_item is not None:
				undone_sentences = _clean_candidate_sentences(undone_item.get("simple_explanation"))
				undone_score = compute_difficulty_score(undone_sentences)
				queue.insert(idx, (undone_score, undone_item, undone_sentences))
			continue

		if not choice.isdigit() or not (0 <= int(choice) < len(sentences)):
			print(f"Invalid input. Enter a number 0-{len(sentences) - 1}, 'u', or 'q'.")
			continue

		selected_index = int(choice)
		record = make_record(item, sentences, v7_index, v7_source, selected_index)
		annotations.append(record)
		write_jsonl_atomic(ANNOTATIONS_FILE, annotations)
		annotated_ids.add(str(source_id))
		idx += 1

	print(f"Total labeled: {len(annotations)}")


def run_review(annotations, args):
	if not annotations:
		print("No annotations to review yet.")
		return

	i = 0
	while i < len(annotations):
		record = annotations[i]
		print("-" * 60)
		print(f"Reviewing {i + 1} / {len(annotations)}")
		print()
		print(f"TERM: {record['term']}")
		print()
		print("Candidates:")
		for j, s in enumerate(record["candidates"]):
			print(f"[{j}] {s}")
		print()
		print(f"Your previous choice: [{record['selected_index']}]")
		if record.get("current_v7_index") is not None:
			print(f"V7 selected: [{record['current_v7_index']}]")
		print()

		try:
			choice = input("Press Enter to keep, type a new index to correct, or q to stop: ").strip().lower()
		except EOFError:
			break

		if choice == "q":
			break
		if choice == "":
			i += 1
			continue
		if not choice.isdigit() or not (0 <= int(choice) < len(record["candidates"])):
			print(f"Invalid input. Enter a number 0-{len(record['candidates']) - 1}, or press Enter, or 'q'.")
			continue

		new_index = int(choice)
		record["selected_index"] = new_index
		record["agrees_with_v7"] = (
			(record["current_v7_index"] == new_index) if record.get("current_v7_index") is not None else None
		)
		record["annotated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
		write_jsonl_atomic(ANNOTATIONS_FILE, annotations)
		print(f"Updated selection to [{new_index}].")
		i += 1


def main():
	parser = argparse.ArgumentParser(description="ClearMed short-explanation human annotation tool")
	parser.add_argument("--target", type=int, default=180, help="Target total labeled examples, shown in the progress line")
	parser.add_argument("--no-ai", action="store_true", help="Do not call the OpenAI V7 selector; show V7 choice as unavailable")
	parser.add_argument("--review", action="store_true", help="Review/correct already-labeled terms instead of labeling new ones")
	args = parser.parse_args()

	with open(JSON_FILE, "r", encoding="utf-8") as f:
		all_terms = json.load(f)["terms"]
	terms_by_id = {str(item.get("source_id")): item for item in all_terms}

	annotations = load_jsonl(ANNOTATIONS_FILE)
	annotated_ids = {str(r["source_id"]) for r in annotations}
	v7_cache = load_json(V7_CACHE_FILE, {})

	if args.review:
		run_review(annotations, args)
	else:
		run_annotation(all_terms, terms_by_id, annotations, annotated_ids, v7_cache, args)


if __name__ == "__main__":
	main()
