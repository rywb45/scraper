from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ScrapedContact:
    first_name: str = ""
    last_name: str = ""
    full_name: str = ""
    title: str = ""
    email: str = ""
    email_confidence: float = 0.0
    phone: str = ""
    linkedin_url: str = ""
    source: str = ""
    source_url: str = ""


@dataclass
class ScrapedCompany:
    name: str = ""
    domain: str = ""
    website: str = ""
    industry: str = ""
    sub_industry: str = ""
    description: str = ""
    employee_count_range: str = ""
    city: str = ""
    state: str = ""
    zip_code: str = ""
    country: str = "US"
    phone: str = ""
    source: str = ""
    source_url: str = ""
    contacts: list[ScrapedContact] = field(default_factory=list)


class BaseScraper(ABC):
    name: str = "base"

    @abstractmethod
    async def search(self, query: str, num_results: int = 10) -> list[str]:
        """Return a list of URLs matching the query."""

    @abstractmethod
    async def scrape_company(self, url: str) -> ScrapedCompany | None:
        """Scrape company info from a URL."""
