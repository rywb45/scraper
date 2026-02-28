"""Shared utilities for directory scrapers (ThomasNet, Kompass, IndustryNet)."""

import re
from urllib.parse import urlparse

from app.scraper.serper_keys import serper_search

SOCIAL_DOMAINS = {
    "wikipedia.org", "youtube.com", "facebook.com", "twitter.com",
    "linkedin.com", "instagram.com", "reddit.com", "yelp.com",
    "indeed.com", "glassdoor.com", "bbb.org", "crunchbase.com",
    "thomasnet.com", "kompass.com", "industrynet.com",
    "bloomberg.com", "reuters.com", "forbes.com",
    "amazon.com", "ebay.com", "google.com", "yahoo.com",
}

US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC",
}


def is_social_domain(domain: str) -> bool:
    for d in SOCIAL_DOMAINS:
        if domain == d or domain.endswith(f".{d}"):
            return True
    return False


def extract_name_from_title(title: str) -> str:
    """Extract company name from a directory search result title.

    Handles formats like:
      "Company Name: City, ST ZIP - Thomasnet"
      "Company Name - Supplier of ..."
    """
    if not title:
        return ""
    for sep in [" - ", " | ", " — ", " – "]:
        if sep in title:
            title = title.split(sep)[0]
            break
    if ": " in title:
        parts = title.split(": ", 1)
        after = parts[1].strip()
        if re.match(r"[A-Z][a-z]+.*,\s*[A-Z]{2}", after):
            title = parts[0]
    name = title.strip()
    return name[:200] if len(name) >= 2 else ""


def extract_location_from_snippet(snippet: str) -> tuple[str, str]:
    """Try to extract city, state from a snippet."""
    match = re.search(r"([A-Z][a-z]+(?:\s[A-Z][a-z]+)*),\s*([A-Z]{2})\b", snippet)
    if match and match.group(2) in US_STATES:
        return match.group(1).strip(), match.group(2)
    return "", ""


def extract_domain_from_snippet(snippet: str, exclude_domain: str) -> tuple[str, str]:
    """Try to extract a company domain/website URL from a snippet.

    Returns (domain, website_url) or ("", "").
    """
    # Look for URLs in the snippet text
    url_match = re.search(r"(https?://[a-zA-Z0-9.-]+\.[a-z]{2,})", snippet)
    if url_match:
        url = url_match.group(1)
        parsed = urlparse(url)
        domain = parsed.netloc.lower().removeprefix("www.")
        if domain and "." in domain and domain != exclude_domain and not is_social_domain(domain):
            return domain, f"{parsed.scheme}://{parsed.netloc}"

    # Look for bare domain patterns like "www.example.com" or "example.com"
    domain_match = re.search(r"\b((?:www\.)?[a-zA-Z0-9-]+\.[a-z]{2,}(?:\.[a-z]{2,})?)\b", snippet)
    if domain_match:
        domain = domain_match.group(1).lower().removeprefix("www.")
        if domain and domain != exclude_domain and not is_social_domain(domain):
            return domain, f"https://{domain}"

    return "", ""


async def find_company_website(name: str) -> tuple[str, str]:
    """Use a quick Google search to find the company's website.

    Returns (domain, website_url) or ("", "").
    """
    data = await serper_search(f"{name} official website", num=3)
    if not data:
        return "", ""
    for r in data.get("organic", []):
        link = r.get("link", "")
        if not link:
            continue
        parsed = urlparse(link)
        domain = parsed.netloc.lower().removeprefix("www.")
        if domain and "." in domain and not is_social_domain(domain):
            return domain, f"{parsed.scheme}://{parsed.netloc}"
    return "", ""
