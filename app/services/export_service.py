import csv
import io

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Company


async def export_companies_csv(
    db: AsyncSession,
    industry: str | None = None,
    state: str | None = None,
) -> str:
    query = select(Company).options(selectinload(Company.contacts))

    if industry:
        query = query.where(Company.industry == industry)
    if state:
        query = query.where(Company.state == state)

    query = query.order_by(Company.name)
    result = await db.execute(query)
    companies = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Company Name", "Domain", "Website", "Industry", "Sub-Industry",
        "Description", "Employee Count", "City", "State", "Zip", "Phone",
        "Contact Name", "Contact Title", "Contact Email", "Email Confidence",
        "Contact Phone", "LinkedIn URL", "Source",
    ])

    for company in companies:
        if company.contacts:
            for contact in company.contacts:
                writer.writerow([
                    company.name, company.domain, company.website,
                    company.industry, company.sub_industry, company.description,
                    company.employee_count_range, company.city, company.state,
                    company.zip_code, company.phone,
                    contact.full_name, contact.title, contact.email,
                    contact.email_confidence, contact.phone, contact.linkedin_url,
                    company.source,
                ])
        else:
            writer.writerow([
                company.name, company.domain, company.website,
                company.industry, company.sub_industry, company.description,
                company.employee_count_range, company.city, company.state,
                company.zip_code, company.phone,
                "", "", "", "", "", "", company.source,
            ])

    return output.getvalue()
