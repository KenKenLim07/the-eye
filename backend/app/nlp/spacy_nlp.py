from __future__ import annotations

import re
from typing import Dict, List, Tuple

import spacy

_nlp = None


def get_nlp():
    global _nlp
    if _nlp is None:
        # Lazy-load to keep startup fast
        _nlp = spacy.load("en_core_web_sm")
    return _nlp


def extract_entities(text: str) -> List[Dict[str, str]]:
    if not text:
        return []
    nlp = get_nlp()
    doc = nlp(text)
    entities: List[Dict[str, str]] = []
    for ent in doc.ents:
        entities.append({
            "text": ent.text,
            "label": ent.label_,
            "start": ent.start_char,
            "end": ent.end_char,
        })
    return entities


def extract_keyphrases(text: str, top_k: int = 10) -> List[str]:
    if not text:
        return []
    nlp = get_nlp()
    doc = nlp(text)
    # Simple noun-chunk based keyphrase extraction as a baseline
    phrases: Dict[str, int] = {}
    for chunk in doc.noun_chunks:
        cleaned = re.sub(r"\s+", " ", chunk.text.strip())
        if 3 <= len(cleaned) <= 80:
            phrases[cleaned] = phrases.get(cleaned, 0) + 1
    # Fallback: include frequent proper nouns
    for token in doc:
        if token.pos_ == "PROPN" and token.ent_type_:
            phrases[token.text] = phrases.get(token.text, 0) + 1
    ranked = sorted(phrases.items(), key=lambda x: x[1], reverse=True)
    return [p for p, _ in ranked[:top_k]]


