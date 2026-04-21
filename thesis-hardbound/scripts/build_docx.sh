#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

REF_DOC="thesis-hardbound/reference/reference.docx"
BIB="thesis-hardbound/bibliography/references.bib"
CSL="thesis-hardbound/bibliography/acm-sig-proceedings.csl"
OUT="thesis-hardbound/dist/thesis.docx"

mkdir -p "$(dirname "$OUT")"

# Concatenate chapters in a stable order.
CHAPTERS=(
  thesis-hardbound/chapters/00_abstract.md
  thesis-hardbound/chapters/01_introduction.md
  thesis-hardbound/chapters/02_related_work.md
  thesis-hardbound/chapters/03_technicality_project.md
  thesis-hardbound/chapters/04_methodology.md
  thesis-hardbound/chapters/05_results_discussion.md
  thesis-hardbound/chapters/06_conclusion_recommendations.md
  thesis-hardbound/chapters/A_appendix_commands_repro.md
  thesis-hardbound/chapters/B_appendix_lexicon_eval_assets.md
)

PANDOC_IMAGE="${PANDOC_IMAGE:-pandoc/core:3.1}"

echo "Building DOCX (Markdown -> DOCX)..."
echo "- reference doc: $REF_DOC"
echo "- bibliography:  $BIB"
echo "- csl:           $CSL"
echo "- output:        $OUT"

docker run --rm \
  -v "$(pwd)":/data \
  -w /data \
  "$PANDOC_IMAGE" \
  "${CHAPTERS[@]}" \
  --resource-path="thesis-hardbound" \
  --reference-doc="$REF_DOC" \
  --citeproc \
  --bibliography="$BIB" \
  --csl="$CSL" \
  -o "$OUT"

echo "Done."
