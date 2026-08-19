# OpenMRS integration

Server-to-server integration with an OpenMRS instance's REST API: ClearMed
fetches patient data, does its own processing, and writes observations back.
Authenticates with HTTP Basic Auth on every request.

## Env vars

| Variable                  | Purpose                                              |
| -------------------------- | ----------------------------------------------------- |
| `OPENMRS_BASE_URL`         | e.g. `https://dev3.openmrs.org/openmrs` (no trailing slash) |
| `OPENMRS_USERNAME`         | OpenMRS service account username                     |
| `OPENMRS_PASSWORD`         | OpenMRS service account password                     |
| `OPENMRS_TIMEOUT_SECONDS`  | Per-request timeout, default `10`                    |
| `OPENMRS_ORIGIN`           | The OpenMRS domain allowed to call `/openmrs/*` cross-origin (CORS) |

See `.env.example` at the repo root. `/openmrs/*` is mounted as its own
sub-app in `server/api.py` with its own `CORSMiddleware`, so this allowlist
applies only to those endpoints, not to `/analyse`/`/translate`/static — and
it stays a closed allowlist (never a wildcard) on purpose (see below).

## Endpoints

| Method | Path                          | Purpose                                    |
| ------ | ----------------------------- | ------------------------------------------- |
| GET    | `/openmrs/patients/{uuid}`    | Fetch a patient by UUID from OpenMRS.       |
| POST   | `/openmrs/observations`       | Create a new observation in OpenMRS.        |

## Security & architecture best practices

- **Credentials**: only via env vars (or a secrets manager like AWS Secrets
  Manager in production) — never committed to git. `.env` is already
  gitignored; `.env.example` documents the shape without real secrets.
- **Least privilege**: use a dedicated OpenMRS service account scoped to
  only the REST resources ClearMed actually needs, not `admin`.
- **HTTPS only** to the OpenMRS instance.
- **CORS is a closed allowlist, never a wildcard, and scoped to `/openmrs/*`
  only.** `/openmrs/patients/*` and `/openmrs/observations` let a browser
  trigger reads/writes against real patient records, so they're mounted as
  their own sub-app in `server/api.py` with `allow_origins` restricted to
  the trusted OpenMRS origin(s) (`OPENMRS_ORIGIN`, plus `localhost:8080` for
  local dev) — the rest of the API (`/analyse`, `/translate`) isn't affected
  by this policy at all.
- **Network exposure**: restrict with VPC/security groups or IP
  allowlisting between the AWS server and the OpenMRS instance where
  possible, on top of the CORS/auth layers.
- **Idempotency**: retries on the observation POST can create duplicate
  obs records in OpenMRS — consider a client-supplied idempotency key or a
  dedupe check before writing.
- **Server-side validation**: validate concept UUID format and value
  type/range in ClearMed before forwarding to OpenMRS — don't trust the
  caller (including the microfrontend) to have already done this.
- **Audit logging**: every write ClearMed makes to OpenMRS is logged (see
  the `clearmed.openmrs.*` logger hierarchy) — who/what/when.
- **Concept UUIDs are instance-specific.** The same concept (e.g.
  "Weight (kg)") is not guaranteed to share a UUID across OpenMRS
  installations unless both are seeded from the same dictionary (e.g.
  CIEL). Never hardcode a concept UUID as a magic constant — treat it as
  configuration, same as `clearmedApiBaseUrl` in the microfrontend's
  config schema.
- **Graceful degradation**: if OpenMRS is unreachable, `/openmrs/*` returns
  `503` with a clear message. OpenMRS is a bolt-on dependency — `/analyse`
  and `/translate` must keep working regardless of its availability.
