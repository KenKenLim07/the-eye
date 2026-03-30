#!/usr/bin/env bash
set -euo pipefail

# Scrape catch-up backfill (ingest-only)
#
# Usage:
#   ./scrape_backfill.sh [days] [max_per_source] [sources_csv|--sources=sources_csv]
#
# Examples:
#   ./scrape_backfill.sh 7 80
#   ./scrape_backfill.sh 3 50 "gma,inquirer,rappler"
#   ./scrape_backfill.sh 7 80 --sources=inquirer

DAYS="${1:-7}"
MAX_PER_SOURCE="${2:-80}"
RAW_SOURCES_ARG="${3:-}"
SOURCES_CSV=""
if [[ -n "${RAW_SOURCES_ARG}" ]]; then
  if [[ "${RAW_SOURCES_ARG}" == --sources=* ]]; then
    SOURCES_CSV="${RAW_SOURCES_ARG#--sources=}"
  else
    SOURCES_CSV="${RAW_SOURCES_ARG}"
  fi
fi

echo "Starting scrape catch-up backfill for last ${DAYS} days..."
echo "Max per source: ${MAX_PER_SOURCE}"
if [[ -n "${SOURCES_CSV}" ]]; then
  echo "Sources: ${SOURCES_CSV}"
fi
echo ""

# Run inside Docker. Support both legacy `docker-compose` and modern `docker compose`.
compose_cmd=(docker compose)
if command -v docker-compose >/dev/null 2>&1; then
  compose_cmd=(docker-compose)
fi

cmd=(
  "${compose_cmd[@]}"
  exec
  worker
  python
  /app/scripts/backfill_scrape_articles.py
  --days
  "${DAYS}"
  --max-per-source
  "${MAX_PER_SOURCE}"
)
if [[ -n "${SOURCES_CSV}" ]]; then
  cmd+=(--sources "${SOURCES_CSV}")
fi

"${cmd[@]}"

echo ""
echo "Scrape backfill completed. You can now queue ML backfill (optional) with:"
echo "  ./backfill.sh ${DAYS} 200"
