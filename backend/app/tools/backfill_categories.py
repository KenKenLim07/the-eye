import os
import sys
import re
import argparse
from typing import Tuple, Optional, Dict, Any, List

# Reuse existing Supabase client factory
try:
    from app.core.supabase import get_supabase
except Exception as e:
    print("ERROR: cannot import get_supabase from app.core.supabase:", e, file=sys.stderr)
    sys.exit(1)

GENERIC_BAD_CATEGORIES = {
    None,
    "",
    "Post",
    "General",
    "Uncategorized",
}

# -----------------------------
# URL category resolvers per source
# -----------------------------

def resolve_gma(url: str) -> Tuple[str, Optional[str]]:
    if "/news/topstories/" in url:
        # try sub-category
        m = re.search(r"/news/topstories/([^/]+)/", url)
        if m:
            sub = m.group(1).lower()
            return _map_common(sub)
        return ("News", "News")
    m = re.search(r"/news/([^/]+)/", url)
    if m:
        return _map_common(m.group(1).lower())
    return ("News", None)

def resolve_philstar(url: str) -> Tuple[str, Optional[str]]:
    m = re.search(r"https?://[^/]+/(\w+)/", url)
    if m:
        return _map_common(m.group(1).lower())
    return ("News", None)

def resolve_rappler(url: str) -> Tuple[str, Optional[str]]:
    # use first path segment
    m = re.search(r"https?://[^/]+/(\w+)/", url)
    if m:
        return _map_common(m.group(1).lower())
    return ("News", None)

def resolve_sunstar(url: str) -> Tuple[str, Optional[str]]:
    # city-first structure; map cities to Nation and store raw city
    m = re.search(r"https?://[^/]+/([^/]+)/([^/]+)/", url)
    if m:
        city = m.group(1).lower()
        section = m.group(2).lower()
        norm, raw = _map_common(section)
        if norm == "News" or norm == "General":
            return ("Nation", city.replace('-', ' ').title())
        return (norm, raw)
    return ("Nation", None)

def resolve_manila_bulletin(url: str) -> Tuple[str, Optional[str]]:
    m = re.search(r"https?://[^/]+/(\w+)/", url)
    if m:
        return _map_common(m.group(1).lower())
    return ("News", None)

def resolve_manila_times(url: str) -> Tuple[str, Optional[str]]:
    # look for known sections anywhere in path
    for key in [
        "business","sports","opinion","world","regions","politics",
        "lifestyle","entertainment","top-business","foreign-business",
        "top-sports","columns","the-sunday-times","news","top-news",
    ]:
        if f"/{key}/" in url:
            return _map_common(key)
    return ("News", None)

SECTION_MAP = {
    "news": "News",
    "top-news": "News",
    "headlines": "News",
    "business": "Business",
    "top-business": "Business",
    "foreign-business": "Business",
    "sports": "Sports",
    "top-sports": "Sports",
    "opinion": "Opinion",
    "columns": "Opinion",
    "editorial": "Opinion",
    "world": "World",
    "regions": "Nation",
    "nation": "Nation",
    "politics": "Politics",
    "lifestyle": "Lifestyle",
    "entertainment": "Entertainment",
    "metro": "Metro",
    "technology": "Technology",
    "tech": "Technology",
    "health": "Health",
    "education": "Education",
}

def _map_common(segment: str) -> Tuple[str, Optional[str]]:
    seg = (segment or "").lower()
    norm = SECTION_MAP.get(seg)
    if norm:
        return (norm, seg.replace('-', ' ').title())
    return ("News", None)

RESOLVERS = {
    "GMA": resolve_gma,
    "PhilStar": resolve_philstar,
    "Rappler": resolve_rappler,
    "Sunstar": resolve_sunstar,
    "Manila Bulletin": resolve_manila_bulletin,
    "Manila Times": resolve_manila_times,
}

# -----------------------------
# Backfill driver
# -----------------------------

def fetch_candidates(sb, source: Optional[str], limit: int, offset: int) -> List[Dict[str, Any]]:
    q = sb.table("articles").order("inserted_at", desc=True)
    if source:
        q = q.eq("source", source)
    # missing or generic
    q = q.or_(
        ",".join([
            "category.is.null",
            "category.eq.Post",
            "category.eq.General",
            "category.eq.Uncategorized",
        ])
    )
    q = q.range(offset, offset + limit - 1)
    res = q.execute()
    return res.data or []

def backfill_batch(sb, rows: List[Dict[str, Any]], dry_run: bool) -> Tuple[int,int]:
    updated = 0
    skipped = 0
    for r in rows:
        url = r.get("url") or ""
        source = r.get("source")
        resolver = RESOLVERS.get(source)
        if not resolver or not url:
            skipped += 1
            continue
        norm, raw = resolver(url)
        if not norm:
            skipped += 1
            continue
        # If norm is still very generic and we had a previous non-empty category, skip
        if norm in {"News", "General"} and (r.get("category") and r.get("category").strip()):
            skipped += 1
            continue
        if dry_run:
            updated += 1
        else:
            sb.table("articles").update({
                "category": norm,
                "raw_category": raw,
            }).eq("id", r["id"]).execute()
            updated += 1
    return updated, skipped


def main():
    parser = argparse.ArgumentParser(description="Backfill article categories using URL-based rules")
    parser.add_argument("--source", help="Limit to a single source label (e.g., 'PhilStar')", default=None)
    parser.add_argument("--limit", type=int, default=500, help="Batch size per fetch")
    parser.add_argument("--offset", type=int, default=0, help="Offset for paging")
    parser.add_argument("--dry-run", action="store_true", help="Do not write changes, only report counts")
    args = parser.parse_args()

    sb = get_supabase()

    rows = fetch_candidates(sb, args.source, args.limit, args.offset)
    print(f"Candidates fetched: {len(rows)} (source={args.source or 'ALL'}, limit={args.limit}, offset={args.offset})")
    if not rows:
        return

    updated, skipped = backfill_batch(sb, rows, args.dry_run)
    print(f"Updated: {updated}, Skipped: {skipped}, Dry-run: {args.dry_run}")

if __name__ == "__main__":
    main() 