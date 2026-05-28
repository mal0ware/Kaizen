# Kaizen — deploy/

Production deployment artifacts for **Box A**, the always-on home that
runs Kaizen core + Vixen on a single DigitalOcean Droplet funded by the
GitHub Student Developer Pack credit. Hermes is not co-hosted here.

| File | Purpose |
|---|---|
| `docker-compose.box-a.yml` | The full stack: shared Postgres (with pgvector) + Redis + Kaizen + Vixen. |
| `postgres-init.sh` | First-boot script that creates per-project DBs/roles and enables pgvector. |
| `provision.sh` | Fresh-Droplet bootstrap: Docker, Tailscale, ufw, unattended-upgrades, restic. |
| `.env.example` | Environment template (copy to `.env`, fill in secrets, never commit). |
| `backup.sh` | Nightly `pg_dump` + Redis AOF snapshot pushed into a restic repo. |
| `box-a.service` | systemd unit that auto-starts the compose stack on boot. |
| `box-a-backup.service` + `.timer` | Schedules `backup.sh` at 03:30 daily. |
| `runbook.md` | The operational reference — read this first. |

Start with [`runbook.md`](runbook.md).
