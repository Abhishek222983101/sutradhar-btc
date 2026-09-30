#!/usr/bin/env bash
# Restores a backup produced by backup.sh. Usage: ./deploy/scripts/restore.sh backups/sutradhar-backup-XXXX.tar.gz
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."
ARCHIVE="${1:?usage: restore.sh <backup.tar.gz>}"
[ -f "$ARCHIVE" ] || { echo "not found: $ARCHIVE"; exit 1; }

echo "==> Stopping the stack"
docker compose -f compose.airgap.yaml down

echo "==> Restoring into the sutradhar-data volume"
docker run --rm -v sutradhar_sutradhar-data:/data -v "$(pwd)/$(dirname "$ARCHIVE")":/backup alpine \
  sh -c "rm -rf /data/* && tar xzf /backup/$(basename "$ARCHIVE") -C / "

echo "==> Restarting the stack"
JWT_SECRET="$(grep JWT_SECRET .env | cut -d= -f2)" docker compose -f compose.airgap.yaml up -d

echo "==> Verifying"
sleep 5
./deploy/scripts/selfcheck.sh
echo "==> Restore complete"
