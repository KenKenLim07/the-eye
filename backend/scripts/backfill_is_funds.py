import re
from typing import Iterable, List
from app.core.supabase import get_supabase

MONEY = r"(fund|budget|appropriation|allocation|disbursement|audit|coa|\bphp\b|billion|million|trillion|peso|pesos)"
PUBLIC_SECTOR = r"(gov(ernment)?|government|public|senate|house|congress|dbm|doe|dotr|doh|dep(ed)?|dpwh|coa|comelec|dilg|lgu|city|province|barangay|state|national|solon|lawmaker|bill|appropriation|budget)"
CORRUPTION = r"(pork|kickback|anomaly|graft|plunder|misuse|overprice|overpriced|scam|whistleblower)"
SPORTS = r"(basketball|volleyball|football|soccer|nba|pba|uaap|ncaa|tournament|match|game|coach|player|club)"

POSITIVE_PATTERN = re.compile(fr"(?=.*{MONEY}).*(?:{PUBLIC_SECTOR}|{CORRUPTION})", re.IGNORECASE | re.DOTALL)
NEGATIVE_PATTERN = re.compile(SPORTS, re.IGNORECASE)

def is_funds_related(title: str | None, content: str | None) -> bool:
    text = ((title or "") + "\n" + (content or "")).lower()
    if NEGATIVE_PATTERN.search(text):
        return False
    return bool(POSITIVE_PATTERN.search(text))

def chunked(items: List[int], size: int) -> Iterable[List[int]]:
    for i in range(0, len(items), size):
        yield items[i:i+size]

def main() -> None:
    sb = get_supabase()

    to_true_ids: List[int] = []

    # Paginate through all articles not yet marked true
    offset = 0
    limit = 1000
    total_evaluated = 0
    while True:
        res = (
            sb.table("articles")
            .select("id,title,content,is_funds")
            .order("id", desc=False)
            .range(offset, offset + limit - 1)
            .execute()
        )
        rows = res.data or []
        if not rows:
            break
        total_evaluated += len(rows)
        for row in rows:
            # Skip those already true
            if row.get("is_funds") is True:
                continue
            if is_funds_related(row.get("title"), row.get("content")):
                to_true_ids.append(int(row["id"]))
        offset += limit
        if len(rows) < limit:
            break

    # Apply updates in batches
    for batch in chunked(to_true_ids, 500):
        sb.table("articles").update({"is_funds": True}).in_("id", batch).execute()

    print({"evaluated": total_evaluated, "marked_true": len(to_true_ids)})

if __name__ == "__main__":
    main()


