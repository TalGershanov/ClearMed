# esm-clearmed-widget

OpenMRS 3.x microfrontend widget that sits in the patient chart and delegates
all logic to the external ClearMed FastAPI backend. This module is
standalone boilerplate — it isn't wired into any build in this repo, and is
meant as a starting point to import into a real OpenMRS frontend deployment.

## Running it standalone

```bash
npm install
npm start
```

`npm start` runs `openmrs develop`, which spins up the standard OpenMRS 3.x
dev shell (default `http://localhost:8080`) against a backend OpenMRS
instance, e.g.:

```bash
npm start -- --backend https://dev3.openmrs.org
```

Point `clearmedApiBaseUrl` (via the OpenMRS admin configuration UI, or a
local config override) at a running ClearMed API — e.g. `http://localhost:8000`
if you're running it locally with `uvicorn server.api:app --reload` from the
repo root.

The local dev-shell origin (`http://localhost:8080`) is already in
ClearMed's hardcoded CORS allowlist (see `../../openmrs/README.md`) so local
testing works out of the box; a production deployment needs its real
OpenMRS domain added to the `OPENMRS_ORIGIN` constant in the backend's
`config.py` instead.

## Building

```bash
npm run typescript   # type-check
npm run build         # rspack --mode production, produces dist/esm-clearmed-widget-app.js
```
