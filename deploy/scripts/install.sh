#!/usr/bin/env bash
# Sutradhar air-gapped installer. Run on Linux with Docker + Compose v2. No network required except to pull the
# pinned images the first time (or load them from a bundle with `docker load`).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."

export JWT_SECRET="$(openssl rand -hex 32)"
ADMIN_EMAIL="${ADMIN_BOOTSTRAP_EMAIL:-admin@local}"
ADMIN_PASSWORD="$(openssl rand -base64 18 | tr -d '=+/' | cut -c1-20)"

echo "==> Sutradhar installer"
echo "==> Building images (offline after this step)"
docker compose -f compose.airgap.yaml build

echo "==> Starting the stack"
docker compose -f compose.airgap.yaml up -d

echo "==> Waiting for the API to become healthy"
for _ in $(seq 1 60); do
  if docker compose -f compose.airgap.yaml exec -T api python -c "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/api/health', timeout=2)" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

echo "==> Creating the bootstrap admin account"
docker compose -f compose.airgap.yaml exec -T api sutradhar users create --email "$ADMIN_EMAIL" --name "Administrator" --role admin > /tmp/sutradhar-admin.txt 2>&1 || true

echo "==> Persisting the JWT secret for future 'docker compose' invocations"
{
  echo "JWT_SECRET=$JWT_SECRET"
} > .env
chmod 600 .env

echo ""
echo "==================================================================="
echo " Sutradhar is running: http://127.0.0.1:${WEB_PORT:-8080}"
echo " Admin account: $ADMIN_EMAIL"
grep "shown once" /tmp/sutradhar-admin.txt 2>/dev/null || true
echo " (secret persisted to .env; keep it safe, it signs every login)"
echo "==================================================================="
echo ""
echo "Run './deploy/scripts/selfcheck.sh' to verify the install end to end."
