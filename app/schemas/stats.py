from pydantic import BaseModel


class IndustryBreakdown(BaseModel):
    industry: str
    company_count: int
    contact_count: int


class DashboardStats(BaseModel):
    total_companies: int
    total_contacts: int
    total_jobs: int
    active_jobs: int
    industries: list[IndustryBreakdown]
    recent_jobs: list[dict]
    recent_companies: list[dict]
