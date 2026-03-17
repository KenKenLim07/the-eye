from typing import Callable, List, TypeVar
import re
import time
import random
from app.core.supabase import get_supabase
from .normalize import NormalizedArticle
from app.scrapers.utils import normalize_source, normalize_category
import logging
from urllib.parse import urlparse, urlunparse

logger = logging.getLogger(__name__)
T = TypeVar("T")


def _canonicalize_url(raw_url: str) -> str:
    """Normalize URLs to avoid duplicate shapes (strip query/fragment, lower host, trim trailing slash)."""
    if not raw_url:
        return raw_url
    try:
        p = urlparse(raw_url)
        # Lower-case hostname
        netloc = p.netloc.lower()
        # Remove query and fragment
        path = p.path or "/"
        # Trim trailing slash except for root
        if path != "/" and path.endswith("/"):
            path = path.rstrip("/")
        canon = urlunparse((p.scheme, netloc, path, "", "", ""))
        return canon
    except Exception:
        return raw_url


def _is_transient_network_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    transient_markers = [
        "temporary failure in name resolution",
        "name or service not known",
        "err_name_not_resolved",
        "connect timeout",
        "read timeout",
        "connection reset",
        "connection refused",
        "service unavailable",
        "502",
        "503",
        "504",
    ]
    return any(marker in msg for marker in transient_markers)


def _with_retries(fn: Callable[[], T], op_name: str, retries: int = 3, base_delay_s: float = 0.7) -> T:
    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            is_transient = _is_transient_network_error(exc)
            if (not is_transient) or attempt == retries:
                logger.error("%s failed (attempt %s/%s): %s", op_name, attempt, retries, exc)
                raise
            sleep_s = base_delay_s * (2 ** (attempt - 1)) + random.uniform(0.0, 0.25)
            logger.warning(
                "%s transient failure (attempt %s/%s): %s. Retrying in %.2fs",
                op_name, attempt, retries, exc, sleep_s
            )
            time.sleep(sleep_s)
    # Unreachable in normal control flow; keeps type-checkers happy.
    if last_exc is not None:
        raise last_exc
    raise RuntimeError(f"{op_name} failed unexpectedly")


def insert_articles(articles: List[NormalizedArticle]) -> dict:
    sb = get_supabase()
    # Canonicalize URLs up-front
    for a in articles:
        if getattr(a, "url", None):
            a.url = _canonicalize_url(a.url)
    # Filter out articles without URL (optional, but keeps DB clean)
    to_check = [a.url for a in articles if a.url]
    existing_urls: set[str] = set()
    
    # FIXED: Re-enable duplicate check with proper error handling
    duplicate_check_failed = False
    if to_check:
        try:
            res = _with_retries(
                lambda: sb.table('articles').select('url').in_('url', to_check).execute(),
                op_name="duplicate_check",
                retries=3,
            )
            existing_urls = set((row.get('url') for row in (res.data or []) if row.get('url')))
            logger.info(f'Duplicate check: {len(existing_urls)} existing URLs found out of {len(to_check)} checked')
        except Exception as e:
            duplicate_check_failed = True
            logger.warning(
                "Duplicate check unavailable (%s). Continuing with best-effort insert/upsert path.",
                e,
            )

    # Build rows and log skip reasons
    rows = []
    skipped = 0
    for a in articles:
        if not a.url:
            logger.info(f"Skip reason: missing_url | title='{a.title}'")
            skipped += 1
            continue
        if a.url in existing_urls:
            logger.info(f"Skip reason: duplicate_url | url={a.url}")
            skipped += 1
            continue

        rows.append({
            'source': normalize_source(a.source) or a.source,
            'category': normalize_category(a.category) if a.category else None,
            'raw_category': getattr(a, 'raw_category', None),
            'title': a.title,
            'url': a.url,
            'content': a.content,
            'published_at': a.published_at,
        })

    inserted = 0
    inserted_ids: list[int] = []
    error_msg = None
    
    if rows:
        try:
            if duplicate_check_failed:
                # Best-effort fallback path when duplicate pre-check is unavailable.
                # If a unique constraint exists on url, this avoids hard-failing the whole batch.
                ins = _with_retries(
                    lambda: sb.table('articles').upsert(rows, on_conflict='url', ignore_duplicates=True).execute(),
                    op_name="insert_articles_upsert_fallback",
                    retries=3,
                )
            else:
                ins = _with_retries(
                    lambda: sb.table('articles').insert(rows).execute(),
                    op_name="insert_articles",
                    retries=3,
                )
            data = ins.data or []
            inserted = len(data)
            inserted_ids = [int(r.get('id')) for r in data if r.get('id') is not None]
            logger.info(f'Successfully inserted {inserted} new articles')
        except Exception as e:
            error_msg = str(e)
            logger.error(f'Error inserting articles: {error_msg}')
            inserted_ids = []
            inserted = 0
    else:
        logger.info('No new articles to insert (all were duplicates or invalid)')

    result = {
        'checked': len(to_check),
        'skipped': skipped,
        'inserted': inserted,
        'inserted_ids': inserted_ids,
    }
    
    if error_msg:
        result['error'] = error_msg
        
    return result
