from typing import List
from app.core.supabase import get_supabase
from .normalize import NormalizedArticle
from app.scrapers.utils import normalize_source, normalize_category
import logging
from urllib.parse import urlparse, urlunparse

logger = logging.getLogger(__name__)


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
    if to_check:
        try:
            res = sb.table('articles').select('url').in_('url', to_check).execute()
            existing_urls = set((row.get('url') for row in (res.data or []) if row.get('url')))
            logger.info(f'Duplicate check: {len(existing_urls)} existing URLs found out of {len(to_check)} checked')
        except Exception as e:
            logger.error(f'Error checking existing URLs: {e}')
            return {'checked': 0, 'skipped': 0, 'inserted': 0, 'error': str(e), 'inserted_ids': []}

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
            ins = sb.table('articles').insert(rows).execute()
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
