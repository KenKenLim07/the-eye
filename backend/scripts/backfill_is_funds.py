from typing import Iterable, List
from app.core.supabase import get_supabase
from app.pipeline.store import classify_is_funds

def is_funds_related(title: str | None, content: str | None) -> bool:
    return classify_is_funds(title, content)

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


