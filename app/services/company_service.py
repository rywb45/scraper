from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Company, Contact
from app.schemas.company import CompanyCreate, CompanyUpdate


REVENUE_BRACKETS = {
    "under_1m": (None, 1_000_000),
    "1m_10m": (1_000_000, 10_000_000),
    "10m_50m": (10_000_000, 50_000_000),
    "50m_100m": (50_000_000, 100_000_000),
    "100m_200m": (100_000_000, 200_000_000),
    "200m_500m": (200_000_000, 500_000_000),
    "500m_1b": (500_000_000, 1_000_000_000),
    "over_1b": (1_000_000_000, None),
}


def _parse_revenue_to_number(rev_str: str) -> float | None:
    """Convert revenue string like '$50M' or '$1.2B' to a number."""
    import re
    if not rev_str:
        return None
    rev_str = rev_str.replace("~", "").replace(",", "").strip()
    m = re.match(r"\$\s*([\d.]+)\s*(B|M|K)?", rev_str, re.IGNORECASE)
    if not m:
        return None
    val = float(m.group(1))
    suffix = (m.group(2) or "").upper()
    if suffix == "B":
        return val * 1_000_000_000
    elif suffix == "M":
        return val * 1_000_000
    elif suffix == "K":
        return val * 1_000
    return val


async def get_companies(
    db: AsyncSession,
    page: int = 1,
    per_page: int = 25,
    search: str | None = None,
    industry: str | None = None,
    state: str | None = None,
    city: str | None = None,
    revenue_bracket: str | None = None,
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
    if city:
        query = query.where(Company.city == city)

    # Revenue bracket filtering — needs Python since revenue is a formatted string
    if revenue_bracket and revenue_bracket in REVENUE_BRACKETS:
        low, high = REVENUE_BRACKETS[revenue_bracket]
        # Must filter in Python, so fetch all matching IDs first
        all_result = await db.execute(query.with_only_columns(Company.id, Company.estimated_revenue))
        matching_ids = []
        for cid, rev_str in all_result.all():
            val = _parse_revenue_to_number(rev_str)
            if val is None:
                continue
            if low is not None and val < low:
                continue
            if high is not None and val >= high:
                continue
            matching_ids.append(cid)
        if not matching_ids:
            return {"items": [], "total": 0, "page": page, "per_page": per_page, "pages": 1}
        query = select(Company).where(Company.id.in_(matching_ids))

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
        select(Company.state).where(Company.state.isnot(None)).where(Company.state != "").distinct().order_by(Company.state)
    )
    return [r[0] for r in result.all()]


async def get_distinct_cities(db: AsyncSession) -> list[str]:
    result = await db.execute(
        select(Company.city).where(Company.city.isnot(None)).where(Company.city != "").distinct().order_by(Company.city)
    )
    return [r[0] for r in result.all()]
