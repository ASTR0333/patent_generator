#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root"
  exit 1
fi

apt update
apt install -y git curl ca-certificates gnupg lsb-release nginx certbot python3-certbot-nginx

install -m 0755 -d /etc/apt/keyrings
if [[ ! -f /etc/apt/keyrings/docker.gpg ]]; then
  ID="$(. /etc/os-release && echo "$ID")"
  curl -fsSL "https://download.docker.com/linux/$ID/gpg" | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg
fi

ARCH="$(dpkg --print-architecture)"
ID="$(. /etc/os-release && echo "$ID")"
CODENAME="$(. /etc/os-release && echo "$VERSION_CODENAME")"

if [[ "$ID" == "ubuntu" ]]; then
  echo "deb [arch=${ARCH} signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu ${CODENAME} stable" > /etc/apt/sources.list.d/docker.list
elif [[ "$ID" == "debian" ]]; then
  echo "deb [arch=${ARCH} signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian ${CODENAME} stable" > /etc/apt/sources.list.d/docker.list
else
  echo "Unsupported OS: $ID. This script supports Ubuntu and Debian."
  exit 1
fi

apt update
apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

systemctl enable docker
systemctl start docker
systemctl enable nginx
systemctl start nginx

if ! docker info >/dev/null 2>&1; then
  echo "Docker daemon is not available"
  exit 1
fi

echo "Docker + Nginx + Certbot installed."
