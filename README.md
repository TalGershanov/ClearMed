# ClearMed

ClearMed detects medical terms in an uploaded document (`.txt` or `.pdf`) and explains
them in patient-friendly language, sourced from [MedlinePlus](https://medlineplus.gov/),
a health information service of the U.S. National Library of Medicine (NIH).

---

## Features

### Currently available

* Detect medical terms in an uploaded document via a trie-based matcher
* Patient-friendly term explanations sourced from MedlinePlus (NIH)
* Interactive 4-step web wizard: upload → select terms → review summary → export/print
* Rewrite/annotate document text using only the terms the patient approved
* Offline database build pipeline from MedlinePlus XML, using GPT-4o-mini to generate
  each term's patient-facing explanation
* Hospital system simulation
* Upload a document by taking a picture on mobile
  
### Planned

* Multiple language support
* AI fine-tuning to reword and shorten the explanation paragraphs
* tone adjusting 

---

## Architecture

The architecture below shows both the **current project** and the features planned
for the future.

```mermaid
flowchart TD
    User["User"]
    Wizard["Web Wizard<br/>static/<br/>CURRENT"]

    Upload["1. Upload Document<br/>.txt / .pdf, read in-browser<br/>CURRENT"]
    Select["2. Select Terms<br/>CURRENT"]
    Summary["3. Review Summary<br/>editable<br/>CURRENT"]
    Export["4. Export / Print<br/>client-side PDF / print<br/>CURRENT"]
    Camera["Camera Capture<br/>CURRENT"]

    API["FastAPI App<br/>server/api.py<br/>CURRENT"]
    Detector["Term Detector<br/>logic/medical_term_detector.py<br/>CURRENT"]
    Trie["Term Trie, in memory<br/>logic/medical_term_trie.py<br/>CURRENT"]
    Translator["Translator<br/>logic/translator.py<br/>CURRENT"]
    DAL["DAL<br/>DAL/db.py<br/>CURRENT"]
    DB[("clearmed.db<br/>SQLite<br/>CURRENT")]

    Bootstrap["server_init Bootstrap<br/>offline, not run by server<br/>CURRENT"]
    XML["health_topics.xml<br/>CURRENT"]
    GPT["OpenAI GPT-4o-mini<br/>CURRENT"]

    AIRewriter["AI Rewriter<br/>PLANNED"]
    MultiLang["Multi-language Support<br/>PLANNED"]
    HospitalSim["Hospital System Simulation<br/>CURRENT"]

    User --> Wizard
    Wizard --> Upload
    Upload -.-> Camera

    Upload -- "POST /analyse" --> API
    API -- "detected terms" --> Select
    Select -- "POST /translate" --> API
    API -- "translated text" --> Summary
    Summary --> Export

    API --> Detector
    API --> Translator

    Detector -- "trie.find_terms()" --> Trie
    Detector -- "get_term_details()" --> DAL
    Translator -- "fetch_explanations()" --> DAL
    DAL --> DB

    API -- "startup: init_trie()" --> Trie
    Trie -- "build_trie_from_db()" --> DAL

    Bootstrap --> XML
    Bootstrap --> GPT
    Bootstrap --> DB

    Translator -.-> AIRewriter
    Wizard -.-> MultiLang
    Wizard -.-> HospitalSim
```

**CURRENT** = already implemented

**PLANNED** = planned for a future version

---

## Project Structure

```text
ClearMed/
│
├── server/            ← FastAPI app and routes (api.py)
├── logic/             ← term detection (trie) + translation
├── DAL/               ← data access layer over clearmed.db (SQLite)
├── data_preparation/  ← offline, rarely run: scrapes/converts raw sources into JSON
│                        (health_topics.xml lives here)
├── server_init/       ← offline: builds clearmed.db from server_init/data/*.json
├── static/            ← frontend wizard (upload → select → review → export)
│
├── clearmed.db         ← SQLite term database
├── requirements.txt
└── README.md
```

---

## Website

https://clearmed.duckdns.org

---

## API endpoints

| Method | Path          | Purpose                                                            |
| ------ | ------------- | ------------------------------------------------------------------- |
| POST   | `/analyse`    | Detect medical terms in `{text}`, return them with explanations.    |
| POST   | `/translate`  | Rewrite `{text}` using only the approved terms in `{ui_selection}`. |

---

## Deployment

`.github/workflows/deploy.yml` automatically deploys to an EC2 instance on every push
to `main`: it SSHs in, `git pull`s, builds the `appFrontend/` React app, installs
Python deps, runs pending `alembic` migrations, and restarts `uvicorn` -- failing the
deploy loudly (with the last 50 lines of `output.log`) if the server doesn't come back
up, instead of leaving a crashed process behind a still-"successful" nginx proxy.

### One-time production box setup

The automated deploy assumes the box already has this in place. On a fresh EC2
instance (or after replacing the current one), set these up once by hand first:

* **`~/clearmed/.env`** -- not tracked in git. Copy `.env.example` and fill in real
  values, at minimum `JWT_SECRET_KEY` (`python -c "import secrets; print(secrets.token_hex(32))"`)
  and `ENVIRONMENT=production`. A missing `JWT_SECRET_KEY` crashes the *entire* app at
  import time (not just the patient-app routes), which is a common cause of a
  site-wide 502.
* **Node.js + pnpm**, for building `appFrontend/`. Amazon Linux 2023's `dnf` Node
  package is too old for this project's Vite version; install via
  [nvm](https://github.com/nvm-sh/nvm) instead: `nvm install 20 && npm install -g pnpm`.
* **Docker + the Compose plugin**, for the patient-app's Postgres database
  (`docker-compose.yml`). AL2023 doesn't package `docker-compose-plugin`; install the
  plugin binary directly per
  [Docker's docs](https://docs.docker.com/compose/install/linux/#install-the-plugin-manually).
  Then `docker compose up -d` once to create the `clearmed_postgres` container (the
  deploy script does not start it for you).
* **nginx**: `/etc/nginx/conf.d/clearmed.conf` needs a `location /app/` block serving
  `appFrontend/dist/` (via `alias`, with `try_files $uri $uri/ /app/index.html` for
  client-side routing), alongside the existing `location /` proxy to
  `http://127.0.0.1:8000`. Confirm the nginx worker user can traverse into
  `~/clearmed` (`sudo -u nginx stat ~/clearmed/appFrontend/dist/index.html`).

Once those are in place, every subsequent `git push` to `main` redeploys both the
API and the frontend, and applies any new `alembic` migrations, without manual steps.

---

## Try the OpenMRS widget

An OpenMRS 3.x microfrontend widget (`openmrs-frontend/esm-clearmed-widget/`)
adds a "ClearMed" tab to the patient chart, calling the already-deployed
backend above — no database build or local ClearMed server needed.

```bash
cd openmrs-frontend/esm-clearmed-widget
npm install
```

`dev3.openmrs.org`'s live `routes.registry.json` endpoint currently returns
its app list wrapped one level too deep (a confirmed bug on that server, not
this repo) — work around it once per session:

```bash
curl -s "https://dev3.openmrs.org/openmrs/spa/routes.registry.json" \
  | python3 -c "import json,sys; json.dump(json.load(sys.stdin)['routes'], open('routes.registry.fixed.json','w'))"
```

Then start the dev shell:

```bash
npm start -- --backend https://dev3.openmrs.org --routes routes.registry.fixed.json
```

Open the printed URL (e.g. `http://localhost:8080/openmrs/spa`), log in with
the `dev3.openmrs.org` demo credentials (`admin` / `Admin123`), open any
patient's chart, and click the **ClearMed** tab.

---

## Authors

**Tal Gershanov**

GitHub: https://github.com/TalGershanov

**Yuval Bashan**

GitHub: https://github.com/YuvalBashan
