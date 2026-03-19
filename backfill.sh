#!/usr/bin/env bash
set -euo pipefail

# Quick ML Analysis Backfill Script (bash)
#
# Usage:
#   ./backfill.sh [days] [batch_size]
#
# Examples:
#   ./backfill.sh 7 50
#   ./backfill.sh 3 200

DAYS="${1:-7}"
BATCH_SIZE="${2:-100}"

echo "Starting ML analysis backfill for last ${DAYS} days..."
echo "Batch size: ${BATCH_SIZE}"
echo ""

# Run the backfill inside Docker. Support both legacy `docker-compose` and
# modern `docker compose`.
if command -v docker-compose >/dev/null 2>&1; then
  docker-compose exec api python /app/scripts/backfill_ml_analysis.py --days "${DAYS}" --batch-size "${BATCH_SIZE}"
else
  docker compose exec api python /app/scripts/backfill_ml_analysis.py --days "${DAYS}" --batch-size "${BATCH_SIZE}"
fi

echo ""
echo "Backfill command completed. Monitor progress with:"
echo "  docker compose logs -f worker"
