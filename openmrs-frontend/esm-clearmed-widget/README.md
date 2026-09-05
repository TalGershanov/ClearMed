# esm-clearmed-widget

OpenMRS 3.x microfrontend widget that adds a "ClearMed" tab to the patient
chart dashboard. Clicking it lets a clinician pick one of the patient's
OpenMRS clinical notes, then runs ClearMed's term-detection/translation flow
on it — skipping the file-upload step the standalone `static/` wizard uses,
since the text comes from OpenMRS instead. All ClearMed logic (term
detection, translation) is delegated to the external ClearMed FastAPI
backend; this module only talks to OpenMRS indirectly, through that backend.

## Dashboard tab vs. a `launchWorkspace` panel

The tab is implemented as a `createDashboard`-registered chart dashboard
(`src/dashboard.meta.ts`, `src/index.ts`, `src/routes.json`) rather than a
`launchWorkspace` side panel. This was a deliberate choice: OpenMRS's
workspace registration API had a breaking rename (`workspaces` →
`workspaces2`) between `openmrs-esm-patient-chart` versions, and which
generation a given OpenMRS instance runs isn't knowable from this repo. The
dashboard-tab/`createDashboard` mechanism, by contrast, is unchanged across
every `openmrs-esm-patient-chart` version checked (`v10.0.0`–`v12.3.4`), so
it was picked to avoid reproducing the same class of bug this fixed (see
"Known instance-side issues" below). If a later maintainer confirms which
workspace-API generation a target instance runs, this could be revisited as
a real side-panel workspace.

Note also that `createDashboard` is imported from `@openmrs/esm-styleguide`,
not `createDashboardLink` from `@openmrs/esm-patient-common-lib` — the two
are equivalent, but `esm-patient-common-lib` ships raw, uncompiled
TypeScript source with no `dist/` build (fine when consumed inside the real
`openmrs-esm-patient-chart` monorepo, where a shared pipeline compiles it,
but unbuildable by a standalone project like this one using the default
`openmrs`-CLI rspack config, which excludes `node_modules` from its
TS/JSX transform). `esm-styleguide` ships a compiled `dist/`, so it doesn't
have this problem.

## Known instance-side issues

If the browser console shows
`TypeError: getLocaleDisplayName is not a function`, this is **not**
ClearMed code — `getLocaleDisplayName` lives in `openmrs-esm-core`'s
`@openmrs/esm-framework` (used only by `@openmrs/esm-primary-navigation-app`'s
language switcher) and was, as of this writing, still an unreleased/unconsumed
changeset on `esm-core`'s `main` branch (present only in the `next`
prerelease, not the stable `10.0.0` release). Seeing this error means the
OpenMRS instance is running an `esm-primary-navigation-app` build that's
ahead of the `@openmrs/esm-framework` version it's actually paired with —
report it to whoever manages that OpenMRS instance; the fix is to align
those two packages' versions, not something this repo can change.

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
ClearMed's CORS allowlist (see `../../openmrs/README.md`) so local testing
works out of the box; a production deployment needs its real OpenMRS domain
set as `OPENMRS_ORIGIN` in the backend's `.env` instead. The backend also
needs `OPENMRS_NOTE_CONCEPT_UUID` set to your OpenMRS instance's concept UUID
for clinical notes, or the note picker will show a "not configured" message
(see `../../openmrs/README.md`).

## Building

```bash
npm run typescript   # type-check
npm run build         # rspack --mode production, produces dist/esm-clearmed-widget-app.js
```
