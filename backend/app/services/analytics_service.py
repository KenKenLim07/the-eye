from __future__ import annotations

import re


# Shared entity cleaning/canonicalization for both ranking and trends-correlation views.
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
ENTITY_CANONICAL_ALIASES = {
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
    "hong kong": ("Hong Kong", "GPE"),
    "southeast asia": ("Southeast Asia", "GPE"),
    "central visayas": ("Central Visayas", "GPE"),
    "ilocos sur": ("Ilocos Sur", "GPE"),
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
    "department of the interior and local government": (
        "Department of the Interior and Local Government",
        "ORG",
    ),
    "dpwh": ("Department of Public Works and Highways", "ORG"),
    "department of public works and highways": ("Department of Public Works and Highways", "ORG"),
    "pnp": ("Philippine National Police", "ORG"),
    "philippine national police": ("Philippine National Police", "ORG"),
    "afp": ("Armed Forces of the Philippines", "ORG"),
    "armed forces of the philippines": ("Armed Forces of the Philippines", "ORG"),
    "nbi": ("National Bureau of Investigation", "ORG"),
    "national bureau of investigation": ("National Bureau of Investigation", "ORG"),
    # Encoding variants observed in DB
    "malacaÃƒÂ±ang": ("Malacanang Palace", "ORG"),
    "malacaÃƒÂ£Ã‚Â±ang": ("Malacanang Palace", "ORG"),
    "malacaaÃ‚Â±ang": ("Malacanang Palace", "ORG"),
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


def _canonical_entity(text: str, label: str) -> tuple[str, str]:
    norm = _normalize_entity_text(text).replace("\u2019", "'")
    norm = norm.strip(".,;:!?()[]{}\"'")
    mapped = ENTITY_CANONICAL_ALIASES.get(norm)
    if mapped:
        canonical_text, forced_label = mapped
        return canonical_text, (forced_label or label)
    # Catch malformed encodings/variants of Malacanyang-like tokens.
    if norm.startswith("malaca") and norm.endswith("ang"):
        return "Malacanang Palace", "ORG"
    # Rule: labels like "Pasay City" should be geography, not org/person.
    if norm.endswith(" city"):
        return text.strip(), "GPE"
    return text.strip(), label


def clean_entity_for_counting(raw_text: str, label: str):
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
    # Phrase-level obvious noise for PERSON mislabels
    if canon_label == "PERSON":
        if norm_text.startswith("on ") or norm_text.startswith("the "):
            return None
        if any(tok in norm_text for tok in ("related", "read more", "loading")):
            return None
    # Drop short noisy ORG acronyms unless whitelisted.
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


def aggregate_entities_with_sentiment(
    analysis_rows,
    articles_by_id,
    exclude_set=None,
    max_entities: int = 100,
):
    from app.nlp.spacy_nlp import extract_entities as _extract_entities

    exclude_set = exclude_set or set()
    entity_stats = {}
    entity_display = {}
    seen_article_ids = set()

    for row in analysis_rows:
        aid = row.get("article_id")
        if not aid:
            continue
        a = articles_by_id.get(aid)
        if not a:
            continue
        if exclude_set and (a.get("source") or "").strip() in exclude_set:
            continue
        score = row.get("sentiment_score")
        if score is None:
            continue
        text = f"{a.get('title','')} {a.get('content','')}"
        try:
            ents = _extract_entities(text)
        except Exception:
            ents = []
        if ents:
            seen_article_ids.add(aid)
        for ent in ents:
            cleaned = clean_entity_for_counting(ent.get("text", ""), ent.get("label", ""))
            if not cleaned:
                continue
            norm_text, clean_label, display_text = cleaned
            key = (norm_text, clean_label)
            entity_display[key] = display_text
            stats = entity_stats.get(key) or {"mentions": 0, "sum_sent": 0.0}
            stats["mentions"] += 1
            stats["sum_sent"] += float(score)
            entity_stats[key] = stats

    top = sorted(
        [
            {
                "text": entity_display.get(k, _title_display(k[0])),
                "type": k[1],
                "mentions": v["mentions"],
                "avg_sentiment": (v["sum_sent"] / v["mentions"]) if v["mentions"] else 0.0,
            }
            for k, v in entity_stats.items()
        ],
        key=lambda x: (-x["mentions"], -abs(x["avg_sentiment"])),
    )[:max_entities]

    return top, len(seen_article_ids)
