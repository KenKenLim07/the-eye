from __future__ import annotations

import re
from typing import Dict, List, Tuple

import spacy
from spacy.util import is_package

_nlp = None


def get_nlp():
    global _nlp
    if _nlp is None:
        # Lazy-load; never attempt runtime downloads in API path.
        # If en_core_web_sm is unavailable, fall back to blank English model.
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

    # Add PH-specific EntityRuler patterns to boost recall for local names/agencies
    try:
        if _nlp and "entity_ruler" not in _nlp.pipe_names:
            # Create ruler via add_pipe so it is properly registered in spaCy v3.
            insert_pos = {"before": "ner"} if "ner" in _nlp.pipe_names else {}
            ruler = _nlp.add_pipe("entity_ruler", config={"overwrite_ents": False}, **insert_pos)
            patterns = []
            # Key Philippine persons (recent and historical figures)
            persons = [
                "Ferdinand Marcos Jr.", "Bongbong Marcos", "Ferdinand R. Marcos Jr.",
                "Sara Duterte", "Rodrigo Duterte", "Leni Robredo", "Imee Marcos",
                "Manny Pacquiao", "Isko Moreno", "Alan Peter Cayetano", "Leila de Lima",
                "Gloria Macapagal Arroyo", "Benigno Aquino III", "Noynoy Aquino",
                "Mar Roxas", "Bam Aquino", "Risa Hontiveros", "Kiko Pangilinan",
                "Harry Roque", "Vic Rodriguez", "Martin Romualdez", "Juan Ponce Enrile",
                "Antonio Trillanes", "Chiz Escudero", "Grace Poe", "Imee Marcos",
                "Ronald Bato Dela Rosa", "Bato Dela Rosa", "Pantaleon Alvarez", "Edcel Lagman", "Cheloy Garafil",
                "Jesus Crispin Remulla", "Remulla", "Teodoro Herbosa", "Teddy Herbosa",
                "Ted Te", "Jose Manuel Diokno", "Chel Diokno", "Bam Aquino",
                "Imee Marcos", "Imee R. Marcos", "Imee R Marcos", "Vicente Sotto", "Tito Sotto",
                "Ralph Recto", "Francis Tolentino", "Nancy Binay", "JV Ejercito", "Jinggoy Estrada",
                "Joseph Estrada", "Erap Estrada", "Jejomar Binay", "Jojo Binay",
                "Franklin Drilon", "Aquino", "Arroyo", "Duterte"
            ]
            for name in persons:
                patterns.append({"label": "PERSON", "pattern": name})

            # Government agencies / institutions / offices
            orgs = [
                "DPWH", "Department of Public Works and Highways",
                "DBM", "Department of Budget and Management",
                "DILG", "Department of the Interior and Local Government",
                "DOH", "Department of Health",
                "DepEd", "Department of Education",
                "DOTr", "Department of Transportation", "DOTR",
                "DOJ", "Department of Justice",
                "DA", "Department of Agriculture",
                "DTI", "Department of Trade and Industry",
                "DENR", "Department of Environment and Natural Resources",
                "COA", "Commission on Audit",
                "COMELEC", "Commission on Elections",
                "NBI", "National Bureau of Investigation",
                "PNP", "Philippine National Police",
                "AFP", "Armed Forces of the Philippines",
                "Ombudsman", "Office of the Ombudsman",
                "Sandiganbayan", "Supreme Court", "Court of Appeals",
                "Senate", "House of Representatives", "Congress",
                "Malacañang", "Malacanang", "Palace",
                "BIR", "Bureau of Internal Revenue", "BSP", "Bangko Sentral ng Pilipinas",
                "DPWH-CAR", "MMDA", "Metro Manila Development Authority"
            ]
            for org in orgs:
                patterns.append({"label": "ORG", "pattern": org})

            # Parties / NORP
            norps = [
                "PDP-Laban", "PDP–Laban", "Liberal Party", "Nacionalista Party",
                "Nationalist People's Coalition", "NPC", "United Nationalist Alliance",
                "UNA", "Lakas–CMD", "Lakas-CMD", "Aksyon Demokratiko",
                "Makabayan Bloc", "Bayan Muna", "Gabriela"
            ]
            for n in norps:
                patterns.append({"label": "NORP", "pattern": n})

            # Add patterns to active ruler
            ruler.add_patterns(patterns)
    except Exception:
        # Non-fatal if patterns cannot be added
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
    if entities:
        return entities

    # Heuristic fallback when only blank model is available or no entities are produced.
    # Keeps trends entity analytics usable for operational/thesis summaries.
    fallback: List[Dict[str, str]] = []
    seen = set()
    org_tokens = {
        "department", "bureau", "commission", "office", "university", "bank",
        "ministry", "council", "agency", "court", "senate", "congress",
        "inc", "corp", "corporation", "authority", "administration",
    }
    gpe_terms = {
        "philippines", "manila", "cebu", "davao", "quezon", "makati", "pasig",
        "taguig", "iloilo", "bacolod", "zamboanga", "mindanao", "luzon", "visayas",
        "middle east", "metro manila", "quezon city", "united states", "the united states",
        "united states of america", "america", "new zealand", "south korea",
        "saudi arabia", "united arab emirates", "israel", "iran", "qatar", "jordan",
    }
    gpe_acronyms = {"US", "USA", "UAE", "UK", "PH"}
    gpe_upper_words = {"MANILA", "CEBU", "DAVAO", "BAGUIO", "PASIG", "TAGUIG", "MAKATI"}

    # Acronyms (ORG-like)
    for m in re.finditer(r"\b[A-Z]{2,}(?:-[A-Z]{2,})?\b", text):
        t = m.group(0).strip()
        if t in {"THE", "AND", "FOR", "WITH"}:
            continue
        label = "GPE" if t in gpe_acronyms or t in gpe_upper_words else "ORG"
        key = (t, label)
        if key in seen:
            continue
        seen.add(key)
        fallback.append({"text": t, "label": label, "start": m.start(), "end": m.end()})

    # Title-cased multi-word phrases (PERSON/ORG/GPE guess)
    for m in re.finditer(r"\b(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b", text):
        t = m.group(0).strip()
        low = t.lower()
        label = "PERSON"
        if any(tok in low.split() for tok in org_tokens):
            label = "ORG"
        elif low in gpe_terms or low.endswith(" city"):
            label = "GPE"
        key = (t, label)
        if key in seen:
            continue
        seen.add(key)
        fallback.append({"text": t, "label": label, "start": m.start(), "end": m.end()})
        if len(fallback) >= 30:
            break

    return fallback


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


