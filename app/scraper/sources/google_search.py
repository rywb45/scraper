from urllib.parse import urlparse

from app.config import settings
from app.scraper.base import BaseScraper, ScrapedCompany
from app.scraper.http_client import HttpClient


class GoogleSearchScraper(BaseScraper):
    name = "google_search"

    def __init__(self):
        self.http = HttpClient()

    async def search(self, query: str, num_results: int = 10) -> list[str]:
        if settings.serp_api_provider == "serpapi":
            return await self._search_serpapi(query, num_results)
        return await self._search_serper(query, num_results)

    async def _search_serpapi(self, query: str, num_results: int) -> list[str]:
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
            results = search.get_dict()
            urls = []
            for r in results.get("organic_results", []):
                link = r.get("link", "")
                if link and self._is_valid_url(link):
                    urls.append(link)
            return urls[:num_results]
        except Exception:
            return []

    async def _search_serper(self, query: str, num_results: int) -> list[str]:
        import httpx

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    "https://google.serper.dev/search",
                    json={"q": query, "num": num_results, "gl": "us"},
                    headers={"X-API-KEY": settings.serp_api_key},
                )
                resp.raise_for_status()
                data = resp.json()
                urls = []
                for r in data.get("organic", []):
                    link = r.get("link", "")
                    if link and self._is_valid_url(link):
                        urls.append(link)
                return urls[:num_results]
        except Exception:
            return []

    def _is_valid_url(self, url: str) -> bool:
        skip_domains = {
            "wikipedia.org", "youtube.com", "facebook.com", "twitter.com",
            "linkedin.com", "instagram.com", "reddit.com", "yelp.com",
            "indeed.com", "glassdoor.com",
        }
        parsed = urlparse(url)
        domain = parsed.netloc.lower().removeprefix("www.")
        return domain not in skip_domains

    async def scrape_company(self, url: str) -> ScrapedCompany | None:
        resp = await self.http.get(url)
        if not resp:
            return None

        from app.scraper.extractors.company_extractor import extract_company
        return extract_company(url, resp.text)
