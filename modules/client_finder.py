import requests


def find(industry: str, location: str = "India", type: str = "clients") -> str:
    """Find potential clients/companies via web search"""
    queries = [
        f"{industry} companies {location} contact email",
        f"top {industry} startups {location} 2024",
        f"{industry} businesses hiring {location}",
    ]
    results = []
    for q in queries[:2]:
        r = requests.get(
            "https://api.duckduckgo.com/",
            params={"q": q, "format": "json", "no_html": "1"},
            timeout=8
        ).json()
        text = r.get("AbstractText", "") or " | ".join(
            t.get("Text", "") for t in r.get("RelatedTopics", [])[:5] if "Text" in t
        )
        if text:
            results.append(f"Search: {q}\n{text}")

    return "\n\n".join(results) or f"No results for {industry} in {location}"
