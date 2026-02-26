from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.services.export_service import export_companies_csv

router = APIRouter()


@router.get("/csv")
async def download_csv(
    industry: str | None = None,
    state: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    csv_content = await export_companies_csv(db, industry=industry, state=state)
    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=leads_export.csv"},
    )
