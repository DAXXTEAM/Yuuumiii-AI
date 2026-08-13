import requests
from html.parser import HTMLParser


def search(query: str) -> str:
    r = requests.get(
        "https://api.duckduckgo.com/",
        params={"q": query, "format": "json", "no_html": "1"},
        timeout=8
    ).json()
    text = r.get("AbstractText", "") or r.get("Answer", "")
    if not text:
        text = " | ".join(
            t.get("Text", "") for t in r.get("RelatedTopics", [])[:5] if "Text" in t
        )
    return text[:1500] or "No results found"


class Extractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text = []
        self.skip = False

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'nav', 'footer', 'header'):
            self.skip = True

    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'nav', 'footer', 'header'):
            self.skip = False

    def handle_data(self, data):
        if not self.skip and data.strip():
            self.text.append(data.strip())


def fetch(url: str) -> str:
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=12)
        p = Extractor()
        p.feed(r.text)
        return ' '.join(p.text)[:2000]
    except Exception as e:
        return f"Error: {e}"
