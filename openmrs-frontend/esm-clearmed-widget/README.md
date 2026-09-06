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

### Pinned to a moving target: `openmrs`/`esm-framework`/`esm-styleguide`

These three are pinned in `package.json` to an exact **prerelease** version
(currently `10.0.1-pre.5324`, npm's `next` dist-tag) instead of the normal
`^10.0.0` (`latest`) range. This is a workaround for the same class of issue
as the `getLocaleDisplayName` one above, just worse: `dev3.openmrs.org` (the
demo server `npm start --backend` proxies to, and the one its import map
always resolves against — `o3.openmrs.org`'s own import map 403s the CLI's
fetch and silently falls back to `dev3`'s) serves core apps (nav bar, login,
help menu, ...) built from whatever `next`-tagged build OpenMRS most recently
pushed. If our pinned version falls behind that, the local `openmrs`
CLI's app shell doesn't speak the same module-loading protocol (older builds
use SystemJS, `next` has moved to Webpack Module Federation) and **every**
core app dies with `does not refer to a federated module`, leaving a
completely blank page — nothing OpenMRS renders (including the login
screen) survives.

**If you see that error, or the dev shell is blank:**

1. Open the browser console. A failing module's script URL contains the
   version OpenMRS is actually running, e.g.
   `.../10.0.1-pre.5330/openmrs-esm-help-menu-app.js`.
2. Run `npm run check-openmrs-version` (wraps
   `scripts/check-openmrs-version.sh`) — it compares that number against
   what's pinned in `package.json` and, if they differ, rewrites the pin for
   you automatically.
3. Follow the script's printed next steps: `npm install` (see the EMFILE
   warning below — do **not** delete `package-lock.json` first), then fully
   stop and restart `npm start` (see "must be restarted" warning below).

Because this chases a public demo server's bleeding-edge builds, it *will*
drift again — there's no permanent fix short of testing against a
version-locked local OpenMRS instance instead (e.g. the official
`openmrs-reference-application-3` Docker distro) rather than `dev3`/`o3`.

### EMFILE: too many open files

If `npm start` crashes with `Error: EMFILE: too many open files, watch`,
resist the urge to just raise `ulimit -n` — that treats a symptom, not the
cause, and can require an unreasonably high limit to "fix". The real cause
we hit: running `rm -rf node_modules package-lock.json && npm install`
throws away this project's **committed, already-deduplicated**
`package-lock.json` and lets npm re-resolve the whole dependency graph from
just the loose `^` ranges in `package.json` — with no lockfile to anchor it,
the fresh resolution can dedupe far worse, inflating `node_modules` enough
that the dev server's file watcher (`chokidar`) exhausts even a
generously-raised file-descriptor limit.

Fix: restore the tracked lockfile and do a clean, deterministic install from
it instead of a fresh resolve:

```bash
git checkout -- package-lock.json
rm -rf node_modules dist
npm ci
```

When you *do* need to change a dependency version on purpose (e.g. the
prerelease pin above), use plain `npm install` afterwards — never delete
`package-lock.json` first — so npm updates only what actually changed
instead of re-resolving everything from scratch.

### A running dev server must be restarted after any dependency change

`npm start`'s Module Federation "shared module" versions are computed once,
at startup, from `package.json`/`node_modules` at that instant. Editing
`src/` hot-reloads live, but changing dependencies (`npm install`, `npm ci`,
editing `package.json`) does not — a server left running will keep using its
original, now-stale versions and throw confusing
`Cannot find module '@openmrs/esm-framework'`-style errors that look like a
broken install even though `npm ls` shows everything correctly resolved.
Always fully stop (`Ctrl+C`, or `lsof -ti:8080,8081 | xargs kill` if the
terminal's gone) and restart `npm start` after any dependency change.

## Running it standalone

```bash
npm install
npm start
```

`npm start` runs `openmrs develop`, which spins up the standard OpenMRS 3.x
dev shell (default `http://localhost:8080`) against a backend OpenMRS
instance, e.g.:

```bash
npm start -- --backend https://dev3.openmrs.org --routes routes.registry.fixed.json
```

(`--routes routes.registry.fixed.json` works around `o3.openmrs.org`'s
routes-registry endpoint also 403ing the CLI's fetch — see "Pinned to a
moving target" above for why `dev3` is used as the backend either way.)

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
