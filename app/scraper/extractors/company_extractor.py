import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from app.scraper.base import ScrapedCompany
from app.scraper.extractors.revenue_extractor import (
    estimate_revenue,
    extract_employee_count,
    extract_revenue,
)
from app.scraper.extractors.structured_data import extract_organization_data

US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC",
}

# Words that indicate the "name" is actually a page title, not a company
BAD_NAME_INDICATORS = [
    "top ", "best ", "list of ", "category:", "directory", " companies",
    " manufacturers", " suppliers", "wikipedia", "article", "review",
    " - search", "search results", "home page", "official site",
    "official website", "welcome to", "| linkedin", "| indeed",
]


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

    # Try structured data first — most reliable source
    org = extract_organization_data(soup)
    if org:
        name = (org.get("name") or "").strip()
        if name and _is_valid_company_name(name):
            company.name = name
        company.description = (org.get("description") or "")[:1000]
        company.phone = org.get("telephone") or ""
        addr = org.get("address", {})
        if isinstance(addr, dict):
            company.city = addr.get("addressLocality", "")
            company.state = addr.get("addressRegion", "")
            company.zip_code = addr.get("postalCode", "")

    # Try og:site_name — usually the real company name
    if not company.name:
        og_name = soup.find("meta", property="og:site_name")
        if og_name and og_name.get("content"):
            name = og_name["content"].strip()
            if _is_valid_company_name(name):
                company.name = name

    # Try <title> but clean it aggressively
    if not company.name:
        title = soup.find("title")
        if title:
            name = _clean_title(title.get_text(strip=True))
            if name and _is_valid_company_name(name):
                company.name = name

    # Last resort: derive from domain
    if not company.name:
        company.name = _name_from_domain(domain)

    if not company.description:
        og_desc = soup.find("meta", property="og:description")
        meta_desc = soup.find("meta", attrs={"name": "description"})
        desc = og_desc or meta_desc
        if desc and desc.get("content"):
            company.description = desc["content"].strip()[:1000]

    # Phone extraction
    if not company.phone:
        phone_pattern = re.compile(r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}")
        for el in soup.find_all("a", href=re.compile(r"^tel:")):
            match = phone_pattern.search(el.get_text(strip=True))
            if match:
                company.phone = match.group()
                break
        if not company.phone:
            for el in soup.find_all(["span", "p", "div"], limit=200):
                text = el.get_text(strip=True)
                if len(text) < 30:
                    match = phone_pattern.search(text)
                    if match:
                        company.phone = match.group()
                        break

    # Address extraction
    if not company.state:
        addr_pattern = re.compile(
            r"([A-Za-z\s]+),\s*([A-Z]{2})\s+(\d{5}(?:-\d{4})?)"
        )
        # Search in footer and address elements first
        for el in soup.find_all(["footer", "address"]):
            text = el.get_text()
            match = addr_pattern.search(text)
            if match and match.group(2) in US_STATES:
                company.city = match.group(1).strip()
                company.state = match.group(2)
                company.zip_code = match.group(3)
                break
        # Fallback: search full page
        if not company.state:
            text = soup.get_text()
            match = addr_pattern.search(text)
            if match and match.group(2) in US_STATES:
                company.city = match.group(1).strip()
                company.state = match.group(2)
                company.zip_code = match.group(3)

    # Revenue extraction
    revenue, rev_source = extract_revenue(html)
    if revenue:
        company.estimated_revenue = revenue
        company.revenue_source = rev_source

    # Employee count extraction
    emp_count, emp_range = extract_employee_count(html)
    if emp_count:
        company.employee_count = emp_count
    if emp_range and not company.employee_count_range:
        company.employee_count_range = emp_range

    # If no revenue found but have employee data, estimate
    if not company.estimated_revenue and (company.employee_count or company.employee_count_range):
        est_rev, est_source = estimate_revenue(
            company.employee_count, company.employee_count_range, company.industry
        )
        if est_rev:
            company.estimated_revenue = est_rev
            company.revenue_source = est_source

    # Validate: must have a real name
    if not company.name or not _is_valid_company_name(company.name):
        return None

    return company


def _clean_title(title: str) -> str:
    """Extract company name from a page title by removing common suffixes."""
    # Split on common separators and take the first part
    for sep in [" | ", " - ", " — ", " – ", " :: ", " >> ", " » "]:
        if sep in title:
            title = title.split(sep)[0]
            break
    return title.strip()[:200]


def _is_valid_company_name(name: str) -> bool:
    """Check if a string looks like an actual company name."""
    if not name or len(name) < 2:
        return False
    if len(name) > 150:
        return False
    lower = name.lower()
    for indicator in BAD_NAME_INDICATORS:
        if indicator in lower:
            return False
    # Reject if it's mostly numbers
    alpha = sum(1 for c in name if c.isalpha())
    if alpha < 2:
        return False
    return True


def _name_from_domain(domain: str) -> str:
    """Generate a company name from a domain as last resort."""
    # Remove TLD
    parts = domain.split(".")
    if len(parts) >= 2:
        name = parts[0]
    else:
        name = domain
    # Capitalize
    return name.replace("-", " ").replace("_", " ").title()
