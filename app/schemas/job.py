from datetime import datetime

from pydantic import BaseModel


class JobCreate(BaseModel):
    name: str
    job_type: str = "full"  # discovery, enrichment, full
    industries: list[str] = []
    sources: list[str] = []  # google, thomasnet, kompass, industrynet (empty = all)
    location: str = ""  # optional geographic filter e.g. "Texas", "Chicago IL"
    config: dict = {}


class JobUpdate(BaseModel):
    name: str | None = None
    status: str | None = None


class JobOut(BaseModel):
    id: int
    name: str
    status: str
    job_type: str | None
    industries: str  # JSON string
    total_urls: int
    processed_urls: int
    companies_found: int
    contacts_found: int
    errors_count: int
    progress: float = 0.0
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class LogOut(BaseModel):
    id: int
    level: str
    message: str
    url: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
