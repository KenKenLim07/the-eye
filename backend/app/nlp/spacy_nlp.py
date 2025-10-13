from __future__ import annotations

import re
from typing import Dict, List, Tuple

import spacy
from spacy.util import is_package

_nlp = None


def get_nlp():
    global _nlp
    if _nlp is None:
        # Lazy-load; fall back to blank model if en_core_web_sm is unavailable
        try:
            _nlp = spacy.load("en_core_web_sm")
        except Exception:
            _nlp = spacy.blank("en")
    else:
        # If we previously loaded a blank pipeline, but the small model is now installed, upgrade live
        try:
            nlp_name = getattr(_nlp, "meta", {}).get("name")
        except Exception:
            nlp_name = None
        if (not nlp_name or nlp_name == "blank_en") and is_package("en_core_web_sm"):
            try:
                _nlp = spacy.load("en_core_web_sm")
            except Exception:
                pass
    # Ensure sentences are available even on blank models
    if _nlp and "senter" not in _nlp.pipe_names and "sentencizer" not in _nlp.pipe_names and not _nlp.has_factory("parser"):
        try:
            _nlp.add_pipe("sentencizer")
        except Exception:
            pass
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
    phrases: Dict[str, int] = {}
    # If parser isn't available (blank model), skip noun_chunks
    use_noun_chunks = doc.has_annotation("DEP") and hasattr(doc, "noun_chunks")
    if use_noun_chunks:
        for chunk in doc.noun_chunks:
            cleaned = re.sub(r"\s+", " ", chunk.text.strip())
            if 3 <= len(cleaned) <= 80:
                phrases[cleaned] = phrases.get(cleaned, 0) + 1
    # Proper noun sequences as a lightweight fallback
    current_seq: List[str] = []
    for token in doc:
        if token.pos_ == "PROPN" or (token.is_title and token.is_alpha):
            current_seq.append(token.text)
        else:
            if current_seq:
                key = " ".join(current_seq)
                phrases[key] = phrases.get(key, 0) + 1
                current_seq = []
    if current_seq:
        key = " ".join(current_seq)
        phrases[key] = phrases.get(key, 0) + 1
    ranked = sorted(phrases.items(), key=lambda x: x[1], reverse=True)
    return [p for p, _ in ranked[:top_k]]


