from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


_INQUIRER_BOILERPLATE_PHRASES = (
    "By providing an email address.",
    "I agree to the Terms of Use",
    "acknowledge that I have read the Privacy Policy",
)
_INQUIRER_MARKER = "By providing an email address."

_READ_LINK_RE = re.compile(
    r"(?:(?:^|\s)(?:READ(?:\s+MORE)?|WRAP|WATCH)\s*:\s*[^\n]{0,200})",
    flags=re.IGNORECASE,
)

_DATELINE_MANILA_RE = re.compile(r"(?m)^MANILA\s*(?:—|--|-)\s+")
_DATELINE_MANILA_ANY_RE = re.compile(r"MANILA\s*(?:—|--|-)\s+", flags=0)


@dataclass(frozen=True)
class CleanMeta:
    enabled: bool
    input_len: int
    output_len: int
    removed_read_links: int
    removed_boilerplate_paragraphs: int
    removed_duplicate_paragraphs: int
    truncated_at_second_dateline: bool
    truncated_on_repeat_prefix: bool
    truncated_at_inquirer_marker: bool


def _normalize_line_endings(s: str) -> str:
    return (s or "").replace("\r\n", "\n").replace("\r", "\n")


def _is_inquirer_boilerplate(paragraph: str) -> bool:
    p = (paragraph or "").strip()
    if not p:
        return False
    for phrase in _INQUIRER_BOILERPLATE_PHRASES:
        if phrase in p:
            return True
    return False


def _dedupe_paragraphs(paragraphs: list[str]) -> tuple[list[str], int]:
    """
    Drop exact duplicate paragraphs (case/whitespace-insensitive).
    This is common when a scraper accidentally concatenates an article twice.
    """
    seen: set[str] = set()
    out: list[str] = []
    removed = 0

    for p in paragraphs:
        raw = (p or "").strip()
        if not raw:
            continue
        key = re.sub(r"\s+", " ", raw).strip().lower()
        # Only dedupe "meaningful" paragraphs to avoid dropping headings like "MANILA —".
        if len(key) >= 80 and key in seen:
            removed += 1
            continue
        seen.add(key)
        out.append(raw)

    return out, removed


def _truncate_at_second_manila_dateline(text: str, *, min_second_pos: int = 800) -> tuple[str, bool]:
    """
    Heuristic: if a scraped article contains multiple MANILA datelines, it's often
    concatenated with another story. Keep only the first story.

    This intentionally targets the most common PH-news pattern and avoids applying
    a broad "all caps dateline" rule that could truncate legitimate content.
    """
    s = text or ""
    hits = list(_DATELINE_MANILA_RE.finditer(s))
    if len(hits) >= 2:
        second_pos = hits[1].start()
    else:
        hits_any = list(_DATELINE_MANILA_ANY_RE.finditer(s))
        if len(hits_any) < 2:
            return s, False
        second_pos = hits_any[1].start()

    if second_pos < min_second_pos:
        return s, False

    return s[:second_pos].rstrip(), True


def _truncate_on_repeat_prefix(text: str, *, prefix_len: int = 400, min_second_pos: int = 1200) -> tuple[str, bool]:
    """
    Heuristic: if the exact prefix of the article appears again later,
    the scraper likely concatenated the same story twice. Truncate at the repeat.
    """
    s = text or ""
    if len(s) < (min_second_pos + prefix_len):
        return s, False
    prefix = s[:prefix_len]
    if not prefix.strip():
        return s, False
    idx = s.find(prefix, prefix_len)
    if idx >= min_second_pos:
        return s[:idx].rstrip(), True
    return s, False


def clean_scraped_news_text(text: str, *, enabled: bool = True) -> tuple[str, CleanMeta]:
    """
    Conservative cleanup for scraped news text used in evaluation/reporting:
    - remove cross-link boilerplate like "READ: ..."
    - remove repeated Inquirer consent/terms boilerplate paragraphs
    - drop exact duplicate paragraphs (common scrape bug)
    - truncate obvious multi-article concatenations (MANILA dateline repeats)

    This is not intended to "improve" sentiment; it's intended to remove scraper noise.
    """
    raw = _normalize_line_endings(text or "")
    if not enabled:
        return raw, CleanMeta(
            enabled=False,
            input_len=len(raw),
            output_len=len(raw),
            removed_read_links=0,
            removed_boilerplate_paragraphs=0,
            removed_duplicate_paragraphs=0,
            truncated_at_second_dateline=False,
            truncated_on_repeat_prefix=False,
            truncated_at_inquirer_marker=False,
        )

    # Remove inline READ:/WRAP:/WATCH: cross-links (keep surrounding text).
    removed_read_links = len(_READ_LINK_RE.findall(raw))
    cleaned = _READ_LINK_RE.sub(" ", raw)

    # Inquirer pages often embed consent/terms boilerplate multiple times and can even
    # re-print the article after those blocks. The phrase below is a strong marker that
    # is not part of the article text; truncate at the first occurrence to keep the
    # first (usually complete) article.
    truncated_inquirer = False
    marker_pos = cleaned.find(_INQUIRER_MARKER)
    if marker_pos >= 0 and marker_pos > 200:
        cleaned = cleaned[:marker_pos].rstrip()
        truncated_inquirer = True

    # Paragraph-level filtering (boilerplate + dedupe).
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", cleaned) if (p or "").strip()]
    kept: list[str] = []
    removed_boilerplate = 0
    for p in paragraphs:
        # Only drop *pure* boilerplate paragraphs. If a paragraph contains boilerplate
        # markers but is long, keep it (we already truncated at the first marker above).
        if len(p) < 500 and _is_inquirer_boilerplate(p):
            removed_boilerplate += 1
            continue
        kept.append(p)

    kept, removed_dupes = _dedupe_paragraphs(kept)
    cleaned = "\n\n".join(kept).strip()

    cleaned, truncated = _truncate_at_second_manila_dateline(cleaned)
    cleaned, truncated_prefix = _truncate_on_repeat_prefix(cleaned)

    return cleaned, CleanMeta(
        enabled=True,
        input_len=len(raw),
        output_len=len(cleaned),
        removed_read_links=removed_read_links,
        removed_boilerplate_paragraphs=removed_boilerplate,
        removed_duplicate_paragraphs=removed_dupes,
        truncated_at_second_dateline=truncated,
        truncated_on_repeat_prefix=truncated_prefix,
        truncated_at_inquirer_marker=truncated_inquirer,
    )


def clean_scraped_news_text_maybe(text: str) -> str:
    """
    Convenience wrapper for pipelines that want a string-only API.
    """
    cleaned, _ = clean_scraped_news_text(text, enabled=True)
    return cleaned
