from urllib.parse import urljoin

from bs4 import BeautifulSoup

from app.scraper.base import BaseScraper, ScrapedCompany
from app.scraper.http_client import HttpClient


class ThomasNetScraper(BaseScraper):
    name = "thomasnet"
    BASE_URL = "https://www.thomasnet.com"

    def __init__(self):
        self.http = HttpClient()

    async def search(self, query: str, num_results: int = 10) -> list[str]:
        search_url = f"{self.BASE_URL}/nsearch.html?cov=NA&heading=&what={query.replace(' ', '+')}&where=US"
        resp = await self.http.get(search_url)
        if not resp:
            return []

        soup = BeautifulSoup(resp.text, "lxml")
        urls = []
        for link in soup.select("a.profile-card__title"):
            href = link.get("href", "")
            if href:
                urls.append(urljoin(self.BASE_URL, href))
            if len(urls) >= num_results:
                break
        return urls

    async def scrape_company(self, url: str) -> ScrapedCompany | None:
        resp = await self.http.get(url)
        if not resp:
            return None

        soup = BeautifulSoup(resp.text, "lxml")
        company = ScrapedCompany(source="thomasnet", source_url=url)

        # Name
        name_el = soup.select_one("h1")
        if name_el:
            company.name = name_el.get_text(strip=True)

        # Description
        desc_el = soup.select_one(".supplier-profile__description, .company-description")
        if desc_el:
            company.description = desc_el.get_text(strip=True)[:1000]

        # Location
        loc_el = soup.select_one(".supplier-profile__location, .co-location")
        if loc_el:
            parts = loc_el.get_text(strip=True).split(",")
            if len(parts) >= 2:
                company.city = parts[0].strip()
                state_zip = parts[-1].strip().split()
                if state_zip:
                    company.state = state_zip[0]
                if len(state_zip) > 1:
                    company.zip_code = state_zip[1]

        # Website link
        website_el = soup.select_one('a[href*="website"], a.supplier-profile__website')
        if website_el:
            href = website_el.get("href", "")
            if href.startswith("http"):
                company.website = href
                from urllib.parse import urlparse
                company.domain = urlparse(href).netloc.lower().removeprefix("www.")

        # Phone
        phone_el = soup.select_one(".supplier-profile__phone, .co-phone")
        if phone_el:
            company.phone = phone_el.get_text(strip=True)

        if not company.name:
            return None
        return company
