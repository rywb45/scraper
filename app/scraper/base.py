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
    employee_count: int | None = None
    estimated_revenue: str = ""
    revenue_source: str = ""
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
    async def search(self, query: str, num_results: int = 10) -> list[dict]:
        """Return a list of result dicts matching the query.

        Each dict contains:
            url: str - the result URL
            title: str - the result title
            snippet: str - the result snippet/description
            domain: str - extracted domain from URL
            knowledge_graph: dict | None - KG data from Serper (first result only)
        """

    @abstractmethod
    async def scrape_company(self, result: dict | str) -> ScrapedCompany | None:
        """Scrape company info from a search result dict or URL string."""
