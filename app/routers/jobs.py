import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models import ScrapeJob, ScrapeLog
from app.schemas.job import JobCreate, JobOut, JobUpdate, LogOut

router = APIRouter()


def _job_to_out(job: ScrapeJob) -> dict:
    total = job.total_urls or 0
    processed = job.processed_urls or 0
    progress = (processed / total * 100) if total > 0 else 0.0
    return {
        "id": job.id, "name": job.name, "status": job.status,
        "job_type": job.job_type, "industries": job.industries or "[]",
        "total_urls": total, "processed_urls": processed,
        "companies_found": job.companies_found or 0,
        "contacts_found": job.contacts_found or 0,
        "errors_count": job.errors_count or 0,
        "progress": round(progress, 1),
        "started_at": job.started_at, "completed_at": job.completed_at,
        "created_at": job.created_at,
    }


@router.get("", response_model=list[JobOut])
async def list_jobs(
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(ScrapeJob).order_by(ScrapeJob.created_at.desc())
    if status:
        query = query.where(ScrapeJob.status == status)
    result = await db.execute(query)
    return [_job_to_out(j) for j in result.scalars().all()]


@router.get("/{job_id}", response_model=JobOut)
async def get_job(job_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ScrapeJob).where(ScrapeJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Job not found")
    return _job_to_out(job)


@router.post("", response_model=JobOut, status_code=201)
async def create_job(data: JobCreate, db: AsyncSession = Depends(get_db)):
    config = {**data.config}
    if data.sources:
        config["sources"] = data.sources
    if data.location:
        config["location"] = data.location
    job = ScrapeJob(
        name=data.name,
        job_type=data.job_type,
        industries=json.dumps(data.industries),
        config=json.dumps(config),
        status="pending",
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return _job_to_out(job)


@router.patch("/{job_id}", response_model=JobOut)
async def update_job(job_id: int, data: JobUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ScrapeJob).where(ScrapeJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Job not found")
    if data.name is not None:
        job.name = data.name
    if data.status is not None:
        job.status = data.status
    await db.commit()
    await db.refresh(job)
    return _job_to_out(job)


@router.post("/{job_id}/pause", response_model=JobOut)
async def pause_job(job_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ScrapeJob).where(ScrapeJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Job not found")
    if job.status != "running":
        raise HTTPException(400, "Can only pause running jobs")
    job.status = "paused"
    await db.commit()
    await db.refresh(job)
    return _job_to_out(job)


@router.post("/{job_id}/resume", response_model=JobOut)
async def resume_job(job_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ScrapeJob).where(ScrapeJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Job not found")
    if job.status != "paused":
        raise HTTPException(400, "Can only resume paused jobs")
    job.status = "running"
    await db.commit()
    await db.refresh(job)
    return _job_to_out(job)


@router.post("/{job_id}/start", response_model=JobOut)
async def start_job(job_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ScrapeJob).where(ScrapeJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Job not found")
    if job.status not in ("pending",):
        raise HTTPException(400, "Can only start pending jobs")
    from app.scraper.engine import start_job as engine_start
    await engine_start(job_id)
    await db.refresh(job)
    return _job_to_out(job)


@router.post("/{job_id}/cancel", response_model=JobOut)
async def cancel_job(job_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ScrapeJob).where(ScrapeJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Job not found")
    if job.status in ("completed", "cancelled"):
        raise HTTPException(400, f"Job already {job.status}")
    job.status = "cancelled"
    await db.commit()
    await db.refresh(job)
    from app.scraper.engine import cancel_job as engine_cancel
    await engine_cancel(job_id)
    return _job_to_out(job)


@router.get("/{job_id}/logs", response_model=list[LogOut])
async def get_job_logs(
    job_id: int,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ScrapeLog)
        .where(ScrapeLog.scrape_job_id == job_id)
        .order_by(ScrapeLog.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return result.scalars().all()


@router.delete("/{job_id}", status_code=204)
async def delete_job(job_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ScrapeJob).where(ScrapeJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Job not found")
    await db.delete(job)
    await db.commit()
