# Box A — Operational Runbook

The always-on home for Kaizen core + Vixen, sized to fit inside the
GitHub Student Developer Pack's $200 DigitalOcean credit for a full
year. Hermes is **not** co-hosted here (see [Why Hermes is on its own
box](#why-hermes-is-on-its-own-box)).

---

## What runs here

| Service | Purpose | Network | Storage |
|---|---|---|---|
| `box-a-postgres` | Shared Postgres 16 with `pgvector` | `box-a-net` only | `postgres-data` volume |
| `box-a-redis` | Shared Redis 7 (AOF on, RDB snapshots on) | `box-a-net` only | `redis-data` volume |
| `box-a-kaizen` | Kaizen core (reasoning loop + router + Discord gateway) | `box-a-net` -> postgres/redis | none |
| `box-a-vixen` | Vixen Discord bot | `box-a-net` -> postgres/redis | none |

The data plane (postgres / redis) is bound to `127.0.0.1` on the host;
remote administrative access goes through Tailscale, never the public
internet.

---

## Sizing and cost

- **Droplet:** DigitalOcean Basic, 2 GB RAM / 1 vCPU / 50 GB SSD,
  region **NYC1** or **NYC3**, image **Ubuntu 24.04 LTS**.
- **List price:** ~$12/mo -> ~$144/yr.
- **Funded by:** the GitHub Student Developer Pack DigitalOcean offer
  ($200 credit, 1 year). A 2 GB Droplet runs the year inside the credit
  with $56 of headroom for storage / bandwidth / occasional snapshots.

A 4 GB Droplet (~$24/mo) is workable but exits the credit at ~month 8
and starts billing the card. Stick with 2 GB unless RAM forces it.

---

## Initial provisioning

Run these once per fresh Droplet.

### 1. Create the Droplet

In the DigitalOcean console: **Create -> Droplets ->**

- Image: Ubuntu 24.04 (LTS) x64
- Plan: Basic, Regular CPU, $12/mo (2 GB / 1 vCPU / 50 GB)
- Region: NYC1 or NYC3
- Authentication: **SSH Key** (paste your public key; no passwords)
- Hostname: `box-a`
- Backups: off (the in-app backups cost extra; restic to a Spaces
  bucket later is the cheaper move)

### 2. Bootstrap as root

```bash
ssh root@<droplet-ip>
curl -fsSL https://raw.githubusercontent.com/mal0ware/Kaizen/feat/box-a-deploy/deploy/provision.sh -o provision.sh
bash provision.sh
```

`provision.sh` is idempotent. It installs Docker + compose + Tailscale
+ ufw + unattended-upgrades + restic, creates the `operator` user,
hardens SSH, and prepares `/opt/box-a/`. Re-read [provision.sh](provision.sh)
before piping anything from the internet to bash.

### 3. Bring up Tailscale and finish login

```bash
ssh operator@<droplet-ip>
sudo tailscale up
# Open the printed URL once, approve the device. The Droplet now has
# a stable name like box-a.tail-xxxx.ts.net reachable only from your
# tailnet.
```

From this point on, SSH **only over Tailscale** if you can — the public
IP works but the tailnet IP is what you want in your `~/.ssh/config`.

### 4. Set the billing alarm (do this before deploying)

DigitalOcean console -> **Settings -> Billing -> Notifications**.
Create a budget alert at **$5**. The $200 credit covers the year, but
the alarm is the belt-and-braces guard that means a runaway resource
or a forgotten managed-DB cannot silently charge the card.

### 5. Clone the repos and configure

```bash
cd /opt/box-a
git clone https://github.com/mal0ware/Kaizen.git
git clone https://github.com/mal0ware/Vixen.git

cd Kaizen
git checkout feat/box-a-deploy        # until the branch is merged into master
cd deploy

cp .env.example .env
$EDITOR .env                          # see "Filling in .env" below
```

### 6. Bring up the stack

```bash
docker compose -f docker-compose.box-a.yml up -d --build

# One-time Vixen schema migration:
docker compose -f docker-compose.box-a.yml exec vixen alembic upgrade head

# Tail logs to confirm everything is healthy:
docker compose -f docker-compose.box-a.yml logs -f
```

### 7. Make it auto-start on boot, and schedule backups

```bash
sudo cp deploy/box-a.service          /etc/systemd/system/
sudo cp deploy/box-a-backup.service   /etc/systemd/system/
sudo cp deploy/box-a-backup.timer     /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now box-a.service
sudo systemctl enable --now box-a-backup.timer

# Verify
systemctl list-timers | grep box-a
```

---

## Filling in `.env`

Every `replace-with-openssl-rand` line in `.env.example` needs a real
secret. Generate them with:

```bash
openssl rand -hex 24
```

Then the real values to plug in are:

- `KAIZEN_ANTHROPIC_API_KEY` — frontier tier. Optional; Kaizen falls
  back to local-only without it (per ADR 0005).
- `KAIZEN_LOCAL_MODEL_ENDPOINT` — if you've wired the home RTX 3080 as
  the on-demand GPU worker (ADR 0007), set this to its Tailscale name,
  e.g. `http://desktop.tail-xxxx.ts.net:11434`. Otherwise leave default.
- `KAIZEN_DISCORD_TOKEN` and `DISCORD_TOKEN` — the bot tokens for
  Kaizen's gateway and for Vixen. Different applications, different
  tokens.
- `GUILD_ID` — Vixen's primary guild ID for fast slash-command sync.

---

## Day-2 operations

### Tailing logs

```bash
cd /opt/box-a/Kaizen/deploy
docker compose -f docker-compose.box-a.yml logs -f kaizen vixen
```

### Restarting one service

```bash
docker compose -f docker-compose.box-a.yml restart kaizen
```

### Updating an app (pull new code -> rebuild image)

```bash
cd /opt/box-a/Kaizen && git pull
cd /opt/box-a/Vixen  && git pull
cd /opt/box-a/Kaizen/deploy
docker compose -f docker-compose.box-a.yml up -d --build
# If Vixen had schema changes:
docker compose -f docker-compose.box-a.yml exec vixen alembic upgrade head
```

### Backup health

```bash
# Latest backup:
journalctl -u box-a-backup.service -n 30 --no-pager

# Inspect snapshots:
set -a && . /opt/box-a/Kaizen/deploy/.env && set +a
restic -r "$RESTIC_REPOSITORY" snapshots
```

### Restore drill (do this once after the first successful backup)

```bash
set -a && . /opt/box-a/Kaizen/deploy/.env && set +a
restic -r "$RESTIC_REPOSITORY" restore latest --target /tmp/restore
ls /tmp/restore/postgres
# pg_restore -d kaizen /tmp/restore/postgres/kaizen.dump  (in a scratch DB)
```

A restore you never tested is a restore that does not work.

### Disk / memory sanity check

```bash
df -h /
free -m
docker system df
docker stats --no-stream
```

If `docker system df` shows >1 GB of build cache and you're tight, run
`docker builder prune -f`.

---

## Off-site backups (later, optional)

Restic to `/var/backups/box-a/restic` is fine to start — it survives a
container wipe but not a Droplet loss. When you want offsite:

1. In the DO console create a **Spaces** bucket (S3-compatible).
2. Set `RESTIC_REPOSITORY=s3:https://nyc3.digitaloceanspaces.com/<bucket>/restic`
   in `.env`.
3. Export `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` in the systemd
   service environment (drop-in `box-a-backup.service.d/secrets.conf`).
4. `restic init` against the new repo and let the timer run.

Spaces is ~$5/mo — outside the Droplet credit budget, so do this only
if the data is genuinely irreplaceable.

---

## Why Hermes is on its own box

`hosting-analysis.md` covers this in full. Short version:

- Hermes' bridge + TimescaleDB + Redis + IB Gateway needs ~3-4 GB on
  its own, which doesn't fit alongside Kaizen + Vixen on a 2 GB box.
- Trading wants **dedicated** vCPU. Box A is a shared-vCPU Basic
  Droplet; CPU steal would introduce jitter into the trade loop, which
  is worse for performance than raw slowness.
- Live trading needs isolation from experimental bots — a misbehaving
  Discord cog must not be able to touch the order path.

When Hermes goes live, stand it up on a DigitalOcean **CPU-Optimized**
Droplet in NYC (~$32/mo dedicated vCPU) or a Hetzner CCX in Ashburn,
and follow `Hermes/deploy/ibc/runbook.md` for the IBC auto-login and
daily Gateway restart.

---

## Failure modes

| Symptom | Likely cause | Action |
|---|---|---|
| `kaizen` / `vixen` crashlooping | bad `.env` or DB not ready | `docker compose logs <service>`; verify `.env` against `.env.example` |
| Postgres init never re-runs after changing passwords | data volume already initialized | `docker compose down`, `docker volume rm box-a_postgres-data`, `up -d` (destructive — restore from backup) |
| Out of memory under load | 2 GB ceiling hit | check `docker stats`; consider 4 GB plan or evict the lowest-priority service |
| Cannot SSH after provisioning | locked yourself out via ufw / sshd | use DigitalOcean recovery console via the web UI |

---

## Sources of truth

- This runbook lives next to the code it describes; if you change one,
  change the other.
- Architectural rationale: `docs/architecture.md` (Kaizen), Hermes'
  `hosting-analysis.md` and `home-server-plan.md` for the broader
  hosting strategy.
- Cost numbers reflect 2026 DigitalOcean pricing and the GitHub
  Student Developer Pack offer terms current as of branch creation;
  re-verify before relying on them long-term.
