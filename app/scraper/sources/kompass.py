from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from app.scraper.base import BaseScraper, ScrapedCompany
from app.scraper.http_client import HttpClient


class KompassScraper(BaseScraper):
    name = "kompass"
    BASE_URL = "https://us.kompass.com"

    def __init__(self):
        self.http = HttpClient()

    async def search(self, query: str, num_results: int = 10) -> list[str]:
        search_url = f"{self.BASE_URL}/searchCompanies?text={query.replace(' ', '+')}"
        resp = await self.http.get(search_url)
        if not resp:
            return []

        soup = BeautifulSoup(resp.text, "lxml")
        urls = []
        for link in soup.select("a.companyName, h2 a"):
            href = link.get("href", "")
            if href and "/company/" in href:
                urls.append(urljoin(self.BASE_URL, href))
            if len(urls) >= num_results:
                break
        return urls

    async def scrape_company(self, url: str) -> ScrapedCompany | None:
        resp = await self.http.get(url)
        if not resp:
            return None

        soup = BeautifulSoup(resp.text, "lxml")
        company = ScrapedCompany(source="kompass", source_url=url)

        name_el = soup.select_one("h1, .company-name")
        if name_el:
            company.name = name_el.get_text(strip=True)

        desc_el = soup.select_one(".company-description, .presentation")
        if desc_el:
            company.description = desc_el.get_text(strip=True)[:1000]

        # Address
        addr_el = soup.select_one(".address, .company-address")
        if addr_el:
            text = addr_el.get_text(strip=True)
            parts = text.rsplit(",", 2)
            if len(parts) >= 2:
                company.city = parts[-2].strip()
                state_parts = parts[-1].strip().split()
                if state_parts:
                    company.state = state_parts[0]

        # Website
        for a in soup.select("a[href]"):
            href = a.get("href", "")
            text = a.get_text(strip=True).lower()
            if "website" in text or ("http" in href and urlparse(href).netloc not in url):
                if href.startswith("http"):
                    company.website = href
                    company.domain = urlparse(href).netloc.lower().removeprefix("www.")
                    break

        phone_el = soup.select_one(".phone, .tel")
        if phone_el:
            company.phone = phone_el.get_text(strip=True)

        if not company.name:
            return None
        return company
