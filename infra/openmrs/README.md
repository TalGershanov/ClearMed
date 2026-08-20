# Self-hosted OpenMRS (EC2 + Docker Compose + HTTPS)

Why this exists: `o3.openmrs.org` (the public OpenMRS instance ClearMed was
testing against) sits behind a Cloudflare bot-challenge that 403s any
non-browser client, including ClearMed's `httpx`-based backend
(`openmrs/client.py`). That's Cloudflare WAF config on infrastructure we
don't control — not fixable from our side. So we self-host our own OpenMRS
instance instead, on a dedicated EC2 box we fully control.

This runs the official [O3 Reference
Application](https://github.com/openmrs/openmrs-distro-referenceapplication)
via its own Docker Compose files — we don't vendor those files here, we just
provision the box and point it at the correct env vars. Its `docker-compose.ssl.yml`
overlay already handles real Let's Encrypt certificates end-to-end (issuance
+ auto-renewal every 12h), so there's no separate nginx/Caddy config to
maintain in this repo.

No ClearMed backend or frontend code changes are needed for this — see
"After this is up" below for the (separate, later) steps to actually point
ClearMed at it.

No Elastic IP is used here — EIPs are billed once they're not attached to a
running instance, and this instance doesn't need a static address: DuckDNS
plus a small auto-updater running on the box (installed in step 3) keeps
`clearmed-openmrs.duckdns.org` pointed at whatever public IP the instance
currently has, even after a stop/start cycle.

## 1. Provision the instance

Requires the AWS CLI configured with your own credentials (`aws configure`).
Creates a `t3.medium` Ubuntu 22.04 instance and a security group open on 22
(your IP only), 80, and 443.

```bash
AWS_REGION=<same region as the existing ClearMed backend instance> \
KEY_NAME=<an existing EC2 key pair name in that region> \
ADMIN_CIDR=$(curl -s ifconfig.me)/32 \
./infra/openmrs/provision-instance.sh
```

Note the public IP it prints at the end (only needed for the initial SSH —
DNS is handled automatically from step 3 onward).

## 2. Get a DuckDNS token

Log into https://www.duckdns.org, create the `clearmed-openmrs` subdomain if
it doesn't exist yet, and copy your account token from the dashboard. You
don't need to set the IP by hand — the updater installed in step 3 does that
on every boot.

## 3. Copy the deploy files to the instance

```bash
cp infra/openmrs/.env.production.example infra/openmrs/.env.production
# edit .env.production: fill in real DB passwords (openssl rand -base64 24),
# confirm CERT_WEB_DOMAINS/CERT_CONTACT_EMAIL, pin TAG to the latest release.

cp infra/openmrs/duckdns.env.example infra/openmrs/duckdns.env
# edit duckdns.env: paste in your real DuckDNS token from step 2.

scp -i <your-key>.pem infra/openmrs/setup-host.sh infra/openmrs/duckdns-update.sh \
  infra/openmrs/.env.production infra/openmrs/duckdns.env \
  ubuntu@<public-ip>:~/
```

## 4. Run the bootstrap script on the instance

```bash
ssh -i <your-key>.pem ubuntu@<public-ip>
./setup-host.sh
```

This installs Docker, sets up a systemd timer that updates DuckDNS on every
boot (and every 5 minutes as a safety net) and runs it once immediately, then
clones `openmrs-distro-referenceapplication` at a pinned tag, drops your
`.env.production` in as its `.env`, and runs `docker compose up -d`. First
boot takes several minutes (DB init + Initializer seeding the
reference-application demo config).

The DuckDNS update runs *before* Docker Compose starts, so the domain
already resolves correctly by the time certbot requests its Let's Encrypt
certificate.

Consider setting `SSL_STAGING=true` in `.env.production` for the very first
run to confirm the ACME flow works without burning Let's Encrypt's
production rate limits, then remove it and re-run `docker compose up -d` to
get a real trusted cert.

## Verification

- `sudo docker compose ps` (from `~/openmrs-distro-referenceapplication` on
  the host) shows `gateway`, `frontend`, `backend`, `db`, `certbot` all
  running/healthy.
- `curl -vI https://clearmed-openmrs.duckdns.org/openmrs/spa` returns
  `200`, and the certificate issuer is Let's Encrypt (not self-signed —
  check you didn't leave `SSL_STAGING=true` set).
- Log into the SPA in a browser at that URL. Default credentials are
  `admin` / `Admin123` (yes, the same placeholder already in this repo's
  root `.env.example` for `OPENMRS_USERNAME`/`OPENMRS_PASSWORD`).
- Confirm port 22 is restricted to your IP, not open to the world:
  `aws ec2 describe-security-groups --region <region> --group-ids <sg-id>`.
- `dig +short clearmed-openmrs.duckdns.org` matches the instance's current
  public IP (`curl -s ifconfig.me` on the box). `systemctl status
  duckdns-update.timer` on the host shows it active/enabled; `journalctl -u
  duckdns-update.service --no-pager` shows `OK` responses.

## Immediately after first login

- **Rotate the admin password.**
- **Create a dedicated least-privilege service account** for ClearMed to use
  (scoped to only the REST resources it needs — patients, observations —
  not `admin`). See the existing guidance in
  [`../../openmrs/README.md`](../../openmrs/README.md).
- **Find the concept UUID for clinical notes** on this instance (needed for
  `OPENMRS_NOTE_CONCEPT_UUID`) — it's instance/dictionary-specific and can't
  be guessed.

## After this is up (follow-up work, not part of this task)

1. Update the ClearMed backend's `.env`:
   `OPENMRS_BASE_URL=https://clearmed-openmrs.duckdns.org/openmrs`,
   `OPENMRS_ORIGIN=https://clearmed-openmrs.duckdns.org`, the new service
   account's `OPENMRS_USERNAME`/`OPENMRS_PASSWORD`, and
   `OPENMRS_NOTE_CONCEPT_UUID`.
2. Deploy `openmrs-frontend/esm-clearmed-widget` into this instance's
   frontend module config.
3. Revisit the widget's placement: it currently registers as its own
   top-level patient-chart dashboard tab
   (`openmrs-frontend/esm-clearmed-widget/src/dashboard.meta.ts`,
   `src/index.ts`, `src/routes.json`) rather than living inline next to each
   note under "Visits", specifically because the widget's README didn't
   know which `openmrs-esm-patient-chart` workspace-API generation
   (`workspaces` vs `workspaces2`) a target instance runs. Now that we
   control the instance and pin its version (`TAG` in `.env.production`),
   that's knowable — move the button (currently
   `src/clearmed-widget.component.tsx`) into the visit/notes widget's own
   extension slot instead.
