#!/usr/bin/env bash
set -euo pipefail

# Quick ML Analysis Backfill Script (bash)
#
# Usage:
#   ./backfill.sh [days] [batch_size] [--dry-run]
#
# Examples:
#   ./backfill.sh 7 50
#   ./backfill.sh 3 200
#   ./backfill.sh 30 200 --dry-run

DAYS="${1:-7}"
BATCH_SIZE="${2:-100}"
DRY_RUN_ARG="${3:-}"

echo "Starting ML analysis backfill for last ${DAYS} days..."
echo "Batch size: ${BATCH_SIZE}"
if [[ "${DRY_RUN_ARG}" == "--dry-run" ]]; then
  echo "Dry run: enabled (no tasks will be queued)"
fi
echo ""

# Run the backfill inside Docker. Use `worker_ml` to avoid relying on the `api`
# container's network (some setups have intermittent DNS in `api` but not the
# worker containers). Support both legacy `docker-compose` and modern
# `docker compose`.
compose_cmd=(docker compose)
if command -v docker-compose >/dev/null 2>&1; then
  compose_cmd=(docker-compose)
fi

cmd=(
  "${compose_cmd[@]}"
  exec
  worker_ml
  python
  /app/scripts/backfill_ml_analysis.py
  --days
  "${DAYS}"
  --batch-size
  "${BATCH_SIZE}"
)
if [[ "${DRY_RUN_ARG}" == "--dry-run" ]]; then
  cmd+=(--dry-run)
fi

"${cmd[@]}"

echo ""
echo "Backfill command completed. Monitor progress with:"
echo "  docker compose logs -f worker_ml"
echo "  # or:"
echo "  docker logs -f ph-eye-worker-ml"
