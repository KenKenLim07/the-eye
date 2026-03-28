from __future__ import annotations

import logging
from typing import Iterable, List, Sequence, Set, Tuple

from app.core.supabase import get_supabase
from app.core.url import canonicalize_url

logger = logging.getLogger(__name__)


def unique_canonical_urls(urls: Iterable[str]) -> List[str]:
    """
    Canonicalize + de-duplicate URLs while preserving order.

    This should match the same canonicalization used by storage (`pipeline/store.py`)
    so scrapers skip duplicates early.
    """
    out: List[str] = []
    seen: Set[str] = set()
    for u in urls:
        if not u:
            continue
        cu = canonicalize_url(u)
        if not cu or cu in seen:
            continue
        seen.add(cu)
        out.append(cu)
    return out


def filter_existing_article_urls(urls: Sequence[str], *, chunk_size: int = 250) -> Tuple[List[str], Set[str]]:
    """
    Return (new_urls, existing_urls) based on `public.articles.url`.

    - Best-effort: if Supabase isn't configured, returns (urls, empty_set)
    - Chunks to avoid request size limits.
    """
    if not urls:
        return [], set()

    try:
        sb = get_supabase()
    except Exception as e:
        logger.warning("DB preflight unavailable (missing Supabase env?): %s", e)
        return list(urls), set()

    existing: Set[str] = set()
    for i in range(0, len(urls), chunk_size):
        chunk = list(urls[i : i + chunk_size])
        if not chunk:
            continue
        try:
            res = sb.table("articles").select("url").in_("url", chunk).execute()
            for row in (res.data or []):
                u = row.get("url")
                if u:
                    existing.add(str(u))
        except Exception as e:
            # Don't hard-fail scraping if the preflight check is down.
            logger.warning("DB preflight failed (continuing without it): %s", e)
            return list(urls), set()

    new_urls = [u for u in urls if u not in existing]
    return new_urls, existing

