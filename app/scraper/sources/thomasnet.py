import re
from urllib.parse import urlparse

import httpx

from app.config import settings
from app.scraper.base import BaseScraper, ScrapedCompany
from app.scraper.http_client import HttpClient
from app.scraper.extractors.company_extractor import extract_company


class ThomasNetScraper(BaseScraper):
    """Find companies listed on ThomasNet via Google site: search,
    then scrape the company's own website for details."""

    name = "thomasnet"

    def __init__(self):
        self.http = HttpClient()

    async def search(self, query: str, num_results: int = 10) -> list[dict]:
        """Search Google for ThomasNet supplier profiles.

        Returns list of dicts with keys: url, title, snippet, company_url (if found).
        """
        if not settings.serp_api_key:
            return []

        search_query = f"site:thomasnet.com/profile {query} supplier manufacturer"
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
                    if not link or "/profile/" not in link:
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
        """Extract company info from a ThomasNet search result.

        Parses name from title, tries to find the company's actual website,
        then scrapes it with company_extractor for full details.
        """
        if isinstance(result, str):
            # Legacy: called with just a URL
            return None

        title = result.get("title", "")
        snippet = result.get("snippet", "")
        source_url = result.get("url", "")

        # Extract company name from title like "Company Name - Supplier of ..."
        name = _extract_name_from_title(title)
        if not name:
            return None

        # Try to find the company's own website from the ThomasNet profile page
        # ThomasNet pages are behind Cloudflare, so try but don't depend on it
        company_website = None
        company_domain = None

        try:
            resp = await self.http.get(source_url)
            if resp and resp.text:
                # Look for external website links in the page
                website_match = re.search(
                    r'(?:href=["\'])?(https?://(?!(?:www\.)?thomasnet\.com)[a-zA-Z0-9.-]+\.[a-z]{2,}[^"\'<>\s]*)',
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

        # If we couldn't get the website from the profile, try Google
        if not company_domain:
            company_domain, company_website = await _find_company_website(name)

        if not company_domain:
            return None

        # Now scrape the company's actual website
        company = ScrapedCompany(
            name=name,
            domain=company_domain,
            website=company_website or "",
            source="thomasnet",
            source_url=source_url,
        )

        # Extract location from snippet (ThomasNet often shows "City, ST" in snippets)
        city, state = _extract_location_from_snippet(snippet)
        if city:
            company.city = city
        if state:
            company.state = state

        # Try scraping the company's own website for richer data
        if company_website:
            try:
                resp = await self.http.get(company_website)
                if resp and resp.text:
                    scraped = extract_company(company_website, resp.text)
                    if scraped:
                        # Merge: keep ThomasNet source but use website data
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
    """Extract company name from a ThomasNet search result title."""
    if not title:
        return ""
    # Common patterns: "Company Name - Supplier of ...", "Company Name | ThomasNet"
    for sep in [" - ", " | ", " — ", " – "]:
        if sep in title:
            title = title.split(sep)[0]
            break
    name = title.strip()
    # Remove common suffixes
    for suffix in [" Inc", " Inc.", " LLC", " Corp", " Corp.", " Co.", " Ltd", " Ltd."]:
        if name.endswith(suffix):
            break
    return name[:200] if len(name) >= 2 else ""


def _extract_location_from_snippet(snippet: str) -> tuple[str, str]:
    """Try to extract city, state from a snippet."""
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
    """Use a quick Google search to find the company's website."""
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
