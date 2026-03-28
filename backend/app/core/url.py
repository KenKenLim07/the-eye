from __future__ import annotations

from urllib.parse import urlparse, urlunparse


def canonicalize_url(raw_url: str, *, force_https: bool = False) -> str:
    """
    Normalize URLs to reduce duplicate shapes.

    - lower-case hostname
    - strip query + fragment
    - trim trailing slash (except root)
    - optionally normalize http->https (force_https=True)
    """
    if not raw_url:
        return raw_url
    try:
        p = urlparse(str(raw_url))
        scheme = (p.scheme or "").lower()
        if force_https and scheme in ("http", "https"):
            scheme = "https"
        netloc = (p.netloc or "").lower()
        path = p.path or "/"
        if path != "/" and path.endswith("/"):
            path = path.rstrip("/")
        return urlunparse((scheme or p.scheme, netloc, path, "", "", ""))
    except Exception:
        return raw_url

