#!/usr/bin/env bash
# Rebuilds images from the current source and restarts the stack, keeping the data volume and JWT secret.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."
[ -f .env ] || { echo "no .env found; run install.sh first"; exit 1; }
set -a; source .env; set +a
echo "==> Backing up before upgrade"
./deploy/scripts/backup.sh
echo "==> Rebuilding"
docker compose -f compose.airgap.yaml build
echo "==> Restarting"
docker compose -f compose.airgap.yaml up -d
echo "==> Verifying"
sleep 5
./deploy/scripts/selfcheck.sh
