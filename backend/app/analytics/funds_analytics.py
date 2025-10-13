#!/usr/bin/env python3
"""
Senior Dev: Advanced Funds Analytics with spaCy
Extract structured data from funds articles for analytics
"""
import os
import re
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime

# spaCy integration
_nlp = None
USE_SPACY_ANALYTICS = os.getenv("USE_SPACY_ANALYTICS", "false").lower() == "true"

@dataclass
class FundsEntity:
    """Structured entity extracted from funds articles"""
    entity_type: str  # "agency", "amount", "project", "location", "person"
    text: str
    confidence: float
    context: str  # surrounding text
    position: int  # character position

@dataclass
class FundsAnalytics:
    """Complete analytics data for a funds article"""
    article_id: int
    title: str
    content: str
    published_at: str
    
    # Extracted entities
    agencies: List[FundsEntity]
    amounts: List[FundsEntity]
    projects: List[FundsEntity]
    locations: List[FundsEntity]
    people: List[FundsEntity]
    
    # Enhanced entities (spaCy-specific)
    contractors: List[str] = None
    project_locations: List[str] = None
    
    # Analytics metrics
    total_amount: Optional[float] = None
    primary_agency: Optional[str] = None
    project_types: List[str] = None
    corruption_indicators: List[str] = None
    
    # Confidence scores
    extraction_confidence: float = 0.0
    funds_relevance_score: float = 0.0

def _get_spacy_nlp():
    """Lazy load spaCy model for analytics"""
    global _nlp
    if _nlp is None and USE_SPACY_ANALYTICS:
        try:
            import spacy
            _nlp = spacy.load("en_core_web_sm")
            print("✅ spaCy model loaded for funds analytics")
        except Exception as e:
            print(f"⚠️ Failed to load spaCy model: {e}")
            _nlp = False
    return _nlp

def extract_funds_analytics(article_id: int, title: str, content: str, published_at: str) -> FundsAnalytics:
    """Extract comprehensive analytics from a funds article"""
    
    # Initialize analytics object
    analytics = FundsAnalytics(
        article_id=article_id,
        title=title,
        content=content,
        published_at=published_at,
        agencies=[],
        amounts=[],
        projects=[],
        locations=[],
        people=[],
        contractors=[],
        project_locations=[],
        project_types=[],
        corruption_indicators=[]
    )
    
    # Combine title and content for analysis
    full_text = f"{title}\n{content}"
    
    if USE_SPACY_ANALYTICS:
        analytics = _extract_with_spacy(full_text, analytics)
    else:
        analytics = _extract_with_regex(full_text, analytics)
    
    # Calculate derived metrics
    analytics = _calculate_derived_metrics(analytics)
    
    return analytics

def _extract_with_spacy(text: str, analytics: FundsAnalytics) -> FundsAnalytics:
    """Extract entities using spaCy NER with custom patterns"""
    nlp = _get_spacy_nlp()
    if not nlp:
        return analytics
    
    try:
        # Add custom patterns for Philippine government entities
        _add_custom_patterns(nlp)
        
        doc = nlp(text)
        
        # Extract entities by type
        for ent in doc.ents:
            entity = FundsEntity(
                entity_type=ent.label_.lower(),
                text=ent.text,
                confidence=ent._.prob if hasattr(ent._, 'prob') else 0.8,
                context=_get_context(text, ent.start_char, ent.end_char),
                position=ent.start_char
            )
            
            # Categorize entities with enhanced logic
            if ent.label_ == "ORG":
                if _is_government_agency(ent.text):
                    analytics.agencies.append(entity)
            elif ent.label_ == "MONEY":
                analytics.amounts.append(entity)
            elif ent.label_ == "GPE":
                analytics.locations.append(entity)
            elif ent.label_ == "PERSON":
                analytics.people.append(entity)
            elif ent.label_ == "PH_GOV_AGENCY":
                # Custom Philippine government agency pattern
                analytics.agencies.append(entity)
            elif ent.label_ == "PH_MONEY":
                # Custom Philippine money pattern
                analytics.amounts.append(entity)
        
        # Extract project types using dependency parsing
        analytics.project_types = _extract_project_types(doc)
        
        # Extract corruption indicators
        analytics.corruption_indicators = _extract_corruption_indicators(doc)
        
        # Extract contractor names
        analytics.contractors = _extract_contractors(doc)
        
        # Extract project locations with context
        analytics.project_locations = _extract_project_locations(doc)
        
        analytics.extraction_confidence = 0.95  # High confidence with enhanced spaCy
        
    except Exception as e:
        print(f"⚠️ spaCy extraction failed: {e}")
        analytics.extraction_confidence = 0.0
    
    return analytics

def _add_custom_patterns(nlp):
    """Add custom patterns for Philippine government entities"""
    # This function is for spaCy integration
    # For now, we'll use enhanced regex patterns
    pass

def _extract_contractors(doc) -> List[str]:
    """Extract contractor names - placeholder for spaCy integration"""
    # This will be implemented when spaCy is available
    return []

def _extract_project_locations(doc) -> List[str]:
    """Extract project locations with context - placeholder for spaCy integration"""
    # This will be implemented when spaCy is available
    return []

def _extract_with_regex(text: str, analytics: FundsAnalytics) -> FundsAnalytics:
    """Enhanced regex extraction with senior dev patterns"""
    
    # Enhanced Philippine government agencies
    agency_pattern = r'\b(DPWH|DBM|COA|Comelec|DILG|DOH|DepEd|DOTR|Senate|House|Congress|LGU|Barangay|Province|City|Municipality|National|Government|Public|Malacañang|Palace|President|Vice President|Ombudsman|Philippine Government|PH Government)\b'
    
    # Enhanced money amounts with better patterns
    money_pattern = r'\b(P\d+(?:\.\d+)?\s*(?:billion|million|thousand|trillion)?|\d+(?:\.\d+)?\s*(?:billion|million|thousand|trillion)\s*(?:pesos?|php)?|\d+(?:\.\d+)?\s*(?:billion|million|thousand|trillion))\b'
    
    # Enhanced locations
    location_pattern = r'\b(Philippines|Manila|Cebu|Davao|Quezon|Makati|Taguig|Pasig|Mandaluyong|San Juan|Marikina|Parañaque|Las Piñas|Muntinlupa|Caloocan|Malabon|Navotas|Valenzuela|Pasay|Pateros|Bohol|Cebu City|Davao City|Quezon City|Makati City|Taguig City|Pasig City)\b'
    
    # Contractor patterns
    contractor_pattern = r'\b([A-Z][a-zA-Z\s]+(?:Construction|Builders|Corp|Inc|Ltd|Company|Enterprises|Development))\b'
    
    # Project type patterns
    project_pattern = r'\b(flood control|infrastructure|road|bridge|school|hospital|building|project|program|initiative|development|construction)\b'
    
    # Corruption indicators
    corruption_pattern = r'\b(corruption|kickback|anomaly|graft|plunder|misuse|overprice|scam|whistleblower|audit|irregularity|bidding|contract)\b'
    
    # Extract agencies
    for match in re.finditer(agency_pattern, text, re.IGNORECASE):
        entity = FundsEntity(
            entity_type="agency",
            text=match.group(),
            confidence=0.8,
            context=_get_context(text, match.start(), match.end()),
            position=match.start()
        )
        analytics.agencies.append(entity)
    
    # Extract amounts
    for match in re.finditer(money_pattern, text, re.IGNORECASE):
        entity = FundsEntity(
            entity_type="amount",
            text=match.group(),
            confidence=0.9,
            context=_get_context(text, match.start(), match.end()),
            position=match.start()
        )
        analytics.amounts.append(entity)
    
    # Extract locations
    for match in re.finditer(location_pattern, text, re.IGNORECASE):
        entity = FundsEntity(
            entity_type="location",
            text=match.group(),
            confidence=0.7,
            context=_get_context(text, match.start(), match.end()),
            position=match.start()
        )
        analytics.locations.append(entity)
    
    # Extract contractors
    for match in re.finditer(contractor_pattern, text, re.IGNORECASE):
        analytics.contractors.append(match.group())
    
    # Extract project types
    for match in re.finditer(project_pattern, text, re.IGNORECASE):
        analytics.project_types.append(match.group())
    
    # Extract corruption indicators
    for match in re.finditer(corruption_pattern, text, re.IGNORECASE):
        analytics.corruption_indicators.append(match.group())
    
    analytics.extraction_confidence = 0.85  # High confidence with enhanced regex
    
    return analytics

def _is_government_agency(text: str) -> bool:
    """Check if an organization is a Philippine government agency"""
    gov_agencies = {
        'dpwh', 'dbm', 'coa', 'comelec', 'dilg', 'doh', 'deped', 'dotr',
        'senate', 'house', 'congress', 'lgu', 'barangay', 'province',
        'city', 'municipality', 'national', 'government', 'public',
        'malacañang', 'palace', 'president', 'vice president', 'ombudsman'
    }
    return text.lower() in gov_agencies

def _get_context(text: str, start: int, end: int, context_size: int = 50) -> str:
    """Get surrounding context for an entity"""
    context_start = max(0, start - context_size)
    context_end = min(len(text), end + context_size)
    return text[context_start:context_end].strip()

def _extract_project_types(doc) -> List[str]:
    """Extract project types using spaCy dependency parsing"""
    project_types = []
    
    # Look for project-related nouns
    for token in doc:
        if token.pos_ == "NOUN" and any(keyword in token.text.lower() for keyword in 
            ['project', 'program', 'initiative', 'infrastructure', 'construction', 'development']):
            project_types.append(token.text)
    
    return list(set(project_types))

def _extract_corruption_indicators(doc) -> List[str]:
    """Extract corruption-related terms"""
    corruption_terms = []
    
    for token in doc:
        if any(keyword in token.text.lower() for keyword in 
            ['corruption', 'kickback', 'anomaly', 'graft', 'plunder', 'misuse', 
             'overprice', 'scam', 'whistleblower', 'audit', 'irregularity']):
            corruption_terms.append(token.text)
    
    return list(set(corruption_terms))

def _calculate_derived_metrics(analytics: FundsAnalytics) -> FundsAnalytics:
    """Calculate derived analytics metrics"""
    
    # Calculate total amount
    total = 0.0
    for amount_entity in analytics.amounts:
        amount_text = amount_entity.text.lower()
        # Extract numeric value and convert to float
        numeric_match = re.search(r'(\d+(?:\.\d+)?)', amount_text)
        if numeric_match:
            value = float(numeric_match.group(1))
            if 'billion' in amount_text:
                total += value * 1_000_000_000
            elif 'million' in amount_text:
                total += value * 1_000_000
            elif 'thousand' in amount_text:
                total += value * 1_000
            else:
                total += value
    
    analytics.total_amount = total if total > 0 else None
    
    # Determine primary agency (most mentioned)
    if analytics.agencies:
        agency_counts = {}
        for agency in analytics.agencies:
            agency_counts[agency.text] = agency_counts.get(agency.text, 0) + 1
        analytics.primary_agency = max(agency_counts, key=agency_counts.get)
    
    # Calculate funds relevance score
    relevance_score = 0.0
    if analytics.agencies:
        relevance_score += 0.3
    if analytics.amounts:
        relevance_score += 0.4
    if analytics.corruption_indicators:
        relevance_score += 0.2
    if analytics.project_types:
        relevance_score += 0.1
    
    analytics.funds_relevance_score = min(relevance_score, 1.0)
    
    return analytics

# Example usage and analytics functions
def analyze_funds_trends(analytics_list: List[FundsAnalytics]) -> Dict[str, Any]:
    """Analyze trends across multiple funds articles"""
    
    # Agency analysis
    agency_totals = {}
    agency_counts = {}
    
    # Amount analysis
    total_funds = 0.0
    amount_distribution = []
    
    # Corruption analysis
    corruption_articles = 0
    
    for analytics in analytics_list:
        # Agency analysis
        if analytics.primary_agency:
            agency_counts[analytics.primary_agency] = agency_counts.get(analytics.primary_agency, 0) + 1
            if analytics.total_amount:
                agency_totals[analytics.primary_agency] = agency_totals.get(analytics.primary_agency, 0) + analytics.total_amount
        
        # Amount analysis
        if analytics.total_amount:
            total_funds += analytics.total_amount
            amount_distribution.append(analytics.total_amount)
        
        # Corruption analysis
        if analytics.corruption_indicators:
            corruption_articles += 1
    
    return {
        "total_articles": len(analytics_list),
        "total_funds_mentioned": total_funds,
        "average_amount_per_article": total_funds / len(analytics_list) if analytics_list else 0,
        "top_agencies_by_count": sorted(agency_counts.items(), key=lambda x: x[1], reverse=True)[:10],
        "top_agencies_by_amount": sorted(agency_totals.items(), key=lambda x: x[1], reverse=True)[:10],
        "corruption_rate": corruption_articles / len(analytics_list) if analytics_list else 0,
        "amount_distribution": {
            "min": min(amount_distribution) if amount_distribution else 0,
            "max": max(amount_distribution) if amount_distribution else 0,
            "median": sorted(amount_distribution)[len(amount_distribution)//2] if amount_distribution else 0
        }
    }

if __name__ == "__main__":
    # Test the analytics system
    sample_article = """
    DPWH allocates P5 billion for flood control projects across the Philippines.
    The Department of Public Works and Highways announced the allocation for 
    infrastructure projects in Manila, Cebu, and Davao. Senator Juan Dela Cruz 
    questioned the allocation, citing potential irregularities in the bidding process.
    """
    
    analytics = extract_funds_analytics(
        article_id=1,
        title="DPWH allocates P5 billion for flood control",
        content=sample_article,
        published_at="2025-01-01"
    )
    
    print("🎯 Funds Analytics Results:")
    print(f"Agencies: {[a.text for a in analytics.agencies]}")
    print(f"Amounts: {[a.text for a in analytics.amounts]}")
    print(f"Locations: {[a.text for a in analytics.locations]}")
    print(f"Total Amount: {analytics.total_amount}")
    print(f"Primary Agency: {analytics.primary_agency}")
    print(f"Corruption Indicators: {analytics.corruption_indicators}")
    print(f"Relevance Score: {analytics.funds_relevance_score}")
