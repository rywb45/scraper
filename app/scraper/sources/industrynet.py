import re
from urllib.parse import urlparse

import httpx

from app.config import settings
from app.scraper.base import BaseScraper, ScrapedCompany
from app.scraper.http_client import HttpClient
from app.scraper.extractors.company_extractor import extract_company


class IndustryNetScraper(BaseScraper):
    """Find companies listed on IndustryNet via Google site: search,
    then scrape the company's own website for details."""

    name = "industrynet"

    def __init__(self):
        self.http = HttpClient()

    async def search(self, query: str, num_results: int = 10) -> list[dict]:
        """Search Google for IndustryNet company profiles."""
        if not settings.serp_api_key:
            return []

        search_query = f"site:industrynet.com/co/ {query} manufacturer"
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    "https://google.serper.dev/search",
                    json={"q": search_query, "num": num_results, "gl": "us"},
                    headers={"X-API-KEY": settings.serp_api_key},
                )
                resp.raise_for_status()
                data = resp.json()

                results = []
                for r in data.get("organic", []):
                    link = r.get("link", "")
                    if not link or "/co/" not in link:
                        continue
                    results.append({
                        "url": link,
                        "title": r.get("title", ""),
                        "snippet": r.get("snippet", ""),
                    })
                    if len(results) >= num_results:
                        break
                return results
        except Exception:
            return []

    async def scrape_company(self, result: dict | str) -> ScrapedCompany | None:
        """Extract company info from an IndustryNet search result."""
        if isinstance(result, str):
            return None

        title = result.get("title", "")
        snippet = result.get("snippet", "")
        source_url = result.get("url", "")

        name = _extract_name_from_title(title)
        if not name:
            return None

        # Try to get website from IndustryNet page
        company_website = None
        company_domain = None

        try:
            resp = await self.http.get(source_url)
            if resp and resp.text:
                website_match = re.search(
                    r'(?:href=["\'])?(https?://(?!(?:www\.)?industrynet\.com)[a-zA-Z0-9.-]+\.[a-z]{2,}[^"\'<>\s]*)',
                    resp.text,
                )
                if website_match:
                    url = website_match.group(1)
                    parsed = urlparse(url)
                    domain = parsed.netloc.lower().removeprefix("www.")
                    if domain and "." in domain and not _is_social_domain(domain):
                        company_website = f"{parsed.scheme}://{parsed.netloc}"
                        company_domain = domain
        except Exception:
            pass

        if not company_domain:
            company_domain, company_website = await _find_company_website(name)

        if not company_domain:
            return None

        company = ScrapedCompany(
            name=name,
            domain=company_domain,
            website=company_website or "",
            source="industrynet",
            source_url=source_url,
        )

        # Extract location from snippet
        city, state = _extract_location_from_snippet(snippet)
        if city:
            company.city = city
        if state:
            company.state = state

        # Try scraping the company's own website
        if company_website:
            try:
                resp = await self.http.get(company_website)
                if resp and resp.text:
                    scraped = extract_company(company_website, resp.text)
                    if scraped:
                        if scraped.description:
                            company.description = scraped.description
                        if scraped.phone:
                            company.phone = scraped.phone
                        if scraped.city and not company.city:
                            company.city = scraped.city
                        if scraped.state and not company.state:
                            company.state = scraped.state
                        if scraped.zip_code:
                            company.zip_code = scraped.zip_code
                        if scraped.employee_count:
                            company.employee_count = scraped.employee_count
                        if scraped.employee_count_range:
                            company.employee_count_range = scraped.employee_count_range
                        if scraped.estimated_revenue:
                            company.estimated_revenue = scraped.estimated_revenue
                            company.revenue_source = scraped.revenue_source
            except Exception:
                pass

        return company


def _extract_name_from_title(title: str) -> str:
    if not title:
        return ""
    for sep in [" - ", " | ", " — ", " – "]:
        if sep in title:
            title = title.split(sep)[0]
            break
    name = title.strip()
    return name[:200] if len(name) >= 2 else ""


def _extract_location_from_snippet(snippet: str) -> tuple[str, str]:
    US_STATES = {
        "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
        "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
        "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
        "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
        "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC",
    }
    match = re.search(r"([A-Z][a-z]+(?:\s[A-Z][a-z]+)*),\s*([A-Z]{2})\b", snippet)
    if match and match.group(2) in US_STATES:
        return match.group(1).strip(), match.group(2)
    return "", ""


async def _find_company_website(name: str) -> tuple[str, str]:
    if not settings.serp_api_key:
        return "", ""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://google.serper.dev/search",
                json={"q": f"{name} official website", "num": 3, "gl": "us"},
                headers={"X-API-KEY": settings.serp_api_key},
            )
            resp.raise_for_status()
            data = resp.json()
            for r in data.get("organic", []):
                link = r.get("link", "")
                if not link:
                    continue
                parsed = urlparse(link)
                domain = parsed.netloc.lower().removeprefix("www.")
                if domain and "." in domain and not _is_social_domain(domain):
                    return domain, f"{parsed.scheme}://{parsed.netloc}"
    except Exception:
        pass
    return "", ""


SOCIAL_DOMAINS = {
    "wikipedia.org", "youtube.com", "facebook.com", "twitter.com",
    "linkedin.com", "instagram.com", "reddit.com", "yelp.com",
    "indeed.com", "glassdoor.com", "bbb.org", "crunchbase.com",
    "thomasnet.com", "kompass.com", "industrynet.com",
    "bloomberg.com", "reuters.com", "forbes.com",
    "amazon.com", "ebay.com", "google.com", "yahoo.com",
}


def _is_social_domain(domain: str) -> bool:
    for d in SOCIAL_DOMAINS:
        if domain == d or domain.endswith(f".{d}"):
            return True
    return False
