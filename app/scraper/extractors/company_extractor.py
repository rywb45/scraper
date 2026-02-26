import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from app.scraper.base import ScrapedCompany
from app.scraper.extractors.structured_data import extract_organization_data

US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC",
}


def extract_company(url: str, html: str) -> ScrapedCompany | None:
    soup = BeautifulSoup(html, "lxml")
    parsed = urlparse(url)
    domain = parsed.netloc.lower().removeprefix("www.")

    company = ScrapedCompany(
        domain=domain,
        website=f"{parsed.scheme}://{parsed.netloc}",
        source="web",
        source_url=url,
    )

    # Try structured data first
    org = extract_organization_data(soup)
    if org:
        company.name = org.get("name", "")
        company.description = org.get("description", "")[:1000] if org.get("description") else ""
        company.phone = org.get("telephone", "")
        addr = org.get("address", {})
        if isinstance(addr, dict):
            company.city = addr.get("addressLocality", "")
            company.state = addr.get("addressRegion", "")
            company.zip_code = addr.get("postalCode", "")

    # Fallback: extract from HTML
    if not company.name:
        # Try og:site_name, then <title>
        og_name = soup.find("meta", property="og:site_name")
        if og_name and og_name.get("content"):
            company.name = og_name["content"].strip()
        else:
            title = soup.find("title")
            if title:
                text = title.get_text(strip=True)
                # Clean up common suffixes
                for sep in [" | ", " - ", " — ", " :: "]:
                    if sep in text:
                        text = text.split(sep)[0]
                company.name = text.strip()[:200]

    if not company.description:
        og_desc = soup.find("meta", property="og:description")
        meta_desc = soup.find("meta", attrs={"name": "description"})
        desc = og_desc or meta_desc
        if desc and desc.get("content"):
            company.description = desc["content"].strip()[:1000]

    # Phone extraction
    if not company.phone:
        phone_pattern = re.compile(r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}")
        for el in soup.find_all(["a", "span", "p", "div"]):
            text = el.get_text(strip=True)
            match = phone_pattern.search(text)
            if match:
                href = el.get("href", "")
                if href.startswith("tel:") or len(text) < 50:
                    company.phone = match.group()
                    break

    # Address extraction
    if not company.state:
        addr_pattern = re.compile(
            r"([A-Za-z\s]+),\s*([A-Z]{2})\s*(\d{5}(?:-\d{4})?)"
        )
        text = soup.get_text()
        match = addr_pattern.search(text)
        if match and match.group(2) in US_STATES:
            company.city = match.group(1).strip()
            company.state = match.group(2)
            company.zip_code = match.group(3)

    if not company.name:
        return None
    return company
