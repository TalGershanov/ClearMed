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

### Planned

* Hospital system simulation
* Multiple language support
* Upload a document by taking a picture on mobile
* AI fine-tuning to reword and shorten the explanation paragraphs

---

## Architecture

The architecture below shows both the **current project** and the features planned
for the future.

```mermaid
flowchart TD
    User["User"]

    ClearMed["ClearMed"]

    WebWizard["Web Wizard<br/>CURRENT"]

    Upload["Upload Document<br/>CURRENT"]
    SelectTerms["Select Terms<br/>CURRENT"]
    ReviewSummary["Review Summary<br/>CURRENT"]
    Export["Export / Print<br/>CURRENT"]

    CameraCapture["Camera Capture<br/>PLANNED"]

    FastAPI["FastAPI App<br/>CURRENT"]
    TermDetector["Term Detector<br/>CURRENT"]
    TermTrie["Term Trie<br/>CURRENT"]
    Translator["Translator<br/>CURRENT"]
    DAL["DAL<br/>CURRENT"]
    DB["clearmed.db<br/>CURRENT"]

    OfflineBuild["server_init Build<br/>CURRENT"]
    XML["health_topics.xml<br/>CURRENT"]
    GPT["GPT-4o-mini<br/>CURRENT"]

    AIRewriter["AI Rewriter<br/>PLANNED"]
    MultiLang["Multi-language Support<br/>PLANNED"]
    HospitalSim["Hospital System Simulation<br/>PLANNED"]

    User --> ClearMed

    ClearMed --> WebWizard
    ClearMed --> FastAPI

    WebWizard --> Upload
    Upload --> SelectTerms
    SelectTerms --> ReviewSummary
    ReviewSummary --> Export

    Upload -.-> CameraCapture

    SelectTerms --> FastAPI
    ReviewSummary --> FastAPI

    FastAPI --> TermDetector
    TermDetector --> TermTrie
    FastAPI --> Translator

    TermDetector --> DAL
    Translator --> DAL
    DAL --> DB

    OfflineBuild --> XML
    OfflineBuild --> GPT
    OfflineBuild --> DB

    Translator -.-> AIRewriter
    ClearMed -.-> MultiLang
    ClearMed -.-> HospitalSim
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
├── server_init/       ← offline: builds clearmed.db from health_topics.xml
├── static/            ← frontend wizard (upload → select → review → export)
│
├── health_topics.xml  ← MedlinePlus source data
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
to `main`: it SSHs in, `git pull`s, and restarts `uvicorn`.

---

## Authors

**Tal Gershanov**

GitHub: https://github.com/TalGershanov

**Yuval Bashan**

GitHub: https://github.com/YuvalBashan
