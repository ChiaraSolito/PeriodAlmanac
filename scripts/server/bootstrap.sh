#!/usr/bin/env bash
# One-time setup of a fresh Ubuntu 24.04 server for PeriodAlmanac.
# Run on the server:  sudo bash scripts/server/bootstrap.sh
# Safe to re-run.
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "Esegui con sudo: sudo bash $0" >&2
  exit 1
fi
TARGET_USER="${SUDO_USER:-ubuntu}"
export DEBIAN_FRONTEND=noninteractive

echo "==> Aggiornamento del sistema"
apt-get update
apt-get -y upgrade
apt-get install -y ca-certificates curl git sqlite3 unattended-upgrades
# Automatic security updates.
dpkg-reconfigure -f noninteractive unattended-upgrades

echo "==> Docker"
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sh
fi
systemctl enable --now docker
usermod -aG docker "$TARGET_USER"

echo "==> Tailscale"
if ! command -v tailscale >/dev/null 2>&1; then
  curl -fsSL https://tailscale.com/install.sh | sh
fi
systemctl enable --now tailscaled

echo
echo "Fatto. Prossimi passi:"
echo "  1. sudo tailscale up --hostname periodalmanac   (apri il link stampato per autorizzare il server)"
echo "  2. esci e rientra via SSH, così l'utente $TARGET_USER può usare docker senza sudo"
