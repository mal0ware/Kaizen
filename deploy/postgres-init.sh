#!/usr/bin/env bash
# Box A — Postgres first-boot initialization.
#
# Runs once, the first time the postgres container starts against an
# empty data volume (docker-entrypoint.sh executes everything in
# /docker-entrypoint-initdb.d/). Creates per-project roles + databases
# and enables pgvector in the Kaizen DB.
#
# Subsequent compose ups are no-ops here; the data volume already
# exists and the entrypoint skips initdb.

set -euo pipefail

create_role() {
  local role="$1" pw="$2"
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "postgres" <<-EOSQL
    DO \$\$
    BEGIN
      IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '${role}') THEN
        CREATE ROLE "${role}" LOGIN PASSWORD '${pw}';
      END IF;
    END
    \$\$;
EOSQL
}

create_db_if_missing() {
  local db="$1" owner="$2"
  local exists
  exists=$(psql -tAX -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "postgres" \
    -c "SELECT 1 FROM pg_database WHERE datname='${db}'" || true)
  if [ "${exists}" != "1" ]; then
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "postgres" \
      -c "CREATE DATABASE \"${db}\" OWNER \"${owner}\""
  fi
}

create_role "${KAIZEN_DB_USER:-kaizen}" "${KAIZEN_DB_PASSWORD:?KAIZEN_DB_PASSWORD required}"
create_role "${VIXEN_DB_USER:-vixen}"   "${VIXEN_DB_PASSWORD:?VIXEN_DB_PASSWORD required}"

create_db_if_missing "kaizen" "${KAIZEN_DB_USER:-kaizen}"
create_db_if_missing "vixen"  "${VIXEN_DB_USER:-vixen}"

# Kaizen uses pgvector for semantic memory; enable inside its own DB.
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "kaizen" \
  -c "CREATE EXTENSION IF NOT EXISTS vector;"

echo "postgres-init: per-project roles, databases, and pgvector ready."
