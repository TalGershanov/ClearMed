# ClearMed

## Rebuilding the database
From the repo root, run:
`python pipeline/build_all.py`

This parses `health_topics.xml` into `output/clearmed_terms_english.json`, then builds
`clearmed.db` from that JSON.

## Running the API
`uvicorn api:app --reload`
