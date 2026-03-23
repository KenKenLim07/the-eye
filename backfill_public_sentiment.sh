#!/usr/bin/env bash
set -euo pipefail

# Backfill `article_sentiment_public` from `bias_analysis` (bash)
#
# Usage:
#   ./backfill_public_sentiment.sh [days] [--apply|--dry-run] [batch_size]
#
# Examples:
#   ./backfill_public_sentiment.sh 7 --dry-run
#   ./backfill_public_sentiment.sh 7 --apply 500

DAYS="${1:-7}"
MODE="${2:---dry-run}"
BATCH="${3:-500}"

compose_cmd=(docker compose)
if command -v docker-compose >/dev/null 2>&1; then
  compose_cmd=(docker-compose)
fi

cmd=(
  "${compose_cmd[@]}"
  exec
  worker_ml
  python
  /app/scripts/backfill_article_sentiment_public.py
  --days
  "${DAYS}"
  --batch-size
  "${BATCH}"
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

