#!/usr/bin/env bash
# Box A — fresh-server bootstrap.
#
# Run once on a brand-new DigitalOcean Basic 2 GB Droplet
# (Ubuntu 24.04 LTS, NYC region) as root, e.g.:
#
#   ssh root@<droplet-ip>
#   curl -fsSL https://raw.githubusercontent.com/mal0ware/Kaizen/master/deploy/provision.sh -o provision.sh
#   bash provision.sh
#
# What it does:
#   1. Creates a non-root sudo user (operator) and copies authorized keys.
#   2. Locks down SSH (key-only, no root login, no passwords).
#   3. Enables ufw with only SSH open; Tailscale handles everything else.
#   4. Installs Docker Engine + the compose plugin.
#   5. Installs Tailscale (interactive auth needed at the end).
#   6. Installs unattended-upgrades for security patches.
#   7. Installs restic for backups (configured separately by backup.sh).
#   8. Creates /opt/box-a and tells you what to clone next.
#
# Idempotent: re-running is safe.

set -euo pipefail

NEW_USER="${BOX_A_USER:-operator}"
SSH_PORT="${SSH_PORT:-22}"

log() { printf '\n=== %s ===\n' "$*"; }

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root (or via sudo)." >&2
  exit 1
fi

# ------------------------------------------------------------------------------
log "Updating base system"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get upgrade -y

# ------------------------------------------------------------------------------
log "Creating operator user '${NEW_USER}'"
if ! id "${NEW_USER}" &>/dev/null; then
  adduser --disabled-password --gecos "" "${NEW_USER}"
  usermod -aG sudo "${NEW_USER}"
fi
# Copy root's authorized_keys so the same SSH key gets you in as operator.
mkdir -p "/home/${NEW_USER}/.ssh"
if [[ -f /root/.ssh/authorized_keys ]]; then
  cp /root/.ssh/authorized_keys "/home/${NEW_USER}/.ssh/authorized_keys"
fi
chmod 700 "/home/${NEW_USER}/.ssh"
chmod 600 "/home/${NEW_USER}/.ssh/authorized_keys" 2>/dev/null || true
chown -R "${NEW_USER}:${NEW_USER}" "/home/${NEW_USER}/.ssh"
# Passwordless sudo for the operator — same key-based access as root used to give.
echo "${NEW_USER} ALL=(ALL) NOPASSWD:ALL" > "/etc/sudoers.d/90-${NEW_USER}"
chmod 440 "/etc/sudoers.d/90-${NEW_USER}"

# ------------------------------------------------------------------------------
log "Hardening SSH"
SSHD_CONF=/etc/ssh/sshd_config
sed -ri 's/^#?PermitRootLogin.*/PermitRootLogin no/' "$SSHD_CONF"
sed -ri 's/^#?PasswordAuthentication.*/PasswordAuthentication no/' "$SSHD_CONF"
sed -ri 's/^#?PubkeyAuthentication.*/PubkeyAuthentication yes/' "$SSHD_CONF"
sed -ri 's/^#?ChallengeResponseAuthentication.*/ChallengeResponseAuthentication no/' "$SSHD_CONF"
systemctl reload ssh || systemctl reload sshd

# ------------------------------------------------------------------------------
log "Configuring ufw firewall"
apt-get install -y ufw
ufw default deny incoming
ufw default allow outgoing
ufw allow "${SSH_PORT}/tcp" comment "ssh"
yes | ufw enable

# ------------------------------------------------------------------------------
log "Installing Docker Engine + compose plugin"
apt-get install -y ca-certificates curl gnupg
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  | gpg --dearmor --yes -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg
. /etc/os-release
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" \
  > /etc/apt/sources.list.d/docker.list
apt-get update -y
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
usermod -aG docker "${NEW_USER}"
systemctl enable --now docker

# ------------------------------------------------------------------------------
log "Installing Tailscale"
curl -fsSL https://tailscale.com/install.sh | sh
# Interactive: ask the user to run `tailscale up` at the end with their auth.
# We don't pre-bake an auth key here to avoid leaving one in any image.

# ------------------------------------------------------------------------------
log "Enabling unattended-upgrades for security patches"
apt-get install -y unattended-upgrades apt-listchanges
dpkg-reconfigure -f noninteractive unattended-upgrades
cat > /etc/apt/apt.conf.d/52unattended-upgrades-reboot <<'EOF'
Unattended-Upgrade::Automatic-Reboot "true";
Unattended-Upgrade::Automatic-Reboot-Time "04:00";
EOF

# ------------------------------------------------------------------------------
log "Installing restic for backups"
apt-get install -y restic
mkdir -p /var/backups/box-a/restic
chown -R "${NEW_USER}:${NEW_USER}" /var/backups/box-a

# ------------------------------------------------------------------------------
log "Preparing /opt/box-a"
mkdir -p /opt/box-a
chown -R "${NEW_USER}:${NEW_USER}" /opt/box-a

# ------------------------------------------------------------------------------
cat <<EOF

================================================================================
Box A provisioning complete.

Next steps (run as ${NEW_USER}, not root):

  ssh ${NEW_USER}@<droplet-ip>
  sudo tailscale up                      # follow the auth URL
  cd /opt/box-a
  git clone https://github.com/mal0ware/Kaizen.git
  git clone https://github.com/mal0ware/Vixen.git
  cd Kaizen
  cd deploy
  cp .env.example .env
  \$EDITOR .env                          # fill in tokens + DB passwords
  docker compose -f docker-compose.box-a.yml up -d --build
  # one-time Vixen schema migration:
  docker compose -f docker-compose.box-a.yml exec vixen alembic upgrade head

Then set up automatic backups and the systemd auto-start unit per
deploy/runbook.md.

DigitalOcean billing alert: open the cloud console once and set a
$5 budget alarm under Settings -> Billing -> Notifications. The credit
covers a year of Basic 2 GB, but the alarm is the belt-and-braces
guard against ever being silently charged.
================================================================================
EOF
