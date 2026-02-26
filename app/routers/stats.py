from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models import Company, Contact, ScrapeJob
from app.schemas.stats import DashboardStats, IndustryBreakdown

router = APIRouter()


@router.get("", response_model=DashboardStats)
async def get_stats(db: AsyncSession = Depends(get_db)):
    total_companies = (await db.execute(select(func.count(Company.id)))).scalar() or 0
    total_contacts = (await db.execute(select(func.count(Contact.id)))).scalar() or 0
    total_jobs = (await db.execute(select(func.count(ScrapeJob.id)))).scalar() or 0
    active_jobs = (
        await db.execute(
            select(func.count(ScrapeJob.id)).where(ScrapeJob.status.in_(["running", "pending"]))
        )
    ).scalar() or 0

    # Industry breakdown
    industry_q = (
        select(Company.industry, func.count(Company.id))
        .where(Company.industry.isnot(None))
        .group_by(Company.industry)
        .order_by(func.count(Company.id).desc())
    )
    industry_rows = (await db.execute(industry_q)).all()

    industries = []
    for industry_name, count in industry_rows:
        contact_count = (
            await db.execute(
                select(func.count(Contact.id))
                .join(Company)
                .where(Company.industry == industry_name)
            )
        ).scalar() or 0
        industries.append(IndustryBreakdown(
            industry=industry_name, company_count=count, contact_count=contact_count,
        ))

    # Recent jobs
    recent_jobs_q = select(ScrapeJob).order_by(ScrapeJob.created_at.desc()).limit(5)
    recent_jobs = (await db.execute(recent_jobs_q)).scalars().all()
    recent_jobs_data = [
        {"id": j.id, "name": j.name, "status": j.status, "companies_found": j.companies_found,
         "contacts_found": j.contacts_found, "created_at": j.created_at.isoformat()}
        for j in recent_jobs
    ]

    # Recent companies
    recent_companies_q = select(Company).order_by(Company.created_at.desc()).limit(5)
    recent_companies = (await db.execute(recent_companies_q)).scalars().all()
    recent_companies_data = [
        {"id": c.id, "name": c.name, "domain": c.domain, "industry": c.industry,
         "state": c.state, "created_at": c.created_at.isoformat()}
        for c in recent_companies
    ]

    return DashboardStats(
        total_companies=total_companies,
        total_contacts=total_contacts,
        total_jobs=total_jobs,
        active_jobs=active_jobs,
        industries=industries,
        recent_jobs=recent_jobs_data,
        recent_companies=recent_companies_data,
    )
