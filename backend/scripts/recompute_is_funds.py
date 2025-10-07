"""
Recompute is_funds for all articles using the latest rules in app.pipeline.store.classify_is_funds
Sets is_funds = true when classifier matches, else false.
Batch/paginate to avoid timeouts.
"""
from app.core.supabase import get_supabase
from app.pipeline.store import classify_is_funds

def main() -> None:
    sb = get_supabase()
    offset = 0
    limit = 1000
    updated_true = 0
    updated_false = 0
    total = 0

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
        total += len(rows)

        to_true = []
        to_false = []
        for row in rows:
            want_true = classify_is_funds(row.get("title"), row.get("content"))
            current = row.get("is_funds")
            if want_true and current is not True:
                to_true.append(row["id"])
            elif not want_true and current is not False:
                to_false.append(row["id"])

        if to_true:
            sb.table("articles").update({"is_funds": True}).in_("id", to_true).execute()
            updated_true += len(to_true)
        if to_false:
            sb.table("articles").update({"is_funds": False}).in_("id", to_false).execute()
            updated_false += len(to_false)

        offset += limit
        if len(rows) < limit:
            break

    print({
        "evaluated": total,
        "updated_true": updated_true,
        "updated_false": updated_false,
    })

if __name__ == "__main__":
    main()




