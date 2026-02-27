from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.schemas.company import CompanyCreate, CompanyList, CompanyOut, CompanyUpdate
from app.services import company_service

router = APIRouter()


@router.get("", response_model=CompanyList)
async def list_companies(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    search: str | None = None,
    industry: str | None = None,
    state: str | None = None,
    city: str | None = None,
    revenue_bracket: str | None = None,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
    db: AsyncSession = Depends(get_db),
):
    return await company_service.get_companies(
        db, page=page, per_page=per_page, search=search,
        industry=industry, state=state, city=city,
        revenue_bracket=revenue_bracket,
        sort_by=sort_by, sort_dir=sort_dir,
    )


@router.get("/industries")
async def list_industries(db: AsyncSession = Depends(get_db)):
    return await company_service.get_distinct_industries(db)


@router.get("/states")
async def list_states(db: AsyncSession = Depends(get_db)):
    return await company_service.get_distinct_states(db)


@router.get("/cities")
async def list_cities(db: AsyncSession = Depends(get_db)):
    return await company_service.get_distinct_cities(db)


@router.get("/{company_id}", response_model=CompanyOut)
async def get_company(company_id: int, db: AsyncSession = Depends(get_db)):
    company = await company_service.get_company(db, company_id)
    if not company:
        raise HTTPException(404, "Company not found")
    company.contact_count = len(company.contacts)
    return company


@router.post("", response_model=CompanyOut, status_code=201)
async def create_company(data: CompanyCreate, db: AsyncSession = Depends(get_db)):
    return await company_service.create_company(db, data)


@router.patch("/{company_id}", response_model=CompanyOut)
async def update_company(company_id: int, data: CompanyUpdate, db: AsyncSession = Depends(get_db)):
    company = await company_service.update_company(db, company_id, data)
    if not company:
        raise HTTPException(404, "Company not found")
    return company


@router.delete("/{company_id}", status_code=204)
async def delete_company(company_id: int, db: AsyncSession = Depends(get_db)):
    if not await company_service.delete_company(db, company_id):
        raise HTTPException(404, "Company not found")
