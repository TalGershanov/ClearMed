import json
import logging
import os
import re
import sqlite3
import sys
import time

import httpx
from bs4 import BeautifulSoup, Tag

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_FILE, HEBREW_JSON_FILE
from logic.term_detectors.hebrew import is_hebrew_char

logger = logging.getLogger("clearmed.data_preparation.scrape_infomed_to_json")

ENGLISH_LANG = "en"
HEBREW_LANG = "he"

DEFINITIONS_SITEMAP_URL = "https://www.infomed.co.il/content/sitemaps/definitions-sitemap.xml"
DEFINITIONS_URL_PREFIX = "https://www.infomed.co.il/definitions/"
DISEASES_SITEMAP_URL = "https://www.infomed.co.il/content/sitemaps/diseases-sitemap.xml"
DISEASES_URL_PREFIX = "https://www.infomed.co.il/diseases/"
REQUEST_DELAY_SECONDS = 0.3

# Hand-edit to e.g. 20 for a pilot run; None runs against every URL in the sitemap.
LIMIT = None

# Hand-edit to True to re-scrape concepts that already have Hebrew data (e.g.
# after changing _extract_body_text) -- otherwise already_scraped() skips
# them. Revert to False afterward so normal runs stay incremental-only.
FORCE_RESCRAPE = False


def already_scraped(connection, concept_id):
	row = connection.execute(
		"SELECT 1 FROM explanations WHERE concept_id = ? AND language_code = ?",
		(concept_id, HEBREW_LANG),
	).fetchone()
	return row is not None


def fetch_sitemap_urls(client, sitemap_url, url_prefix):
	response = client.get(sitemap_url, timeout=30)
	response.raise_for_status()
	urls = re.findall(re.escape(url_prefix) + r"[^<\s]+", response.text)
	logger.info("Found %d URL(s) in %s", len(urls), sitemap_url)
	return urls


_PAREN_GROUP_RE = re.compile(r"\(([^()]*)\)")


def _classify_names(text, hebrew_names, english_names):
	# Titles can carry either language in a parenthetical (e.g. a Hebrew
	# synonym in its own parens before the English one), so classify each
	# comma-separated piece by script rather than by its position in the title.
	for piece in text.split(","):
		piece = piece.strip()
		if not piece:
			continue
		is_hebrew = any(is_hebrew_char(ch) for ch in piece)
		(hebrew_names if is_hebrew else english_names).append(piece)


def _parse_title(title):
	hebrew_names, english_names = [], []
	primary = _PAREN_GROUP_RE.split(title, maxsplit=1)[0].strip()
	_classify_names(primary, hebrew_names, english_names)
	for paren_group in _PAREN_GROUP_RE.findall(title):
		_classify_names(paren_group, hebrew_names, english_names)
	return hebrew_names, english_names


def _extract_body_text(soup):
	container = soup.select_one("div.centeredContent.encyclopediaSection-bottom")
	if container is None:
		return ""
	for div in container.select("div.description"):
		if div.get("id") == "description":
			continue
		# The page's own template only marks off the intro section
		# structurally: an inserted photo separates it from every later
		# section (causes, types, treatment, etc.) -- there's no heading or
		# other marker. Walk every descendant in document order (not just
		# direct children -- some page templates nest the intro text and the
		# photo inside one shared wrapper element, so stopping at whichever
		# *child* contains an image would discard real intro text along with
		# it) and stop at the first actual <img>/<picture>/<source> node,
		# keeping only the text before it. A minority of older,
		# encyclopedia-sourced pages have no image anywhere in this div (bare
		# <br>-separated text) -- for those there's no safe place to cut, so
		# the full text is kept, unchanged from before.
		pieces = []
		for node in div.descendants:
			if isinstance(node, Tag):
				if node.name in ("img", "picture", "source"):
					break
				continue
			text = node.strip()
			if text:
				pieces.append(text)
		if pieces:
			return " ".join(pieces)
		return div.get_text(" ", strip=True)
	return ""


def parse_definition_page(html):
	soup = BeautifulSoup(html, "lxml")
	h1 = soup.find("h1")
	if h1 is None:
		return None
	hebrew_names, english_names = _parse_title(h1.get_text(strip=True))
	if not hebrew_names or not english_names:
		return None

	body_text = _extract_body_text(soup)
	if not body_text:
		return None

	return {"hebrew_names": hebrew_names, "english_names": english_names, "body_text": body_text}


def parse_disease_page(html):
	# Unlike /definitions/ pages, /diseases/ titles are Hebrew-only (e.g.
	# "אסטמה, קצרת" for asthma) -- no English name to parse out. english_names
	# is usually empty here; concept resolution instead falls back to
	# matching the page's URL slug (see find_matching_concept_by_slug).
	soup = BeautifulSoup(html, "lxml")
	h1 = soup.find("h1")
	if h1 is None:
		return None
	hebrew_names, english_names = _parse_title(h1.get_text(strip=True))
	if not hebrew_names:
		return None

	body_text = _extract_body_text(soup)
	if not body_text:
		return None

	return {"hebrew_names": hebrew_names, "english_names": english_names, "body_text": body_text}


def find_matching_concept(connection, english_names):
	# Exact (case-insensitive) name match only -- confirmed with the user:
	# a term with no match to an existing English concept is skipped
	# entirely, never given a synthesized id. Matches against every existing
	# English alias (term_aliases), not just each concept's primary
	# term_name -- a concept's synonyms (e.g. "Rheumatoid spondylitis" for
	# "Ankylosing Spondylitis") are legitimate match targets too, and 560 of
	# the 1017 English concepts have at least one alias beyond their
	# term_name that a term_name-only check would silently miss.
	for name in english_names:
		row = connection.execute(
			"""
			SELECT e.concept_id, e.short_explanation
			FROM term_aliases a
			JOIN explanations e ON e.concept_id = a.concept_id AND e.language_code = ?
			WHERE a.language_code = ? AND LOWER(a.alias_text) = LOWER(?)
			""",
			(ENGLISH_LANG, ENGLISH_LANG, name),
		).fetchone()
		if row is not None:
			return row[0], row[1]
	return None, None


def _slugify(name):
	slug = name.lower().strip()
	slug = re.sub(r"[^a-z0-9\s-]", "", slug)
	slug = re.sub(r"[\s-]+", "-", slug).strip("-")
	return slug


def find_matching_concept_by_slug(connection, slug):
	# /diseases/ pages give no explicit English name, so fall back to
	# comparing the page's own URL slug against a slugified form of every
	# existing English alias. A disease slug sometimes carries a
	# disambiguating suffix (e.g. "angina-pectoris" for "Angina",
	# "appendicitis-acute" for "Appendicitis"), so a prefix match counts too,
	# not just exact equality -- verified against real data before running
	# this at scale (175/810 previously-unmatched concepts confirmed this way).
	rows = connection.execute(
		"""
		SELECT DISTINCT a.alias_text, e.concept_id, e.short_explanation
		FROM term_aliases a
		JOIN explanations e ON e.concept_id = a.concept_id AND e.language_code = ?
		WHERE a.language_code = ?
		""",
		(ENGLISH_LANG, ENGLISH_LANG),
	).fetchall()
	# Row order from SQLite is not guaranteed, and a short generic alias
	# (e.g. "cell") can be a valid prefix match alongside a longer, more
	# specific one (e.g. "cell-therapy") for the same page slug -- take the
	# longest/most-specific matching alias rather than whichever row happens
	# to come first, so a scraped page can't get silently mis-attributed to
	# the wrong, less-specific concept.
	best_match = None
	best_len = -1
	for alias_text, concept_id, short_explanation in rows:
		candidate = _slugify(alias_text)
		if candidate and (slug == candidate or slug.startswith(candidate + "-")):
			if len(candidate) > best_len:
				best_match = (concept_id, short_explanation)
				best_len = len(candidate)
	return best_match if best_match is not None else (None, None)


def _scrape_pages(connection, client, urls, parse_page, resolve_concept):
	"""Shared fetch/parse/match loop for both infomed sections. Returns the
	list of matched term dicts (ready to write to HEBREW_JSON_FILE) plus
	summary stats. `resolve_concept(connection, parsed, url)` must return
	(concept_id, short_explanation)."""
	collected = []
	fetched = matched = no_match = no_body = failed = 0
	for index, url in enumerate(urls, start=1):
		if index % 100 == 0:
			logger.info("Processed %d/%d page(s)", index, len(urls))
		try:
			response = client.get(url, timeout=30)
			response.raise_for_status()
			fetched += 1
		except httpx.HTTPError:
			logger.warning("Failed to fetch %s", url, exc_info=True)
			failed += 1
			time.sleep(REQUEST_DELAY_SECONDS)
			continue

		parsed = parse_page(response.text)
		if parsed is None:
			no_body += 1
			time.sleep(REQUEST_DELAY_SECONDS)
			continue

		concept_id, short_explanation = resolve_concept(connection, parsed, url)
		if concept_id is None:
			no_match += 1
			time.sleep(REQUEST_DELAY_SECONDS)
			continue

		if FORCE_RESCRAPE or not already_scraped(connection, concept_id):
			collected.append({
				"concept_id": concept_id,
				"hebrew_names": parsed["hebrew_names"],
				"english_names": parsed["english_names"],
				"simple_explanation": parsed["body_text"],
				"short_explanation": short_explanation,
			})
		matched += 1
		time.sleep(REQUEST_DELAY_SECONDS)

	stats = {"fetched": fetched, "matched": matched, "no_match": no_match, "no_body": no_body, "failed": failed}
	return collected, stats


def _print_summary(label, stats):
	print(f"--- {label} ---")
	print(f"Pages fetched: {stats['fetched']}")
	print(f"Matched: {stats['matched']}")
	print(f"Skipped (no matching English concept): {stats['no_match']}")
	print(f"Skipped (no parseable name/body): {stats['no_body']}")
	print(f"Failed to fetch: {stats['failed']}")


def scrape_definitions(connection, client):
	urls = fetch_sitemap_urls(client, DEFINITIONS_SITEMAP_URL, DEFINITIONS_URL_PREFIX)
	if LIMIT is not None:
		urls = urls[:LIMIT]

	def resolve(conn, parsed, url):
		return find_matching_concept(conn, parsed["english_names"])

	collected, stats = _scrape_pages(connection, client, urls, parse_definition_page, resolve)
	_print_summary("definitions", stats)
	return collected


def scrape_diseases(connection, client):
	urls = fetch_sitemap_urls(client, DISEASES_SITEMAP_URL, DISEASES_URL_PREFIX)
	if LIMIT is not None:
		urls = urls[:LIMIT]

	def resolve(conn, parsed, url):
		# Try any explicit English name first (rare on this section, but
		# possible), then fall back to slug matching.
		if parsed["english_names"]:
			concept_id, short_explanation = find_matching_concept(conn, parsed["english_names"])
			if concept_id is not None:
				return concept_id, short_explanation
		slug = url.rstrip("/").rsplit("/", 1)[-1]
		return find_matching_concept_by_slug(conn, slug)

	collected, stats = _scrape_pages(connection, client, urls, parse_disease_page, resolve)
	_print_summary("diseases", stats)
	return collected


def _load_existing_terms():
	# already_scraped() filters out concepts the live DB already has 'he'
	# data for, so a re-scrape (e.g. to pick up new infomed content, or a
	# small LIMIT smoke test) naturally returns only NEW terms. Merge onto
	# whatever's already on disk instead of overwriting it, or a partial
	# re-scrape would silently destroy previously-captured entries.
	try:
		with open(HEBREW_JSON_FILE, "r", encoding="utf-8") as f:
			return json.load(f)["terms"]
	except FileNotFoundError:
		return []


def scrape_to_json():
	connection = sqlite3.connect(DB_FILE)

	with httpx.Client(headers={"User-Agent": "Mozilla/5.0 (clearmed-scraper)"}, follow_redirects=True) as client:
		new_terms = scrape_definitions(connection, client)
		seen_concept_ids = {t["concept_id"] for t in new_terms}
		for term in scrape_diseases(connection, client):
			if term["concept_id"] not in seen_concept_ids:
				new_terms.append(term)
				seen_concept_ids.add(term["concept_id"])

	connection.close()

	terms_by_concept_id = {t["concept_id"]: t for t in _load_existing_terms()}
	added = updated = 0
	for term in new_terms:
		if term["concept_id"] in terms_by_concept_id:
			updated += 1
		else:
			added += 1
		# A freshly-collected term always wins over whatever's already on disk
		# for the same concept_id -- during a normal (non-forced) run this
		# never actually overwrites anything, since already_scraped() already
		# keeps already-done concepts out of new_terms; it only matters when
		# FORCE_RESCRAPE deliberately re-collects them.
		terms_by_concept_id[term["concept_id"]] = term

	terms = list(terms_by_concept_id.values())
	with open(HEBREW_JSON_FILE, "w", encoding="utf-8") as f:
		json.dump({"terms": terms}, f, ensure_ascii=False, indent=2)
	print(f"Added {added} new term(s), updated {updated}; {HEBREW_JSON_FILE} now has {len(terms)} total")


if __name__ == "__main__":
	from log_config import setup_logging
	setup_logging()
	scrape_to_json()
