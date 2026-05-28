#!/usr/bin/env bash
# Box A — nightly backup.
#
# Dumps every Postgres database via pg_dump (clean, owner-preserving),
# snapshots the Redis AOF, and pushes the lot into a restic repository.
# Designed to be invoked by the systemd timer box-a-backup.timer.
#
# Restore drill (do this once after the first successful run, then put
# the date in your calendar):
#   restic -r "$RESTIC_REPOSITORY" snapshots
#   restic -r "$RESTIC_REPOSITORY" restore latest --target /tmp/restore

set -euo pipefail

cd "$(dirname "$0")"

# Pull RESTIC_REPOSITORY / RESTIC_PASSWORD / POSTGRES_* from .env.
set -a; . ./.env; set +a

: "${RESTIC_REPOSITORY:?RESTIC_REPOSITORY must be set}"
: "${RESTIC_PASSWORD:?RESTIC_PASSWORD must be set}"

STAGING="$(mktemp -d /tmp/box-a-backup.XXXXXX)"
trap 'rm -rf "$STAGING"' EXIT

# Lazily init the repo if it doesn't exist yet.
if ! restic -r "$RESTIC_REPOSITORY" snapshots --no-lock >/dev/null 2>&1; then
  restic -r "$RESTIC_REPOSITORY" init
fi

# ------------------------------------------------------------------------------
# Postgres — one logical dump per database.
# ------------------------------------------------------------------------------
PGDUMP_DIR="${STAGING}/postgres"
mkdir -p "$PGDUMP_DIR"
for DB in kaizen vixen; do
  docker exec -e PGPASSWORD="${POSTGRES_SUPERUSER_PASSWORD}" box-a-postgres \
    pg_dump -U "${POSTGRES_SUPERUSER:-postgres}" -Fc --clean --if-exists "$DB" \
    > "${PGDUMP_DIR}/${DB}.dump"
done

# ------------------------------------------------------------------------------
# Redis — flush AOF to a tarball.
# ------------------------------------------------------------------------------
REDIS_DIR="${STAGING}/redis"
mkdir -p "$REDIS_DIR"
docker exec box-a-redis redis-cli BGREWRITEAOF >/dev/null
# Give the rewrite a moment to land, then copy.
sleep 2
docker run --rm --volumes-from box-a-redis -v "${REDIS_DIR}:/out" \
  alpine sh -c "tar czf /out/redis-aof.tgz -C /data ." >/dev/null

# ------------------------------------------------------------------------------
# Push to restic.
# ------------------------------------------------------------------------------
restic -r "$RESTIC_REPOSITORY" backup \
  --tag box-a --tag "$(date -u +%Y-%m-%d)" \
  "$STAGING"

# Keep 7 daily, 4 weekly, 6 monthly.
restic -r "$RESTIC_REPOSITORY" forget --prune \
  --keep-daily 7 --keep-weekly 4 --keep-monthly 6 >/dev/null

echo "backup ok: $(date -u +%FT%TZ)"
