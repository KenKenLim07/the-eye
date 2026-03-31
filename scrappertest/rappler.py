import requests
from bs4 import BeautifulSoup

url = "https://www.rappler.com/technology/bluesky-developers-create-attie-custom-feed-creator/"

headers = {
    "User-Agent": "Mozilla/5.0",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.rappler.com/"
}

res = requests.get(url, headers=headers)

print("STATUS:", res.status_code)

soup = BeautifulSoup(res.text, "lxml")

import requests
from bs4 import BeautifulSoup
import json

url = "https://www.rappler.com/technology/bluesky-developers-create-attie-custom-feed-creator/"

headers = {
    "User-Agent": "Mozilla/5.0"
}

res = requests.get(url, headers=headers)
soup = BeautifulSoup(res.text, "lxml")

# 🔥 Find embedded JSON
script = soup.find("script", id="__NEXT_DATA__")

if not script:
    print("[!] __NEXT_DATA__ not found")
    print(res.text[:500])
    exit()

data = json.loads(script.string)

# 🔍 Navigate structure (this is the tricky part)
try:
    article = data["props"]["pageProps"]["post"]

    title = article["title"]
    content_blocks = article["content"]

    text_parts = []
    for block in content_blocks:
        if "content" in block:
            text_parts.append(block["content"])

    content = "\n".join(text_parts)

    print("\n=== TITLE ===")
    print(title)

    print("\n=== CONTENT PREVIEW ===")
    print(content[:500])

except Exception as e:
    print("[!] Structure changed")
    print(e)
    print(json.dumps(data, indent=2)[:1000])