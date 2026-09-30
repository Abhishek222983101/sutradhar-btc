#!/usr/bin/env bash
# Backs up the app database, datasets and runs into one timestamped tar.gz under ./backups/.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="backups/sutradhar-backup-${STAMP}.tar.gz"
mkdir -p backups

echo "==> Checkpointing the database"
docker compose -f compose.airgap.yaml exec -T api python -c "
import sqlite3
c = sqlite3.connect('/data/app.sqlite')
c.execute('PRAGMA wal_checkpoint(TRUNCATE)')
c.close()
" 2>/dev/null || true

echo "==> Archiving /data from the api container"
docker compose -f compose.airgap.yaml exec -T api tar czf - -C / data > "$OUT"
echo "==> Backup written to $OUT ($(du -h "$OUT" | cut -f1))"
