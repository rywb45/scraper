from urllib.parse import urlparse

import httpx

from app.config import settings
from app.scraper.base import BaseScraper, ScrapedCompany
from app.scraper.filters import is_public_company_domain
from app.scraper.http_client import HttpClient
from app.scraper.serper_keys import key_manager, serper_search

# Domains that are never actual company websites
SKIP_DOMAINS = {
    "wikipedia.org", "youtube.com", "facebook.com", "twitter.com",
    "linkedin.com", "instagram.com", "reddit.com", "yelp.com",
    "indeed.com", "glassdoor.com", "bbb.org", "crunchbase.com",
    "zoominfo.com", "dnb.com", "bloomberg.com", "reuters.com",
    "forbes.com", "inc.com", "businessinsider.com", "cnbc.com",
    "wsj.com", "nytimes.com", "washingtonpost.com",
    "amazon.com", "ebay.com", "alibaba.com", "aliexpress.com",
    "globaldata.com", "statista.com", "ibisworld.com",
    "marketwatch.com", "yahoo.com", "google.com",
    "eletimes.ai", "ensun.io", "clutch.co", "g2.com",
    "thomasnet.com", "kompass.com", "industrynet.com",  # handled by dedicated scrapers
    "manta.com", "superpages.com", "yellowpages.com",
    "sec.gov", "usa.gov", "sba.gov",
    "medium.com", "quora.com", "stackexchange.com",
    "pinterest.com", "tiktok.com", "tumblr.com",
}

# URL path patterns that indicate list/article pages, not company sites
SKIP_PATH_PATTERNS = [
    "/wiki/", "/category/", "/list", "/top-", "/best-",
    "/article/", "/blog/", "/news/", "/press-release/",
    "/search", "/results", "/directory",
]


class GoogleSearchScraper(BaseScraper):
    name = "google_search"

    def __init__(self):
        self.http = HttpClient()

    async def search(self, query: str, num_results: int = 10, location: str = "") -> list[dict]:
        if settings.serp_api_provider == "serpapi":
            return await self._search_serpapi(query, num_results)
        return await self._search_serper(query, num_results, location=location)

    async def _search_serpapi(self, query: str, num_results: int) -> list[dict]:
        try:
            from serpapi import GoogleSearch

            params = {
                "q": query,
                "num": num_results,
                "api_key": settings.serp_api_key,
                "gl": "us",
                "hl": "en",
            }
            search = GoogleSearch(params)
            data = search.get_dict()
            results = []
            for r in data.get("organic_results", []):
                link = r.get("link", "")
                if link and self._is_company_url(link):
                    parsed = urlparse(link)
                    domain = parsed.netloc.lower().removeprefix("www.")
                    results.append({
                        "url": link,
                        "title": r.get("title", ""),
                        "snippet": r.get("snippet", ""),
                        "domain": domain,
                        "knowledge_graph": None,
                    })
            return results[:num_results]
        except Exception:
            return []

    async def _search_serper(self, query: str, num_results: int, location: str = "") -> list[dict]:
        data = await serper_search(query, num=num_results, location=location)
        if not data:
            return []

        kg = data.get("knowledgeGraph") or None
        results = []
        for r in data.get("organic", []):
            link = r.get("link", "")
            if link and self._is_company_url(link):
                parsed = urlparse(link)
                domain = parsed.netloc.lower().removeprefix("www.")
                results.append({
                    "url": link,
                    "title": r.get("title", ""),
                    "snippet": r.get("snippet", ""),
                    "domain": domain,
                    "knowledge_graph": kg if not results else None,  # attach KG to first result only
                })
        return results[:num_results]

    def _is_company_url(self, url: str) -> bool:
        parsed = urlparse(url)
        domain = parsed.netloc.lower().removeprefix("www.")
        path = parsed.path.lower()

        # Skip known non-company domains
        for skip in SKIP_DOMAINS:
            if domain == skip or domain.endswith(f".{skip}"):
                return False

        # Skip all government domains
        if domain.endswith(".gov"):
            return False

        # Skip public/enterprise companies
        if is_public_company_domain(domain):
            return False

        # Skip list/article URLs
        for pattern in SKIP_PATH_PATTERNS:
            if pattern in path:
                return False

        # Should be a homepage or about/contact page of a company
        # Reject deep paths that are likely articles
        path_depth = len([p for p in path.split("/") if p])
        if path_depth > 3:
            return False

        return True

    async def scrape_company(self, result: dict | str) -> ScrapedCompany | None:
        url = result["url"] if isinstance(result, dict) else result
        resp = await self.http.get(url)
        if not resp:
            return None

        from app.scraper.extractors.company_extractor import extract_company
        from app.scraper.filters import has_public_company_indicators

        # Skip if the page looks like a public company
        if has_public_company_indicators(resp.text):
            return None

        return extract_company(url, resp.text)
