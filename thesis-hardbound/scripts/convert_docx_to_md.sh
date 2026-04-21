#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

IN="thesis-hardbound/reference/reference.docx"
OUT="thesis-hardbound/chapters/00_baseline_from_docx.md"
MEDIA_DIR="thesis-hardbound/figures"

mkdir -p "$(dirname "$OUT")" "$MEDIA_DIR"

# Uses Dockerized Pandoc to avoid installing pandoc locally.
# Image choice is intentionally lightweight.
PANDOC_IMAGE="${PANDOC_IMAGE:-pandoc/core:3.1}"

echo "Converting DOCX -> Markdown baseline..."
echo "- input:  $IN"
echo "- output: $OUT"
echo "- media:  $MEDIA_DIR"

docker run --rm \
  -v "$ROOT_DIR":/data \
  -w /data \
  "$PANDOC_IMAGE" \
  "$IN" \
  -t gfm \
  --extract-media="$MEDIA_DIR" \
  -o "$OUT"

echo "Done."

