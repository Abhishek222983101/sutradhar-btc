#!/usr/bin/env bash
# Verifies the running stack: health, offline guard, and a full generate->ingest->analyse->verify cycle.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."

echo "==> API health"
curl -fsS "http://127.0.0.1:${WEB_PORT:-8080}/api/health" && echo " OK"

echo "==> Full offline selftest (generate, ingest, run twice, verify audit chain, confirm no egress)"
docker compose -f compose.airgap.yaml exec -T api sutradhar selftest

echo "==> Audit chain verification"
docker compose -f compose.airgap.yaml exec -T api sutradhar audit verify

echo ""
echo "All checks passed. Sutradhar is installed correctly and provably offline."
