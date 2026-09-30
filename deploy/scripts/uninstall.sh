#!/usr/bin/env bash
# Removes the running stack. Pass --purge-data to also delete the data volume (irreversible).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."
docker compose -f compose.airgap.yaml down $([ "${1:-}" = "--purge-data" ] && echo "-v")
echo "Sutradhar stopped.$([ "${1:-}" = "--purge-data" ] && echo " Data volume removed.")"
