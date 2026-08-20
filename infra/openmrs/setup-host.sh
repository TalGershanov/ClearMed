#!/usr/bin/env bash
# Bootstraps a fresh Ubuntu 22.04 EC2 instance to run self-hosted OpenMRS
# (O3 Reference Application) via Docker Compose with Let's Encrypt HTTPS.
#
# Run this ON the EC2 instance (over SSH), as the `ubuntu` user, from the
# directory where you've copied this repo's infra/openmrs/ files plus your
# filled-in .env.production and duckdns.env (see infra/openmrs/README.md).
#
# Installs a systemd timer that hits the DuckDNS update API on every boot
# (plus every 5 minutes as a safety net) so clearmed-openmrs.duckdns.org
# always resolves to this instance's current public IP — there's no Elastic
# IP here, so the address does change if the instance is ever stopped and
# started again.
#
# Usage: ./setup-host.sh

set -euo pipefail

REPO_TAG="${REPO_TAG:-main}"  # openmrs-distro-referenceapplication branch/tag to clone
CHECKOUT_DIR="$HOME/openmrs-distro-referenceapplication"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.env.production"
DUCKDNS_ENV_FILE="$SCRIPT_DIR/duckdns.env"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE — copy .env.production.example, fill in real values, and place it next to this script." >&2
  exit 1
fi
if [[ ! -f "$DUCKDNS_ENV_FILE" ]]; then
  echo "Missing $DUCKDNS_ENV_FILE — copy duckdns.env.example, fill in your real token, and place it next to this script." >&2
  exit 1
fi

echo "== Installing Docker Engine + Compose plugin =="
if ! command -v docker >/dev/null; then
  sudo apt-get update
  sudo apt-get install -y ca-certificates curl gnupg git
  sudo install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  sudo chmod a+r /etc/apt/keyrings/docker.gpg
  echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
    $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
    sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
  sudo apt-get update
  sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  sudo usermod -aG docker "$USER"
  echo "Added $USER to the docker group — log out/in (or 'newgrp docker') for it to take effect in this shell."
fi

echo "== Installing DuckDNS auto-updater =="
sudo install -m 0600 -o root -g root "$DUCKDNS_ENV_FILE" /etc/duckdns.env
sudo install -m 0755 "$SCRIPT_DIR/duckdns-update.sh" /usr/local/bin/duckdns-update.sh

sudo tee /etc/systemd/system/duckdns-update.service > /dev/null <<'EOF'
[Unit]
Description=Update DuckDNS record with this host's current public IP
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/duckdns-update.sh
EOF

sudo tee /etc/systemd/system/duckdns-update.timer > /dev/null <<'EOF'
[Unit]
Description=Run duckdns-update.service on boot and every 5 minutes

[Timer]
OnBootSec=30s
OnUnitActiveSec=5min
Unit=duckdns-update.service
Persistent=true

[Install]
WantedBy=timers.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now duckdns-update.timer
echo "Running an initial DuckDNS update now (so DNS is correct before Let's Encrypt validates it)..."
sudo systemctl start duckdns-update.service
sudo systemctl status duckdns-update.service --no-pager -l | grep -E 'Active|duckdns update' || true

echo "== Cloning openmrs-distro-referenceapplication ($REPO_TAG) =="
if [[ ! -d "$CHECKOUT_DIR" ]]; then
  git clone --branch "$REPO_TAG" --depth 1 \
    https://github.com/openmrs/openmrs-distro-referenceapplication "$CHECKOUT_DIR"
fi

cp "$ENV_FILE" "$CHECKOUT_DIR/.env"

echo "== Starting the stack (docker compose up -d) =="
cd "$CHECKOUT_DIR"
sudo docker compose up -d

echo "== Waiting for services to report healthy (this can take several minutes on first boot) =="
for i in $(seq 1 60); do
  STATUS=$(sudo docker compose ps --format '{{.Service}}: {{.Status}}')
  echo "$STATUS"
  if ! echo "$STATUS" | grep -qE 'starting|unhealthy'; then
    break
  fi
  sleep 10
done

cat <<'EOF'

== Done ==
Check status any time with: sudo docker compose -f ~/openmrs-distro-referenceapplication/docker-compose.yml ps
Logs:                       sudo docker compose -f ~/openmrs-distro-referenceapplication/docker-compose.yml logs -f backend
DuckDNS updater logs:       sudo journalctl -u duckdns-update.service --no-pager

Next: verify HTTPS is up (see infra/openmrs/README.md's Verification section),
then log in and immediately rotate the default admin password.
EOF
