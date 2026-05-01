#!/usr/bin/env python3
"""
Build a *candidate* VADER PH lexicon patch from Kaggle-style XLSX word-sentiment files.

Why this exists
---------------
The Kaggle dataset in `backend/archive/*.xlsx` provides word-level polarity labels
(positive/negative/neutral) for PH languages (Tagalog, Cebuano, etc.). This script converts
those labels into numeric VADER-style valence scores and merges them into a copy of the
existing patch (`backend/app/ml/vader_ph_lexicon.v1.json`) *conservatively*:

- Adds NEW tokens only (no overrides), unless you explicitly enable overrides.
- Skips short/ambiguous tokens and common function words to reduce false polarity.
- Writes a new JSON patch file (recommended: `vader_ph_lexicon.v2.json`) so you can A/B test.

Typical use
-----------
  cd backend
  python scripts/kaggle_word_sentiments_to_vader_patch.py \\
    --inputs archive/Tagalog\\ Word\\ Sentiments\\ Full.xlsx,archive/PH\\ Word\\ Sentiments\\ Full.xlsx \\
    --out app/ml/vader_ph_lexicon.v2.json

Then evaluate:
  VADER_PH_PATCH=1 VADER_PH_PATCH_FILE=app/ml/vader_ph_lexicon.v2.json \\
    python scripts/evaluate_vader_ph_gold.py --model hybrid --ph-patch on
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
import xml.etree.ElementTree as ET

NS = {"ss": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


@dataclass(frozen=True)
class Row:
    word: str
    dialect: str
    sentiment: str
    definition: str


def _cell_ref_to_col_row(cell_ref: str) -> tuple[int, int] | None:
    m = re.match(r"^([A-Z]+)([0-9]+)$", cell_ref)
    if not m:
        return None
    col_s, row_s = m.group(1), m.group(2)
    col = 0
    for ch in col_s:
        col = col * 26 + (ord(ch) - 64)
    return (col - 1, int(row_s))


def _read_xlsx_rows(path: Path, *, limit: int | None = None) -> list[Row]:
    """
    Minimal XLSX reader (no external deps).
    Assumes a single sheet: `xl/worksheets/sheet1.xml`.
    """
    with zipfile.ZipFile(path) as z:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in z.namelist():
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in root.findall("ss:si", NS):
                texts = [t.text or "" for t in si.findall(".//ss:t", NS)]
                shared.append("".join(texts))

        sheet = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))

        # First row = header.
        header_row = sheet.find(".//ss:sheetData/ss:row", NS)
        if header_row is None:
            return []

        header: dict[int, str] = {}
        for c in header_row.findall("ss:c", NS):
            ref = c.attrib.get("r") or ""
            pos = _cell_ref_to_col_row(ref)
            if not pos:
                continue
            col_i, _ = pos
            v = c.find("ss:v", NS)
            if v is None:
                continue
            val = v.text or ""
            if c.attrib.get("t") == "s":
                try:
                    val = shared[int(val)]
                except Exception:
                    pass
            header[col_i] = (val or "").strip().lower()

        # Map expected columns.
        want = {"word", "definition", "dialect", "sentiment"}
        col_to_name = {col: name for col, name in header.items() if name in want}
        if "word" not in set(col_to_name.values()):
            raise SystemExit(f"{path}: missing 'word' column in header: {header}")

        rows: list[Row] = []
        for row_el in sheet.findall(".//ss:sheetData/ss:row", NS)[1:]:
            cells: dict[int, str] = {}
            for c in row_el.findall("ss:c", NS):
                ref = c.attrib.get("r") or ""
                pos = _cell_ref_to_col_row(ref)
                if not pos:
                    continue
                col_i, _ = pos
                if col_i not in col_to_name:
                    continue
                v = c.find("ss:v", NS)
                if v is None:
                    continue
                val = v.text or ""
                if c.attrib.get("t") == "s":
                    try:
                        val = shared[int(val)]
                    except Exception:
                        pass
                cells[col_i] = (val or "").strip()

            word = (cells.get(_col_for(col_to_name, "word")) or "").strip()
            if not word:
                continue
            definition = (cells.get(_col_for(col_to_name, "definition")) or "").strip()
            dialect = (cells.get(_col_for(col_to_name, "dialect")) or "").strip().lower() or "unknown"
            sentiment = (cells.get(_col_for(col_to_name, "sentiment")) or "").strip().lower()
            if not sentiment:
                # unlabeled row -> skip
                continue
            rows.append(Row(word=word, dialect=dialect, sentiment=sentiment, definition=definition))
            if limit and len(rows) >= limit:
                break
        return rows


def _col_for(col_to_name: dict[int, str], name: str) -> int | None:
    for col, n in col_to_name.items():
        if n == name:
            return col
    return None


def _iter_inputs(inputs_csv: str) -> list[Path]:
    out: list[Path] = []
    for raw in (inputs_csv or "").split(","):
        p = Path(raw.strip())
        if not p:
            continue
        out.append(p)
    if not out:
        raise SystemExit("No inputs provided.")
    for p in out:
        if not p.exists():
            raise SystemExit(f"Input not found: {p}")
    return out


def _is_token_safe(token: str, *, min_len: int) -> bool:
    t = (token or "").strip().lower()
    if len(t) < min_len:
        return False
    if " " in t or "\t" in t:
        return False
    # Keep letters (including ñ) and hyphen only.
    return bool(re.fullmatch(r"[a-zñ]+(?:-[a-zñ]+)*", t))


def _build_token_freq_from_csv(csv_path: Path, *, cols: list[str]) -> Counter[str]:
    """
    Build a simple token frequency counter from a CSV file containing text fields.
    Used to filter Kaggle candidates to tokens that actually appear in a target corpus.
    """
    freq: Counter[str] = Counter()
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            parts: list[str] = []
            for c in cols:
                v = (row.get(c) or "").strip()
                if v:
                    parts.append(v)
            if not parts:
                continue
            text = " ".join(parts).lower()
            for tok in re.findall(r"[a-zñ]+(?:-[a-zñ]+)*", text, flags=re.IGNORECASE):
                t = tok.strip().lower()
                if t:
                    freq[t] += 1
    return freq


def main() -> None:
    ap = argparse.ArgumentParser(description="Convert Kaggle XLSX word sentiments into a VADER PH patch JSON.")
    ap.add_argument(
        "--inputs",
        default="archive/Tagalog Word Sentiments Full.xlsx,archive/PH Word Sentiments Full.xlsx",
        help="Comma-separated XLSX input paths (backend-relative if run from backend/).",
    )
    ap.add_argument(
        "--base",
        default="app/ml/vader_ph_lexicon.v1.json",
        help="Base patch JSON to extend (default: current v1 patch).",
    )
    ap.add_argument(
        "--out",
        default="app/ml/vader_ph_lexicon.v2.json",
        help="Output JSON path to write (default: v2).",
    )
    ap.add_argument(
        "--dialects",
        default="",
        help="Optional comma-separated dialect allowlist (matches the XLSX 'dialect' column). Default: allow all.",
    )
    ap.add_argument("--min-len", type=int, default=4, help="Minimum token length to include (default: 4).")
    ap.add_argument("--pos-weight", type=float, default=1.5, help="Valence score for positive tokens.")
    ap.add_argument("--neg-weight", type=float, default=-1.5, help="Valence score for negative tokens.")
    ap.add_argument(
        "--allow-overrides",
        action="store_true",
        help="Allow overriding tokens already present in the base patch (not recommended).",
    )
    ap.add_argument(
        "--filter-text-csv",
        default="",
        help=(
            "Optional CSV path used to filter candidates to tokens that appear in a target corpus "
            "(e.g., reports/benchmark_sample_2026-03-25_2026-03-31.csv)."
        ),
    )
    ap.add_argument(
        "--filter-text-cols",
        default="title,content",
        help="Comma-separated CSV columns to use as text fields for --filter-text-csv (default: title,content).",
    )
    ap.add_argument(
        "--min-freq",
        type=int,
        default=2,
        help="Minimum token frequency in --filter-text-csv required to keep a candidate (default: 2).",
    )
    ap.add_argument("--limit", type=int, default=0, help="Optional limit per XLSX for quick dry-runs.")
    args = ap.parse_args()

    backend_root = Path(__file__).resolve().parents[1]
    base_path = (backend_root / args.base).resolve() if not Path(args.base).is_absolute() else Path(args.base)
    out_path = (backend_root / args.out).resolve() if not Path(args.out).is_absolute() else Path(args.out)
    input_paths = [
        (backend_root / p).resolve() if not p.is_absolute() else p for p in _iter_inputs(args.inputs)
    ]

    base: dict[str, Any] = json.loads(base_path.read_text(encoding="utf-8"))
    base_lex: dict[str, Any] = dict(base.get("lexicon") or {})
    base_negations = {str(x).strip().lower() for x in (base.get("negations") or []) if str(x).strip()}
    base_boosters = {str(x).strip().lower() for x in (base.get("boosters") or []) if str(x).strip()}
    base_but_words = {str(x).strip().lower() for x in (base.get("but_words") or []) if str(x).strip()}

    # Conservative stop words (subset of Tagalog function words used by the router).
    stop_words = {
        "ang",
        "ng",
        "mga",
        "sa",
        "si",
        "ni",
        "kay",
        "kina",
        "nasa",
        "para",
        "dahil",
        "kasi",
        "pero",
        "ngunit",
        "subalit",
        "hindi",
        "wala",
        "huwag",
        "pang",
        "naman",
        "sana",
        "lang",
        "rin",
        "din",
        "pa",
        "raw",
        "daw",
        "umano",
        "ayon",
        "muna",
        "kayo",
        "kami",
        "tayo",
        "ito",
        "iyan",
        "yun",
        "yung",
    }

    sentiment_counts = Counter()
    per_dialect = Counter()

    dialect_allowlist = {d.strip().lower() for d in (args.dialects or "").split(",") if d.strip()}
    csv_freq: Counter[str] | None = None
    if (args.filter_text_csv or "").strip():
        csv_path = Path(args.filter_text_csv.strip())
        if not csv_path.is_absolute():
            csv_path = backend_root / csv_path
        if not csv_path.exists():
            raise SystemExit(f"--filter-text-csv not found: {csv_path}")
        cols = [c.strip() for c in (args.filter_text_cols or "").split(",") if c.strip()]
        if not cols:
            raise SystemExit("--filter-text-cols must list at least 1 column name")
        csv_freq = _build_token_freq_from_csv(csv_path, cols=cols)

    # Track conflicts: same word appears with both positive and negative labels.
    word_to_labels: dict[str, set[str]] = defaultdict(set)
    candidates: dict[str, float] = {}

    for p in input_paths:
        rows = _read_xlsx_rows(p, limit=args.limit or None)
        for r in rows:
            w = (r.word or "").strip().lower()
            s = (r.sentiment or "").strip().lower()
            d = (r.dialect or "").strip().lower()
            if dialect_allowlist and d not in dialect_allowlist:
                continue
            if s not in {"positive", "negative", "neutral"}:
                continue
            sentiment_counts[s] += 1
            per_dialect[d] += 1

            if not _is_token_safe(w, min_len=int(args.min_len)):
                continue
            if w in stop_words or w in base_negations or w in base_boosters or w in base_but_words:
                continue

            word_to_labels[w].add(s)

    for w, labels in word_to_labels.items():
        # Conflicts: skip completely.
        if "positive" in labels and "negative" in labels:
            continue
        # Neutral doesn't help VADER lexicon; skip.
        if labels == {"neutral"} or "neutral" in labels:
            continue

        if (not args.allow_overrides) and (w in base_lex):
            continue

        if "positive" in labels:
            candidates[w] = float(args.pos_weight)
        elif "negative" in labels:
            candidates[w] = float(args.neg_weight)

    kept_before_filter = len(candidates)
    if csv_freq is not None:
        min_freq = max(1, int(args.min_freq))
        candidates = {w: v for w, v in candidates.items() if int(csv_freq.get(w, 0)) >= min_freq}

    # Merge into base lexicon
    merged_lex = dict(base_lex)
    for w, v in sorted(candidates.items()):
        merged_lex[w] = v

    out: dict[str, Any] = dict(base)
    out["version"] = "ph_taglish_v2_kaggle_candidates"
    out["lexicon"] = merged_lex

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    added = len(merged_lex) - len(base_lex)
    skipped_existing = len([w for w in candidates.keys() if w in base_lex])
    print("=== Kaggle XLSX → VADER patch build ===")
    print(f"Base patch: {base_path}")
    print(f"Output:     {out_path}")
    print(f"Inputs:     {', '.join(str(p) for p in input_paths)}")
    print("")
    print(f"Labeled rows seen: {sum(sentiment_counts.values())} (pos={sentiment_counts['positive']}, neu={sentiment_counts['neutral']}, neg={sentiment_counts['negative']})")
    print(f"Dialects seen:     {len(per_dialect)} (top: {per_dialect.most_common(5)})")
    print("")
    print(f"Candidates generated: {len(candidates)}")
    if csv_freq is not None:
        print(f"Candidates before CSV filter: {kept_before_filter} (min_freq={int(args.min_freq)})")
    print(f"Added to lexicon:     {added}")
    print(f"Skipped existing:     {skipped_existing} (only relevant when --allow-overrides is set)")
    print("")
    print("Next: A/B test via evaluation script, e.g.:")
    print("  VADER_PH_PATCH=1 VADER_PH_PATCH_FILE=app/ml/vader_ph_lexicon.v2.json python scripts/evaluate_vader_ph_gold.py --model hybrid --ph-patch on")


if __name__ == "__main__":
    main()
