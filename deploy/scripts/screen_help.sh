#!/usr/bin/env bash
set -euo pipefail

echo "Active screens:"
screen -ls | grep patent_ || true

echo
echo "Attach backend:  screen -r patent_backend"
echo "Attach frontend: screen -r patent_frontend"
echo "Detach inside screen: Ctrl+A then D"
