#!/usr/bin/env python3
import os, sys, json, argparse, shutil

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
KEYWORDS_PATH = os.path.join(ROOT, 'app', 'ml', 'keywords_ph.json')
SUGG_PATH = os.path.join(ROOT, 'app', 'ml', 'suggestions', 'keywords_ph_suggestions.json')


def load_json(path: str):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json(path: str, data: dict):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    ap = argparse.ArgumentParser(description='Apply mined suggestions to keywords_ph.json')
    ap.add_argument('--apply', action='store_true', help='Write changes to keywords_ph.json (otherwise dry-run)')
    ap.add_argument('--category', default='neutral_institutional', help='Category to merge suggestions into')
    args = ap.parse_args()

    if not os.path.exists(SUGG_PATH):
        print(f"Suggestions file not found: {SUGG_PATH}")
        sys.exit(1)
    if not os.path.exists(KEYWORDS_PATH):
        print(f"Keywords file not found: {KEYWORDS_PATH}")
        sys.exit(1)

    sugg = load_json(SUGG_PATH)
    kw = load_json(KEYWORDS_PATH)

    suggestions = sugg.get('proposed_additions', {}).get(args.category, [])
    if not suggestions:
        print(f"No suggestions found for category '{args.category}'. Nothing to do.")
        return

    kw_cfg = kw.get('keywords') or {}
    existing = kw_cfg.get(args.category) or []

    existing_set = {str(x).strip() for x in existing if str(x).strip()}
    add_set = {str(x).strip() for x in suggestions if str(x).strip()}

    to_add = sorted(list(add_set - existing_set))

    print(json.dumps({
        'category': args.category,
        'existing_count': len(existing_set),
        'suggested_count': len(add_set),
        'new_terms': to_add,
        'new_total_if_applied': len(existing_set) + len(to_add)
    }, ensure_ascii=False, indent=2))

    if not to_add:
        print('No new terms to add.')
        return

    if args.apply:
        backup = KEYWORDS_PATH + '.bak'
        shutil.copy2(KEYWORDS_PATH, backup)
        print(f"Backup written: {backup}")

        updated_list = list(existing_set) + to_add
        updated_list = sorted(set(updated_list), key=lambda s: s.lower())
        kw_cfg[args.category] = updated_list
        kw['keywords'] = kw_cfg
        # bump updated_at
        from datetime import datetime, timezone
        kw['updated_at'] = datetime.now(timezone.utc).isoformat()
        save_json(KEYWORDS_PATH, kw)
        print(f"Applied {len(to_add)} new terms to '{args.category}' and saved to {KEYWORDS_PATH}")


if __name__ == '__main__':
    main() 