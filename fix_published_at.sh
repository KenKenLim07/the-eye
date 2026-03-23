#!/usr/bin/env bash
set -euo pipefail

# Fix `published_at` drift (bash)
#
# Usage:
#   ./fix_published_at.sh [days] [--apply|--dry-run]
#
# Examples:
#   ./fix_published_at.sh 7 --dry-run
#   ./fix_published_at.sh 7 --apply

DAYS="${1:-7}"
MODE="${2:---dry-run}"

compose_cmd=(docker compose)
if command -v docker-compose >/dev/null 2>&1; then
  compose_cmd=(docker-compose)
fi

cmd=(
  "${compose_cmd[@]}"
  exec
  worker_ml
  python
  /app/scripts/fix_published_at_drift.py
  --days
  "${DAYS}"
)

case "${MODE}" in
  --apply)
    cmd+=(--apply)
    ;;
  --dry-run|*)
    cmd+=(--dry-run)
    ;;
esac

"${cmd[@]}"

