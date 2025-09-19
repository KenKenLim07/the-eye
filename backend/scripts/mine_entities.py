#!/usr/bin/env python3
import os, json, re
from collections import Counter

# Minimal Supabase client via REST (reuse existing env)
from app.core.supabase import get_supabase

POLITICAL_STOP = set([
    'News','Latest','Business','Nation','World','Technology','Sports','Entertainment','Opinion',
    'General','Lifestyle','Trends','View','Quick','Open','Original','Editorial','Cartoons',
    'Sept','September','Oct','October','Nov','November','Dec','December','Jan','January',
    'Feb','February','Mar','March','Apr','April','May','Jun','June','Jul','July','Aug','August',
    'No','View All','View all'
])

NAME_RE = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})\b")
ACRO_RE = re.compile(r"\b([A-Z]{2,6})\b")

EXCLUDE_ACROS = { 'PH','PHL','GDP','AI','NBA','UFC','NCAA','UAAP','PBA','PNR','LRT','MRT' }


def fetch_recent_articles(days=30, limit=2000):
    sb = get_supabase()
    from datetime import datetime, timedelta
    start = (datetime.utcnow() - timedelta(days=days)).isoformat()
    res = sb.table('articles').select('*').gte('published_at', start).order('published_at', desc=True).limit(limit).execute()
    return res.data or []


def mine_entities(articles):
    text = "\n".join([f"{a.get('title','')} {a.get('category','')} {a.get('source','')}" for a in articles])
    names = [m.strip() for m in NAME_RE.findall(text)]
    acros = [m for m in ACRO_RE.findall(text)]

    def keep_name(n: str) -> bool:
        if not n:
            return False
        head = n.split()[0]
        if head in POLITICAL_STOP:
            return False
        if len(n) <= 2:
            return False
        return True

    name_cnt = Counter([n for n in names if keep_name(n)])
    acro_cnt = Counter([a for a in acros if a not in EXCLUDE_ACROS])
    return name_cnt.most_common(50), acro_cnt.most_common(50)


def main():
    arts = fetch_recent_articles()
    names, acros = mine_entities(arts)

    KNOWN_AGENCIES = {
        'DPWH','DOF','DOJ','NEDA','DILG','DOH','DEPED','DND','AFP','PNP','COMELEC','OMBUDSMAN','COA','DBM','NBI','BI','BIR','BOC','BSP'
    }
    proposed_neutral_institutional = [a for a,_ in acros if a in KNOWN_AGENCIES]
    people_candidates = [n for n,_ in names if n not in POLITICAL_STOP][:30]

    out = {
        'analyzed_articles': len(arts),
        'top_names': names,
        'top_acronyms': acros,
        'proposed_additions': {
            'neutral_institutional': proposed_neutral_institutional,
            'people_candidates': people_candidates
        }
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))

    sugg_dir = os.path.join(os.path.dirname(__file__), '..', 'app', 'ml', 'suggestions')
    os.makedirs(sugg_dir, exist_ok=True)
    sugg_path = os.path.abspath(os.path.join(sugg_dir, 'keywords_ph_suggestions.json'))
    with open(sugg_path, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\nWrote suggestion file: {sugg_path}")

if __name__ == '__main__':
    main()
