#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root"
  exit 1
fi

PROJECT_DIR="${1:-/opt/patent_generator}"
cd "$PROJECT_DIR"

docker compose -f docker-compose.server.yml up --build -d

docker compose -f docker-compose.server.yml ps
