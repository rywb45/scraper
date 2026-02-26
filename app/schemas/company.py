from datetime import datetime

from pydantic import BaseModel


class CompanyBase(BaseModel):
    name: str
    domain: str
    website: str | None = None
    industry: str | None = None
    sub_industry: str | None = None
    description: str | None = None
    employee_count_range: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    country: str = "US"
    phone: str | None = None
    source: str | None = None
    source_url: str | None = None


class CompanyCreate(CompanyBase):
    scrape_job_id: int | None = None


class CompanyUpdate(BaseModel):
    name: str | None = None
    website: str | None = None
    industry: str | None = None
    sub_industry: str | None = None
    description: str | None = None
    employee_count_range: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    phone: str | None = None


class CompanyOut(CompanyBase):
    id: int
    contact_count: int = 0
    scrape_job_id: int | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CompanyList(BaseModel):
    items: list[CompanyOut]
    total: int
    page: int
    per_page: int
    pages: int
