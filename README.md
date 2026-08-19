# ClearMed

ClearMed detects medical terms in an uploaded document (`.txt` or `.pdf`) and explains
them in patient-friendly language, sourced from [MedlinePlus](https://medlineplus.gov/),
a health information service of the U.S. National Library of Medicine (NIH).

## Architecture

- **`server/`** — the FastAPI app (`api.py`) and its routes.
- **`logic/`** — medical term detection (trie-based matching) and translation of a
  document's text using the terms the patient approved.
- **`DAL/`** — the data access layer, reading term data from `clearmed.db` (SQLite).
- **`server_init/`** — one-time offline tooling that builds `clearmed.db`; not run by
  the server itself.
- **`static/`** — the frontend (a 4-step wizard: upload → select terms → review
  summary → export/print). Served directly by FastAPI as static files, mounted on
  the same origin as the API, so no CORS setup is needed.
- **`openmrs/`** — server-to-server integration with the OpenMRS REST API
  (fetch patient data, post observations). See [`openmrs/README.md`](openmrs/README.md)
  for env vars and security/architecture best practices.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill in the values you need. `OPENAI_API_KEY`
is only needed for the database-build step below, not for running the server
itself. `OPENMRS_*` is only needed for the `/openmrs/*` endpoints — see
[`openmrs/README.md`](openmrs/README.md).

## Building the database

```bash
python server_init/bootstrap.py
```

This parses `health_topics.xml` into `output/clearmed_terms_english.json`, then builds
`clearmed.db` from that JSON, using GPT-4o-mini to pick each term's patient-facing
short explanation from the source text.

This is slow (roughly one OpenAI call per term, ~1000 terms) and **destructive** — it
drops and rebuilds the `medical_terms` table from scratch. If you're rebuilding an
existing `clearmed.db` you care about, back it up first:
```bash
cp clearmed.db clearmed.db.bak
```

## Running the API

```bash
uvicorn server.api:app --reload
```

Open `http://127.0.0.1:8000/`.

## API endpoints

| Method | Path                       | Purpose                                                              |
| ------ | -------------------------- | --------------------------------------------------------------------- |
| POST   | `/analyse`                 | Detect medical terms in `{text}`, return them with explanations.      |
| POST   | `/translate`               | Rewrite `{text}` using only the approved terms in `{ui_selection}`.   |
| GET    | `/openmrs/patients/{uuid}` | Fetch a patient by UUID from OpenMRS.                                  |
| POST   | `/openmrs/observations`    | Create a new observation in OpenMRS.                                   |
| GET    | `/openmrs/patients/{uuid}/notes` | List a patient's clinical notes. See [`openmrs/README.md`](openmrs/README.md). |

## Deployment

`.github/workflows/deploy.yml` automatically deploys to an EC2 instance on every push
to `main`: it SSHs in, `git pull`s, and restarts `uvicorn`. It does **not** rebuild
`clearmed.db` — if you've regenerated it locally (see above), copy it over manually:
```bash
scp -i <your-key>.pem clearmed.db ec2-user@<host>:~/clearmed/
```

The workflow requires these repo secrets to be set (Settings → Secrets and variables →
Actions):
- `EC2_HOST` — the instance's address
- `EC2_USER` — the SSH user (e.g. `ec2-user`)
- `EC2_SSH_KEY` — the private key for that user
