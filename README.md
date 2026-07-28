# ClearMed

## Rebuilding the database
From the repo root, run:
`python server_init/bootstrap.py`

This parses `health_topics.xml` into `output/clearmed_terms_english.json`, then builds
`clearmed.db` from that JSON.

## Running the API
`uvicorn server.api:app --reload`
