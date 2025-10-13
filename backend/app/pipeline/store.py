from typing import List
import re
import os
from app.core.supabase import get_supabase
from .normalize import NormalizedArticle
from app.scrapers.utils import normalize_source, normalize_category
import logging
from urllib.parse import urlparse, urlunparse

logger = logging.getLogger(__name__)

# spaCy integration for enhanced funds detection
_nlp = None
USE_SPACY_FUNDS = os.getenv("USE_SPACY_FUNDS", "false").lower() == "true"

def _get_spacy_nlp():
    """Lazy load spaCy model for funds detection; reuse shared app.nlp.spacy_nlp pipeline when available."""
    global _nlp
    if not USE_SPACY_FUNDS:
        return False
    if _nlp is None:
        try:
            # Reuse the central loader so it can auto-upgrade to en_core_web_sm
            from app.nlp.spacy_nlp import get_nlp as get_shared_nlp
            base_nlp = get_shared_nlp()
            # Attach an EntityRuler with PH-specific patterns if not already present
            if "entity_ruler" not in base_nlp.pipe_names:
                from spacy.pipeline import EntityRuler
                ruler = EntityRuler(base_nlp, overwrite_ents=False)
                patterns = []
                # Government agencies and bodies (common acronyms and names)
                gov_terms = [
                    "DPWH","DBM","COA","COMELEC","DILG","DOH","DepEd","DOTr","DOTR","Senate","House","Congress","LGU",
                    "barangay","province","city","municipality","Malacañang","Palace","Ombudsman","Commission on Audit",
                    "Department of Public Works and Highways","Department of Budget and Management","Department of Health",
                    "Department of Education","Department of the Interior and Local Government","Department of Transportation"
                ]
                for term in gov_terms:
                    patterns.append({"label": "ORG", "pattern": term})
                # Money cues
                money_terms = ["budget","allocation","appropriation","disbursement","fund","funds","billion","million","trillion","pesos","peso","PHP","Php","₱"]
                for term in money_terms:
                    patterns.append({"label": "MONEY", "pattern": term})
                ruler.add_patterns(patterns)
                base_nlp.add_pipe(ruler, name="entity_ruler", before="ner" if "ner" in base_nlp.pipe_names else None)
            _nlp = base_nlp
            logger.info("spaCy funds pipeline initialized with EntityRuler")
        except Exception as e:
            logger.warning(f"Failed to initialize spaCy funds pipeline: {e}. Falling back to regex-only detection.")
            _nlp = False
    return _nlp

def _spacy_funds_analysis(text: str) -> dict:
    """Enhanced funds detection using spaCy NER and entity recognition"""
    nlp = _get_spacy_nlp()
    if not nlp:
        return {"is_funds": None, "entities": [], "confidence": 0.0}
    
    try:
        # Truncate very long content for performance
        if len(text) > 3000:
            text = text[:3000]
        
        doc = nlp(text)
        
        # Extract relevant entities
        entities = {
            "orgs": [],  # Organizations (DPWH, DBM, etc.)
            "gpes": [],  # Geopolitical entities (Philippines, cities)
            "money": [], # Money amounts
            "laws": []   # Legal documents, bills
        }
        
        for ent in doc.ents:
            if ent.label_ == "ORG":
                entities["orgs"].append(ent.text.lower())
            elif ent.label_ == "GPE":
                entities["gpes"].append(ent.text.lower())
            elif ent.label_ == "MONEY":
                entities["money"].append(ent.text.lower())
            elif ent.label_ == "LAW":
                entities["laws"].append(ent.text.lower())
        
        # Check for Philippine government entities
        ph_gov_terms = {
            "dpwh", "dbm", "coa", "comelec", "dilg", "doh", "deped", "dotr", 
            "senate", "house", "congress", "lgu", "barangay", "province", 
            "city", "municipality", "national", "government", "public"
        }
        
        # Check for corruption/funds terms
        corruption_terms = {
            "pork", "kickback", "anomaly", "graft", "plunder", "misuse", 
            "overprice", "scam", "whistleblower", "audit", "appropriation",
            "budget", "allocation", "disbursement", "fund", "billion", "million"
        }
        
        # Check for negative contexts
        negative_terms = {
            "shabu", "buy-bust", "drug", "narcotics", "basketball", "volleyball",
            "football", "soccer", "nba", "pba", "tournament", "match", "game"
        }
        
        # Analyze entity overlap
        all_text = text.lower()
        found_gov = any(term in all_text for term in ph_gov_terms)
        found_corruption = any(term in all_text for term in corruption_terms)
        found_negative = any(term in all_text for term in negative_terms)
        
        # Enhanced decision logic
        if found_negative:
            return {"is_funds": False, "entities": entities, "confidence": 0.9}
        
        if found_gov and found_corruption:
            return {"is_funds": True, "entities": entities, "confidence": 0.8}
        
        # Check for money + government context
        if entities["money"] and (found_gov or any(org in ph_gov_terms for org in entities["orgs"])):
            return {"is_funds": True, "entities": entities, "confidence": 0.7}
        
        return {"is_funds": False, "entities": entities, "confidence": 0.3}
        
    except Exception as e:
        logger.error(f"spaCy analysis failed: {e}")
        return {"is_funds": None, "entities": [], "confidence": 0.0}


# Enhanced patterns for better accuracy - focused on Philippine government funds
MONEY = r"(fund|budget|appropriation|allocation|disbursement|audit|coa|\\bphp\\b|billion|million|trillion|peso|pesos)"
# More specific Philippine government terms - avoid generic terms
PH_GOVERNMENT = r"(philippine|ph|dpwh|dbm|coa|comelec|dilg|doh|deped|dotr|senate|house|congress|solon|lawmaker|bill|appropriation|budget|malacañang|palace|president|vice president|ombudsman|philippines|filipino|philippine\s+government|ph\s+government)"
CORRUPTION = r"(pork|kickback|anomaly|graft|plunder|misuse|overprice|overpriced|scam|whistleblower)"

# Enhanced negative patterns to filter out disasters and non-funds content
SPORTS = r"(basketball|volleyball|football|soccer|nba|pba|uaap|ncaa|tournament|match|game|coach|player|club)"
CRIME = r"(shabu|buy-bust|drug|narcotics|illegal\s+drugs|anti-drug|meth|pdea)"
# More specific disaster patterns - avoid blocking legitimate government terms
DISASTERS = r"(earthquake|typhoon|hurricane|natural\s+disaster|magnitude|aftershock|tsunami|landslide|volcano|eruption|storm|cyclone|tornado|flash\s+flood|flooding\s+incident)"
DAMAGE = r"(damage|damages|destroyed|collapsed|injured|killed|deaths|casualties|evacuated|displaced|affected|victims|property\s+damage)"

# More precise positive pattern - requires BOTH money AND Philippine government context
POSITIVE_PATTERN = re.compile(fr"(?=.*{MONEY}).*(?:{PH_GOVERNMENT}|{CORRUPTION})", re.IGNORECASE | re.DOTALL)
# Enhanced negative pattern - filters out disasters, sports, and crime
NEGATIVE_PATTERN = re.compile(fr"(?:{SPORTS})|(?:{CRIME})|(?:{DISASTERS})|(?:{DAMAGE})", re.IGNORECASE)

def classify_is_funds(title: str | None, content: str | None) -> bool:
    """Enhanced funds classification with improved accuracy"""
    text = ((title or "") + "\n" + (content or "")).strip()
    
    if not text.strip():
        return False
    
    text_lower = text.lower()
    
    # First pass: Check for negative patterns (disasters, sports, crime)
    if NEGATIVE_PATTERN.search(text_lower):
        return False
    
    # Second pass: Check for positive patterns (money + government/corruption)
    regex_decision = bool(POSITIVE_PATTERN.search(text_lower))
    
    # Third pass: spaCy analysis (if enabled and available)
    if USE_SPACY_FUNDS:
        spacy_result = _spacy_funds_analysis(text)
        
        # If spaCy has a confident decision, use it
        if spacy_result["is_funds"] is not None and spacy_result["confidence"] > 0.6:
            return spacy_result["is_funds"]
        
        # If regex says yes but spaCy is uncertain, be more conservative
        if regex_decision and spacy_result["confidence"] < 0.5:
            return False
    
    # Additional validation: Check for disaster-related money mentions
    if regex_decision:
        # If it mentions money but also disaster terms, be more careful
        disaster_money_pattern = re.compile(rf"(?:{DISASTERS}).*{MONEY}|{MONEY}.*{DISASTERS}", re.IGNORECASE)
        if disaster_money_pattern.search(text_lower):
            # Only classify as funds if it also mentions government/corruption
            gov_corruption_pattern = re.compile(rf"(?:{PUBLIC_SECTOR}|{CORRUPTION})", re.IGNORECASE)
            if not gov_corruption_pattern.search(text_lower):
                return False
    
    return regex_decision

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
            'is_funds': classify_is_funds(a.title, a.content),
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
