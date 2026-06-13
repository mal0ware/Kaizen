#!/usr/bin/env bash
# Reproducible live pgvector memory test: docker up -> migrate -> test -> down.
#
#   ./scripts/pgvector-test.sh           # bring up, test, tear down
#   KEEP_UP=1 ./scripts/pgvector-test.sh # leave the container running afterwards
#
# Requires Docker and the `db` extra installed (pip install -e ".[db]").
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE="$ROOT/deploy/docker-compose.pgvector-test.yml"
DB_URL="postgresql+asyncpg://kaizen:kaizen@127.0.0.1:5433/kaizen"
PSQL_URL="postgresql://kaizen:kaizen@127.0.0.1:5433/kaizen"

cleanup() {
  if [ "${KEEP_UP:-0}" != "1" ]; then
    echo "==> tearing down pgvector container"
    docker compose -f "$COMPOSE" down -v >/dev/null 2>&1 || true
  else
    echo "==> KEEP_UP=1: leaving container up. URL: $DB_URL"
  fi
}
trap cleanup EXIT

echo "==> starting pgvector (deploy/docker-compose.pgvector-test.yml, host port 5433)"
docker compose -f "$COMPOSE" up -d

echo "==> waiting for Postgres to accept connections"
for _ in $(seq 1 40); do
  if docker exec kaizen-pgvector-test pg_isready -U kaizen -d kaizen >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

echo "==> enabling the vector extension (migrate)"
docker exec kaizen-pgvector-test psql -U kaizen -d kaizen \
  -c "CREATE EXTENSION IF NOT EXISTS vector;" >/dev/null

echo "==> running the integration suite against $PSQL_URL"
KAIZEN_TEST_DATABASE_URL="$DB_URL" python -m pytest tests/integration -v
