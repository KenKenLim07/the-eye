import re

# Read the broken file
with open('app/scrapers/manila_bulletin.py', 'r') as f:
    content = f.read()

# Find and replace the problematic method
old_method = '''    def _discover_links_from_html(self, html: str) -> List[str]:
        soup = BeautifulSoup(html, "html.parser")
        links: List[str] = []
        for sel in self.SELECTORS["article_links"]:
            for a in soup.select(sel):
                href = a.get("href")
                if not href:
                    continue
                full = urljoin(self.BASE_URL, href)
                if self._validate_url(full):
                    links.append(full)
        # Fallback: scan all anchors and pick likely article URLs (year in path)
        if not links:
            for a in soup:
                href = a.get("href")
                if not href:
                    continue
                full = urljoin(self.BASE_URL, href)
                if not self._validate_url(full):
                    continue
                path = urlparse(full).path or ""
                if re.search(r"/20\d{2}/", path) or re.search(r"/(news|nation|business|sports|entertainment|technology)/", path):
                    links.append(full)
        seen = set()
        unique = []
        for u in links:
            if u not in seen:
                seen.add(u)
                unique.append(u)
        return unique'''

new_method = '''    def _discover_links_from_html(self, html: str) -> List[str]:
        soup = BeautifulSoup(html, "html.parser")
        links: List[str] = []
        for sel in self.SELECTORS["article_links"]:
            for a in soup.select(sel):
                href = a.get("href")
                if not href:
                    continue
                full = urljoin(self.BASE_URL, href)
                if self._validate_url(full):
                    links.append(full)
        # Fallback: scan all anchors and pick likely article URLs (year in path)
        if not links:
            # FIXED: Only iterate over Tag elements, not Doctype or other non-Tag objects
            for a in soup.find_all('a'):
                href = a.get("href")
                if not href:
                    continue
                full = urljoin(self.BASE_URL, href)
                if not self._validate_url(full):
                    continue
                path = urlparse(full).path or ""
                if re.search(r"/20\d{2}/", path) or re.search(r"/(news|nation|business|sports|entertainment|technology)/", path):
                    links.append(full)
        seen = set()
        unique = []
        for u in links:
            if u not in seen:
                seen.add(u)
                unique.append(u)
        return unique'''

# Replace the method
content = content.replace(old_method, new_method)

# Write the fixed file
with open('app/scrapers/manila_bulletin.py', 'w') as f:
    f.write(content)

print('Fixed Manila Bulletin scraper!')
