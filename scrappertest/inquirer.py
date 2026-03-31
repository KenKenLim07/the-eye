import requests
import json
from bs4 import BeautifulSoup
import time


class InquirerScraper:
    def __init__(self):
        self.base_url = "https://www.inquirer.com/pf/api/v3/content/fetch/content-api-v2"

        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://www.inquirer.com/",
            "Origin": "https://www.inquirer.com"
        }

    # ---------------- GET ARTICLE ----------------
    def fetch_article(self, canonical_url):
        query = {
            "canonical_url": canonical_url,
            "numberOfRelatedLinks": 100
        }

        filter_fields = (
            "_id,canonical_url,content_elements{content,type},"
            "credits{by{name}},description{basic},display_date,"
            "first_publish_date,headlines{basic},taxonomy{primary_section{name}}"
        )

        params = {
            "query": json.dumps(query),
            "filter": filter_fields,
            "_website": "philly-media-network"
        }

        res = requests.get(self.base_url, headers=self.headers, params=params)

        # 🔍 DEBUG: check response
        if res.status_code != 200:
            print(f"[!] Status Code: {res.status_code}")
            print(res.text[:300])
            return None

        # 🔍 Try parsing JSON
        try:
            data = res.json()
        except Exception:
            print("[!] Not JSON (probably blocked)")
            print(res.text[:500])
            return None

        # 🔍 FIND CONTENT DYNAMICALLY
        content = None
        for key in ["content", "data", "result"]:
            if key in data:
                content = data[key]
                print(f"[+] Found content under '{key}'")
                break

        if not content:
            print("[!] Unknown structure")
            print("Keys:", data.keys())
            print(json.dumps(data, indent=2)[:800])
            return None

        return self._normalize(content)

    # ---------------- NORMALIZE ----------------
    def _normalize(self, content):
        text_parts = []

        for el in content.get("content_elements", []):
            if el.get("type") == "text" and el.get("content"):
                text_parts.append(el["content"])

        return {
            "source": "inquirer",
            "title": content.get("headlines", {}).get("basic"),
            "url": content.get("canonical_url"),
            "date": content.get("display_date") or content.get("first_publish_date"),
            "category": content.get("taxonomy", {}).get("primary_section", {}).get("name"),
            "content": "\n".join(text_parts)
        }

    # ---------------- GET LINKS FROM HOMEPAGE ----------------
    def get_links(self):
        url = "https://www.inquirer.com/"
        res = requests.get(url, headers=self.headers)

        soup = BeautifulSoup(res.text, "html.parser")

        links = set()

        for a in soup.find_all("a", href=True):
            href = a["href"]

            # Filter real article links
            if href.startswith("/") and any(x in href for x in ["/news/", "/arts/", "/business/", "/sports/"]):
                links.add(href)

        return list(links)

    # ---------------- BULK SCRAPE ----------------
    def scrape_multiple(self, limit=10):
        links = self.get_links()
        print(f"[+] Found {len(links)} links")

        results = []

        for link in links[:limit]:
            print(f"[+] Fetching: {link}")

            article = self.fetch_article(link)

            if article:
                results.append(article)

            time.sleep(1)  # avoid blocking

        return results


# ---------------- RUN ----------------

scraper = InquirerScraper()

articles = scraper.scrape_multiple(limit=5)

print("\n=== RESULTS ===")
print(f"Total: {len(articles)}")

if articles:
    print(json.dumps(articles[0], indent=2))