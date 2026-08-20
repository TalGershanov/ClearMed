#!/usr/bin/env bash
# Hits the DuckDNS update API so DUCKDNS_DOMAIN always resolves to this
# host's current public IP. No IP is passed explicitly — DuckDNS uses the
# address the request arrives from, which is exactly this instance's current
# public IP (there's no NAT/proxy in front of it).
#
# Installed by setup-host.sh to run as a systemd service on every boot plus
# every 5 minutes as a safety net (see duckdns-update.service/.timer).
#
# Reads DUCKDNS_DOMAIN and DUCKDNS_TOKEN from /etc/duckdns.env.

set -euo pipefail

CONFIG_FILE="/etc/duckdns.env"
if [[ ! -f "$CONFIG_FILE" ]]; then
  echo "Missing $CONFIG_FILE (expects DUCKDNS_DOMAIN and DUCKDNS_TOKEN)" >&2
  exit 1
fi
# shellcheck disable=SC1090
source "$CONFIG_FILE"

if [[ -z "${DUCKDNS_DOMAIN:-}" || -z "${DUCKDNS_TOKEN:-}" ]]; then
  echo "DUCKDNS_DOMAIN and DUCKDNS_TOKEN must both be set in $CONFIG_FILE" >&2
  exit 1
fi

RESPONSE=$(curl -fsS "https://www.duckdns.org/update?domains=${DUCKDNS_DOMAIN}&token=${DUCKDNS_TOKEN}&ip=")
echo "$(date -Is) duckdns update for ${DUCKDNS_DOMAIN}: ${RESPONSE}"

if [[ "$RESPONSE" != "OK" ]]; then
  echo "DuckDNS update failed (expected 'OK', got '${RESPONSE}')" >&2
  exit 1
fi
