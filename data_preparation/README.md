# Data Preparation

Scripts that turn raw sources into the JSON files `server_init/` builds `clearmed.db` from.
These are run rarely, only to refresh the source data — the current JSON output already
lives in `server_init/data/` and doesn't need to be regenerated for a normal `bootstrap.py` run.

- `convert_medline_xml_to_json.py` — parses `health_topics.xml` (a MedlinePlus Health Topic
  XML dump, place it in this folder) into `server_init/data/clearmed_terms_english.json`.
- `scrape_infomed_to_json.py` — scrapes infomed.co.il for Hebrew content, matching each page
  to an existing English concept in `clearmed.db`, and merges the result into
  `server_init/data/clearmed_terms_hebrew.json`. Incremental: concepts that already have
  Hebrew data are skipped unless `FORCE_RESCRAPE` is set at the top of the file.

Both write directly to the JSON files `server_init/` reads — after rerunning either script,
`python server_init/bootstrap.py` will pick up the refreshed data on its next run.
