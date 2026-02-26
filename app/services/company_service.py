from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Company, Contact
from app.schemas.company import CompanyCreate, CompanyUpdate


async def get_companies(
    db: AsyncSession,
    page: int = 1,
    per_page: int = 25,
    search: str | None = None,
    industry: str | None = None,
    state: str | None = None,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
):
    query = select(Company)

    if search:
        pattern = f"%{search}%"
        query = query.where(
            (Company.name.ilike(pattern))
            | (Company.domain.ilike(pattern))
            | (Company.city.ilike(pattern))
        )
    if industry:
        query = query.where(Company.industry == industry)
    if state:
        query = query.where(Company.state == state)

    # Count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Sort
    sort_col = getattr(Company, sort_by, Company.created_at)
    query = query.order_by(sort_col.desc() if sort_dir == "desc" else sort_col.asc())

    # Paginate
    query = query.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    companies = result.scalars().all()

    # Attach contact counts
    if companies:
        ids = [c.id for c in companies]
        counts_q = (
            select(Contact.company_id, func.count(Contact.id))
            .where(Contact.company_id.in_(ids))
            .group_by(Contact.company_id)
        )
        counts = dict((await db.execute(counts_q)).all())
        for c in companies:
            c.contact_count = counts.get(c.id, 0)

    pages = max(1, (total + per_page - 1) // per_page)
    return {"items": companies, "total": total, "page": page, "per_page": per_page, "pages": pages}


async def get_company(db: AsyncSession, company_id: int):
    result = await db.execute(
        select(Company).options(selectinload(Company.contacts)).where(Company.id == company_id)
    )
    return result.scalar_one_or_none()


async def get_company_by_domain(db: AsyncSession, domain: str):
    result = await db.execute(select(Company).where(Company.domain == domain))
    return result.scalar_one_or_none()


async def create_company(db: AsyncSession, data: CompanyCreate) -> Company:
    existing = await get_company_by_domain(db, data.domain)
    if existing:
        return existing
    company = Company(**data.model_dump())
    db.add(company)
    await db.commit()
    await db.refresh(company)
    return company


async def update_company(db: AsyncSession, company_id: int, data: CompanyUpdate) -> Company | None:
    company = await get_company(db, company_id)
    if not company:
        return None
    for key, val in data.model_dump(exclude_unset=True).items():
        setattr(company, key, val)
    await db.commit()
    await db.refresh(company)
    return company


async def delete_company(db: AsyncSession, company_id: int) -> bool:
    company = await get_company(db, company_id)
    if not company:
        return False
    await db.delete(company)
    await db.commit()
    return True


async def get_distinct_industries(db: AsyncSession) -> list[str]:
    result = await db.execute(
        select(Company.industry).where(Company.industry.isnot(None)).distinct()
    )
    return [r[0] for r in result.all()]


async def get_distinct_states(db: AsyncSession) -> list[str]:
    result = await db.execute(
        select(Company.state).where(Company.state.isnot(None)).distinct().order_by(Company.state)
    )
    return [r[0] for r in result.all()]
