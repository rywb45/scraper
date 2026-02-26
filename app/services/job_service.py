from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ScrapeJob, ScrapeLog, ScrapeQueue


async def get_job(db: AsyncSession, job_id: int) -> ScrapeJob | None:
    result = await db.execute(select(ScrapeJob).where(ScrapeJob.id == job_id))
    return result.scalar_one_or_none()


async def update_job_status(db: AsyncSession, job_id: int, status: str):
    job = await get_job(db, job_id)
    if not job:
        return
    job.status = status
    if status == "running" and not job.started_at:
        job.started_at = datetime.now(timezone.utc)
    if status in ("completed", "failed", "cancelled"):
        job.completed_at = datetime.now(timezone.utc)
    await db.commit()


async def update_job_progress(
    db: AsyncSession,
    job_id: int,
    processed_urls: int | None = None,
    total_urls: int | None = None,
    companies_found: int | None = None,
    contacts_found: int | None = None,
    errors_count: int | None = None,
):
    job = await get_job(db, job_id)
    if not job:
        return
    if processed_urls is not None:
        job.processed_urls = processed_urls
    if total_urls is not None:
        job.total_urls = total_urls
    if companies_found is not None:
        job.companies_found = companies_found
    if contacts_found is not None:
        job.contacts_found = contacts_found
    if errors_count is not None:
        job.errors_count = errors_count
    await db.commit()


async def add_log(db: AsyncSession, job_id: int, level: str, message: str, url: str | None = None):
    log = ScrapeLog(scrape_job_id=job_id, level=level, message=message, url=url)
    db.add(log)
    await db.commit()


async def add_to_queue(db: AsyncSession, job_id: int, url: str, url_type: str = "company_page", priority: int = 0):
    item = ScrapeQueue(scrape_job_id=job_id, url=url, url_type=url_type, priority=priority)
    db.add(item)
    await db.commit()
    return item


async def get_pending_queue_items(db: AsyncSession, job_id: int, limit: int = 10) -> list[ScrapeQueue]:
    result = await db.execute(
        select(ScrapeQueue)
        .where(ScrapeQueue.scrape_job_id == job_id, ScrapeQueue.status == "pending")
        .order_by(ScrapeQueue.priority.desc(), ScrapeQueue.id)
        .limit(limit)
    )
    return list(result.scalars().all())


async def update_queue_item(db: AsyncSession, item_id: int, status: str, error_message: str | None = None):
    result = await db.execute(select(ScrapeQueue).where(ScrapeQueue.id == item_id))
    item = result.scalar_one_or_none()
    if item:
        item.status = status
        if error_message:
            item.error_message = error_message
        if status in ("completed", "failed"):
            item.processed_at = datetime.now(timezone.utc)
        await db.commit()
