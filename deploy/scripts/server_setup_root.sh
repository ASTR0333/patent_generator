#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root"
  exit 1
fi

apt update
apt install -y git curl nginx certbot python3-certbot-nginx redis-server screen \
  python3 python3-venv python3-pip nodejs npm

systemctl enable redis-server
systemctl start redis-server
systemctl enable nginx
systemctl start nginx

echo "Base packages installed."
