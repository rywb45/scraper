import re
from urllib.parse import urlparse

from app.scraper.base import BaseScraper, ScrapedCompany
from app.scraper.http_client import HttpClient
from app.scraper.extractors.company_extractor import extract_company
from app.scraper.serper_keys import key_manager, serper_search
from app.scraper.sources.directory_utils import (
    extract_domain_from_snippet,
    extract_location_from_snippet,
    extract_name_from_title,
    find_company_website,
    is_social_domain,
)


class KompassScraper(BaseScraper):
    """Find companies listed on Kompass via Google site: search,
    then scrape the company's own website for details."""

    name = "kompass"

    def __init__(self):
        self.http = HttpClient()

    async def search(self, query: str, num_results: int = 10) -> list[dict]:
        """Search Google for Kompass company profiles."""
        if not key_manager.has_keys:
            return []

        search_query = f"site:kompass.com/c/ {query} manufacturer supplier USA"
        data = await serper_search(search_query, num=num_results)
        if not data:
            return []

        results = []
        for r in data.get("organic", []):
            link = r.get("link", "")
            if not link or "/c/" not in link:
                continue
            results.append({
                "url": link,
                "title": r.get("title", ""),
                "snippet": r.get("snippet", ""),
            })
            if len(results) >= num_results:
                break
        return results

    async def scrape_company(self, result: dict | str) -> ScrapedCompany | None:
        """Extract company info from a Kompass search result."""
        if isinstance(result, str):
            return None

        title = result.get("title", "")
        snippet = result.get("snippet", "")
        source_url = result.get("url", "")

        name = extract_name_from_title(title)
        if not name:
            return None

        # Step 1: Try to extract domain from the snippet (free — no API call)
        company_domain, company_website = extract_domain_from_snippet(snippet, "kompass.com")

        # Step 2: If snippet didn't have it, try scraping the profile page
        if not company_domain:
            try:
                resp = await self.http.get(source_url)
                if resp and resp.text:
                    website_match = re.search(
                        r'(?:href=["\'])?(https?://(?!(?:www\.)?kompass\.com)[a-zA-Z0-9.-]+\.[a-z]{2,}[^"\'<>\s]*)',
                        resp.text,
                    )
                    if website_match:
                        url = website_match.group(1)
                        parsed = urlparse(url)
                        domain = parsed.netloc.lower().removeprefix("www.")
                        if domain and "." in domain and not is_social_domain(domain):
                            company_website = f"{parsed.scheme}://{parsed.netloc}"
                            company_domain = domain
            except Exception:
                pass

        # Step 3: Last resort — Google search (costs 1 API call)
        if not company_domain:
            company_domain, company_website = await find_company_website(name)

        if not company_domain:
            return None

        company = ScrapedCompany(
            name=name,
            domain=company_domain,
            website=company_website or "",
            description=snippet,  # Pre-populate from search snippet
            source="kompass",
            source_url=source_url,
        )

        # Extract location from snippet
        city, state = extract_location_from_snippet(snippet)
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
