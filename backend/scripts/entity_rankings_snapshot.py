from __future__ import annotations

import os
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from zoneinfo import ZoneInfo

from supabase import Client, create_client
from postgrest.exceptions import APIError


# Allow importing backend "app" package when invoked from repo root.
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.nlp.spacy_nlp import extract_entities  # noqa: E402


ALLOWED_ENTITY_LABELS = {"PERSON", "ORG", "GPE", "NORP"}
ENTITY_STOP_TERMS = {
    # Filipino
    "sa",
    "ang",
    "ng",
    "mga",
    "kay",
    "si",
    "ni",
    "nasa",
    "mula",
    "para",
    "dahil",
    "kung",
    # Cebuano/Visayan
    "gikan",
    "uban",
    "alang",
    "tungod",
    "ug",
    "akong",
    "ako",
    "samtang",
    # Generic
    "first",
    "second",
    "third",
    "one",
    "two",
    "three",
    "four",
    "2024",
    "2025",
    "2026",
}
ENTITY_NOISY_TERMS = {
    "read",
    "related",
    "city",
    "ii",
    "iii",
    "iv",
    "vi",
    "vii",
    "viii",
    "ix",
    "x",
    "there",
    "at",
    "of",
    "and",
    "to",
    "from",
    "with",
    "day",
    "year",
    "check",
    "fact",
    "manila loading",
    "loading",
    "content",
    "view all",
    "newswire",
    "worldnews",
    "publication",
    "distribution",
    "contacts",
    "investors",
    "analysts",
    "press",
    "information",
    "contained",
    "herein",
    "release",
}
SHORT_ORG_WHITELIST = {
    "afp",
    "bir",
    "bsp",
    "coa",
    "dfa",
    "dilg",
    "doh",
    "doj",
    "dotr",
    "dpwh",
    "dti",
    "denr",
    "deped",
    "nbi",
    "pnp",
    "pdea",
    "comelec",
    "senate",
    "congress",
    "nba",
    "pba",
    "uaap",
    "fiba",
    "ofw",
    "owwa",
    "dmw",
}
GENERIC_ORG_TERMS = {
    "group",
    "information",
    "publication",
    "distribution",
    "contacts",
    "investors",
    "analysts",
    "press",
    "contained",
    "release",
    "newswire",
}
ENTITY_CANONICAL_ALIASES: Dict[str, Tuple[str, str]] = {
    # Geography
    "us": ("United States", "GPE"),
    "u.s.": ("United States", "GPE"),
    "u.s": ("United States", "GPE"),
    "usa": ("United States", "GPE"),
    "united states": ("United States", "GPE"),
    "the united states": ("United States", "GPE"),
    "united states of america": ("United States", "GPE"),
    "philippines": ("Philippines", "GPE"),
    "ph": ("Philippines", "GPE"),
    "republic of the philippines": ("Philippines", "GPE"),
    "the philippines": ("Philippines", "GPE"),
    "philippine": ("Philippines", "GPE"),
    "manila city": ("Manila", "GPE"),
    "city of manila": ("Manila", "GPE"),
    # Organizations
    "deped": ("Department of Education", "ORG"),
    "department of education": ("Department of Education", "ORG"),
    "doh": ("Department of Health", "ORG"),
    "department of health": ("Department of Health", "ORG"),
    "doj": ("Department of Justice", "ORG"),
    "department of justice": ("Department of Justice", "ORG"),
    "dotr": ("Department of Transportation", "ORG"),
    "department of transportation": ("Department of Transportation", "ORG"),
    "dilg": ("Department of the Interior and Local Government", "ORG"),
    "department of the interior and local government": ("Department of the Interior and Local Government", "ORG"),
    "dpwh": ("Department of Public Works and Highways", "ORG"),
    "department of public works and highways": ("Department of Public Works and Highways", "ORG"),
    "pnp": ("Philippine National Police", "ORG"),
    "philippine national police": ("Philippine National Police", "ORG"),
    "afp": ("Armed Forces of the Philippines", "ORG"),
    "armed forces of the philippines": ("Armed Forces of the Philippines", "ORG"),
    "nbi": ("National Bureau of Investigation", "ORG"),
    "national bureau of investigation": ("National Bureau of Investigation", "ORG"),
    "malacanang": ("Malacanang Palace", "ORG"),
    "palace": ("Malacanang Palace", "ORG"),
}


def _normalize_entity_text(text: str) -> str:
    return " ".join((text or "").strip().lower().split())


def _title_display(text: str) -> str:
    if not text:
        return text
    if text.islower() or text.isupper():
        return text.title()
    return text


def _canonical_entity(text: str, label: str) -> Tuple[str, str]:
    norm = _normalize_entity_text(text).replace("\u2019", "'")
    norm = norm.strip(".,;:!?()[]{}\"'")
    mapped = ENTITY_CANONICAL_ALIASES.get(norm)
    if mapped:
        canonical_text, forced_label = mapped
        return canonical_text, (forced_label or label)
    if norm.startswith("malaca") and norm.endswith("ang"):
        return "Malacanang Palace", "ORG"
    if norm.endswith(" city"):
        return text.strip(), "GPE"
    return text.strip(), label


def clean_entity_for_counting(raw_text: str, label: str) -> Optional[Tuple[str, str, str]]:
    if label not in ALLOWED_ENTITY_LABELS:
        return None
    if not raw_text:
        return None
    canon_text, canon_label = _canonical_entity(raw_text, label)
    norm_text = _normalize_entity_text(canon_text)
    if not norm_text:
        return None
    if norm_text in ENTITY_STOP_TERMS or norm_text in ENTITY_NOISY_TERMS:
        return None
    if canon_label == "PERSON":
        if norm_text.startswith("on ") or norm_text.startswith("the "):
            return None
        if any(tok in norm_text for tok in ("related", "read more", "loading")):
            return None
    if canon_label == "ORG":
        bare = re.sub(r"[^A-Za-z0-9]", "", norm_text)
        if len(bare) <= 2:
            return None
        if len(bare) <= 3 and bare not in SHORT_ORG_WHITELIST:
            return None
        if norm_text in GENERIC_ORG_TERMS:
            return None
    mapped = ENTITY_CANONICAL_ALIASES.get(norm_text)
    display = mapped[0] if mapped else _title_display(norm_text)
    return norm_text, canon_label, display


def window_bounds(period: str, include_today: bool = True) -> Tuple[str, str]:
    tz_ph = ZoneInfo("Asia/Manila")
    now_local = datetime.now(tz_ph)
    window_days = 30 if period == "30d" else 7
    if include_today:
        end_local = now_local.replace(hour=23, minute=59, second=59, microsecond=999999)
        start_local = (now_local - timedelta(days=window_days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        end_local = (now_local - timedelta(days=1)).replace(hour=23, minute=59, second=59, microsecond=999999)
        start_local = (end_local - timedelta(days=window_days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
    start_utc = start_local.astimezone(ZoneInfo("UTC"))
    end_utc = end_local.astimezone(ZoneInfo("UTC"))
    return start_utc.isoformat(), end_utc.isoformat()


def get_supabase() -> Client:
    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not url or not key:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")
    return create_client(url, key)


def fetch_articles_paginated(
    sb: Client,
    start_iso: str,
    end_iso: str,
    source: Optional[str],
    limit_per_batch: int = 1000,
) -> List[Dict[str, Any]]:
    all_articles: List[Dict[str, Any]] = []
    offset = 0
    while True:
        q = (
            sb.table("articles")
            .select("id,source,published_at,title,content")
            .gte("published_at", start_iso)
            .lte("published_at", end_iso)
            .order("published_at", desc=True)
            .range(offset, offset + limit_per_batch - 1)
        )
        if source:
            q = q.eq("source", source)
        res = q.execute()
        batch = res.data or []
        if not batch:
            break
        all_articles.extend(batch)
        offset += limit_per_batch
        if len(batch) < limit_per_batch:
            break
    return all_articles


def fetch_latest_sentiment_by_article(sb: Client, article_ids: List[int]) -> Dict[int, float]:
    latest: Dict[int, float] = {}
    batch_size = 2000
    for i in range(0, len(article_ids), batch_size):
        batch_ids = article_ids[i : i + batch_size]
        res = (
            sb.table("bias_analysis")
            .select("article_id,sentiment_score,model_type,created_at")
            .in_("article_id", batch_ids)
            .eq("model_type", "sentiment")
            .order("created_at", desc=True)
            .execute()
        )
        rows = res.data or []
        for row in rows:
            aid = row.get("article_id")
            if not aid or aid in latest:
                continue
            score = row.get("sentiment_score")
            if score is None:
                continue
            try:
                latest[int(aid)] = float(score)
            except Exception:
                continue
    return latest


@dataclass
class SnapshotParams:
    period: str
    source: Optional[str]
    include_today: bool
    scan_mode: str
    limit_articles: int
    total_cap: int
    max_entities: int

    @property
    def snapshot_key(self) -> str:
        return (
            f"entities:period={self.period}:"
            f"source={(self.source or 'all')}:"
            f"include_today={'1' if self.include_today else '0'}:"
            f"scan={self.scan_mode}:"
            f"limit={self.limit_articles}:"
            f"cap={self.total_cap}:"
            f"max={self.max_entities}"
        )


def compute_top_entities(
    articles: Iterable[Dict[str, Any]],
    sentiment_by_article_id: Dict[int, float],
    max_entities: int,
) -> Tuple[List[Dict[str, Any]], int]:
    # key: (norm_text, label) -> {mentions, sum_sent}
    stats: Dict[Tuple[str, str], Dict[str, float]] = defaultdict(lambda: {"mentions": 0.0, "sum_sent": 0.0})
    display: Dict[Tuple[str, str], str] = {}
    analyzed_articles = 0

    for a in articles:
        aid = a.get("id")
        if aid is None:
            continue
        try:
            aid_int = int(aid)
        except Exception:
            continue
        score = sentiment_by_article_id.get(aid_int)
        if score is None:
            continue
        text = f"{a.get('title', '')} {a.get('content', '')}"
        ents = []
        try:
            ents = extract_entities(text)
        except Exception:
            ents = []
        if ents:
            analyzed_articles += 1
        for ent in ents:
            cleaned = clean_entity_for_counting(ent.get("text", ""), ent.get("label", ""))
            if not cleaned:
                continue
            norm_text, clean_label, display_text = cleaned
            key = (norm_text, clean_label)
            display[key] = display_text
            s = stats[key]
            s["mentions"] += 1.0
            s["sum_sent"] += float(score)

    rows = []
    for k, v in stats.items():
        mentions = int(v["mentions"])
        if mentions <= 0:
            continue
        avg_sent = (v["sum_sent"] / v["mentions"]) if v["mentions"] else 0.0
        rows.append(
            {
                "text": display.get(k, _title_display(k[0])),
                "type": k[1],
                "mentions": mentions,
                "avg_sentiment": float(avg_sent),
            }
        )

    rows.sort(key=lambda x: (-x["mentions"], -abs(x["avg_sentiment"])))
    return rows[:max_entities], analyzed_articles


def write_snapshot(
    sb: Client,
    params: SnapshotParams,
    meta: Dict[str, Any],
    items: List[Dict[str, Any]],
) -> None:
    key = params.snapshot_key
    computed_at = datetime.now(timezone.utc).isoformat()
    snapshot_row = {
        "key": key,
        "period": params.period,
        "source": params.source,
        "include_today": params.include_today,
        "scan_mode": params.scan_mode,
        "limit_articles": params.limit_articles,
        "total_cap": params.total_cap,
        "max_entities": params.max_entities,
        "sampled": int(meta.get("sampled", 0)),
        "total_available": int(meta.get("total_available", 0)),
        "total_capped": int(meta.get("total_capped", 0)),
        "computed_at": computed_at,
    }

    try:
        sb.table("entity_rankings_snapshots").upsert(snapshot_row).execute()
    except APIError as e:
        payload = e.args[0] if e.args else None
        if isinstance(payload, dict) and payload.get("code") == "PGRST205":
            raise RuntimeError(
                "Supabase REST API can't see table public.entity_rankings_snapshots yet. "
                "If you just created the tables, run `select pg_notify('pgrst', 'reload schema');` "
                "in the Supabase SQL editor (or wait 1-2 minutes) and retry."
            ) from e
        raise

    sb.table("entity_rankings_items").delete().eq("snapshot_key", key).execute()

    insert_rows = []
    for e in items:
        insert_rows.append(
            {
                "snapshot_key": key,
                "entity_text": e["text"],
                "entity_type": e["type"],
                "mentions": int(e["mentions"]),
                "avg_sentiment": e.get("avg_sentiment", None),
            }
        )

    if insert_rows:
        sb.table("entity_rankings_items").insert(insert_rows).execute()


def run_snapshot(period: str) -> None:
    sb = get_supabase()
    params = SnapshotParams(
        period=period,
        source=None,
        include_today=True,
        scan_mode="fast",
        limit_articles=500,
        total_cap=1000,
        max_entities=100,
    )

    start_iso, end_iso = window_bounds(period, include_today=True)
    all_articles = fetch_articles_paginated(sb, start_iso, end_iso, source=None)
    total_available = len(all_articles)
    total_capped = min(total_available, max(1, params.total_cap))
    capped = all_articles[:total_capped]
    sample_cap = min(params.limit_articles, total_capped)
    sampled = capped[:sample_cap]

    articles_by_id = {int(a["id"]): a for a in sampled if a.get("id") is not None}
    article_ids = list(articles_by_id.keys())
    sentiments = fetch_latest_sentiment_by_article(sb, article_ids)

    top, analyzed_articles = compute_top_entities(
        articles=articles_by_id.values(),
        sentiment_by_article_id=sentiments,
        max_entities=params.max_entities,
    )

    meta = {
        "sampled": analyzed_articles,
        "sample_cap": sample_cap,
        "total_cap": params.total_cap,
        "total_available": total_available,
        "total_capped": total_capped,
        "scan_mode": params.scan_mode,
    }
    write_snapshot(sb, params=params, meta=meta, items=top)
    print(f"Wrote snapshot {params.snapshot_key} items={len(top)} analyzed_articles={analyzed_articles}")


def main(argv: List[str]) -> int:
    periods = ["7d", "30d"]
    if len(argv) >= 2:
        periods = [argv[1]]
    for p in periods:
        if p not in {"7d", "30d"}:
            raise SystemExit("period must be '7d' or '30d'")
        run_snapshot(p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
