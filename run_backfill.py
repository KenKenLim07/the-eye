#!/usr/bin/env python3
import sys, os, json, time, argparse, urllib.request, urllib.parse, datetime

def http_get(url, headers):
    req = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())

def http_post(url, headers, body_dict):
    data = json.dumps(body_dict).encode()
    req = urllib.request.Request(url, headers={**headers, "Content-Type":"application/json"}, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        content = r.read().decode() or "{}"
        try:
            return json.loads(content)
        except Exception:
            return {"raw": content}

def chunk(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i+n]

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--supabase-url", required=True)
    p.add_argument("--backend-url", default="http://localhost:8000")
    p.add_argument("--days", type=int, default=7)
    p.add_argument("--page-size", type=int, default=1000)
    p.add_argument("--batch-size", type=int, default=500)
    args = p.parse_args()

    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    if not service_key:
        print("ERROR: SUPABASE_SERVICE_ROLE_KEY not set in environment", file=sys.stderr)
        sys.exit(1)

    since = (datetime.datetime.utcnow() - datetime.timedelta(days=args.days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"Backfilling analyses since {since} (last {args.days} days)")

    supa_headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
    }

    total_ids = 0
    offset = 0

    while True:
        params = urllib.parse.urlencode({
            "select": "id",
            "order": "published_at.desc",
            "limit": str(args.page_size),
            "offset": str(offset),
        })
        url = f"{args.supabase_url}/rest/v1/articles?published_at=gte.{since}&{params}"
        page = http_get(url, supa_headers)
        ids = [row.get("id") for row in page if row.get("id") is not None]
        if not ids:
            break

        for group in chunk(ids, args.batch_size):
            try:
                http_post(f"{args.backend_url}/ml/analyze", {}, {"article_ids": group})
            except Exception as e:
                print(f"WARN: enqueue failed for {len(group)} ids: {e}")

        total_ids += len(ids)
        offset += args.page_size
        print(f"Queued analysis for {total_ids} articles so far...")
        time.sleep(0.2)

    print(f"Done. Total queued: {total_ids} articles")
    print("Tail worker logs: docker logs -f ph-eye-worker")

if __name__ == "__main__":
    main()
