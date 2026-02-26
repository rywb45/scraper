import asyncio
import json
import logging
from urllib.parse import urlparse

from app.config import settings
from app.db.database import async_session
from app.db.models import ScrapeJob
from app.industries.query_templates import generate_queries
from app.schemas.company import CompanyCreate
from app.schemas.contact import ContactCreate
from app.scraper.base import ScrapedCompany
from app.scraper.extractors.contact_extractor import extract_contacts
from app.scraper.extractors.email_discoverer import discover_email_pattern, generate_email_candidates
from app.scraper.http_client import HttpClient
from app.scraper.sources.google_search import GoogleSearchScraper
from app.scraper.sources.industrynet import IndustryNetScraper
from app.scraper.sources.kompass import KompassScraper
from app.scraper.sources.thomasnet import ThomasNetScraper
from app.services import company_service, contact_service, job_service

logger = logging.getLogger(__name__)

# Active jobs registry
_active_jobs: dict[int, asyncio.Task] = {}


def get_scrapers():
    return {
        "google": GoogleSearchScraper(),
        "thomasnet": ThomasNetScraper(),
        "kompass": KompassScraper(),
        "industrynet": IndustryNetScraper(),
    }


async def start_job(job_id: int):
    """Launch a scrape job in the background."""
    if job_id in _active_jobs:
        return
    task = asyncio.create_task(_run_job(job_id))
    _active_jobs[job_id] = task

    def _cleanup(t):
        _active_jobs.pop(job_id, None)

    task.add_done_callback(_cleanup)


async def cancel_job(job_id: int):
    task = _active_jobs.get(job_id)
    if task and not task.done():
        task.cancel()


async def _run_job(job_id: int):
    async with async_session() as db:
        job = await job_service.get_job(db, job_id)
        if not job:
            return

        await job_service.update_job_status(db, job_id, "running")
        await job_service.add_log(db, job_id, "info", "Job started")

        try:
            industries = json.loads(job.industries or "[]")
            job_type = job.job_type or "full"

            if job_type in ("discovery", "full"):
                await _phase_discovery(db, job_id, industries)

            if job_type in ("enrichment", "full"):
                await _phase_enrichment(db, job_id)

            if settings.enable_email_pattern_matching and job_type in ("enrichment", "full"):
                await _phase_email_patterns(db, job_id)

            await job_service.update_job_status(db, job_id, "completed")
            await job_service.add_log(db, job_id, "info", "Job completed successfully")

        except asyncio.CancelledError:
            await job_service.update_job_status(db, job_id, "cancelled")
            await job_service.add_log(db, job_id, "info", "Job cancelled")
        except Exception as e:
            logger.exception(f"Job {job_id} failed")
            await job_service.update_job_status(db, job_id, "failed")
            await job_service.add_log(db, job_id, "error", f"Job failed: {e}")


async def _phase_discovery(db, job_id: int, industries: list[str]):
    """Phase 1: Discover companies via search."""
    await job_service.add_log(db, job_id, "info", "Starting discovery phase")
    scrapers = get_scrapers()
    total_urls = 0
    processed = 0
    companies_found = 0
    errors = 0

    for industry in industries:
        await _check_job_status(db, job_id)
        queries = generate_queries(industry, "google")
        await job_service.add_log(db, job_id, "info", f"Searching for {industry} ({len(queries)} queries)")

        for query in queries:
            await _check_job_status(db, job_id)

            for source_name, scraper in scrapers.items():
                try:
                    urls = await scraper.search(query, num_results=10)
                    total_urls += len(urls)
                    await job_service.update_job_progress(db, job_id, total_urls=total_urls)

                    for url in urls:
                        await _check_job_status(db, job_id)
                        try:
                            company_data = await scraper.scrape_company(url)
                            processed += 1

                            if company_data and company_data.name and company_data.domain:
                                company_data.industry = industry
                                saved = await _save_company(db, job_id, company_data)
                                if saved:
                                    companies_found += 1

                            await job_service.update_job_progress(
                                db, job_id,
                                processed_urls=processed,
                                companies_found=companies_found,
                                errors_count=errors,
                            )
                        except Exception as e:
                            errors += 1
                            await job_service.add_log(db, job_id, "error", f"Error scraping {url}: {e}", url=url)
                            await job_service.update_job_progress(db, job_id, errors_count=errors)

                except Exception as e:
                    errors += 1
                    await job_service.add_log(db, job_id, "warning", f"Search failed ({source_name}): {e}")

    await job_service.add_log(db, job_id, "info",
                              f"Discovery complete: {companies_found} companies from {processed} URLs")


async def _phase_enrichment(db, job_id: int):
    """Phase 2: Enrich companies with contact information."""
    await job_service.add_log(db, job_id, "info", "Starting contact enrichment phase")
    http = HttpClient()

    # Get all companies from this job
    from sqlalchemy import select
    from app.db.models import Company
    result = await db.execute(
        select(Company).where(Company.scrape_job_id == job_id)
    )
    companies = result.scalars().all()
    contacts_found = 0

    for company in companies:
        await _check_job_status(db, job_id)
        if not company.website:
            continue

        contact_pages = [
            f"{company.website}/contact",
            f"{company.website}/about",
            f"{company.website}/team",
            f"{company.website}/about-us",
            f"{company.website}/our-team",
            f"{company.website}/leadership",
        ]

        for page_url in contact_pages:
            try:
                resp = await http.get(page_url)
                if resp and resp.status_code == 200:
                    contacts = extract_contacts(resp.text, source_url=page_url)
                    for contact_data in contacts:
                        try:
                            await contact_service.create_contact(db, ContactCreate(
                                company_id=company.id,
                                first_name=contact_data.first_name,
                                last_name=contact_data.last_name,
                                full_name=contact_data.full_name,
                                title=contact_data.title,
                                email=contact_data.email,
                                email_confidence=contact_data.email_confidence,
                                phone=contact_data.phone,
                                linkedin_url=contact_data.linkedin_url,
                                source=contact_data.source,
                                source_url=contact_data.source_url,
                            ))
                            contacts_found += 1
                        except Exception:
                            pass  # Duplicate or constraint violation
            except Exception as e:
                await job_service.add_log(db, job_id, "warning",
                                          f"Error enriching {company.name}: {e}", url=page_url)

        await job_service.update_job_progress(db, job_id, contacts_found=contacts_found)

    await job_service.add_log(db, job_id, "info", f"Enrichment complete: {contacts_found} contacts found")


async def _phase_email_patterns(db, job_id: int):
    """Phase 3: Discover email patterns and generate guesses."""
    await job_service.add_log(db, job_id, "info", "Starting email pattern matching phase")

    from sqlalchemy import select
    from app.db.models import Company, Contact

    result = await db.execute(
        select(Company).where(Company.scrape_job_id == job_id)
    )
    companies = result.scalars().all()
    generated = 0

    for company in companies:
        await _check_job_status(db, job_id)
        if not company.domain:
            continue

        # Get existing contacts for this company
        contacts_result = await db.execute(
            select(Contact).where(Contact.company_id == company.id)
        )
        contacts = list(contacts_result.scalars().all())

        known_emails = [c.email for c in contacts if c.email]
        pattern = discover_email_pattern(known_emails, company.domain)

        # Generate emails for contacts without one
        for contact in contacts:
            if contact.email:
                continue
            if not contact.first_name or not contact.last_name:
                continue

            from app.scraper.base import ScrapedContact as SC
            sc = SC(first_name=contact.first_name, last_name=contact.last_name)
            candidates = generate_email_candidates(sc, company.domain, pattern)

            if candidates:
                best_email, best_conf = candidates[0]
                contact.email = best_email
                contact.email_confidence = best_conf
                generated += 1

        await db.commit()

    await job_service.add_log(db, job_id, "info", f"Email patterns: generated {generated} email guesses")


async def _save_company(db, job_id: int, data: ScrapedCompany):
    """Save a scraped company, deduplicating by domain."""
    existing = await company_service.get_company_by_domain(db, data.domain)
    if existing:
        return None

    company = await company_service.create_company(db, CompanyCreate(
        name=data.name,
        domain=data.domain,
        website=data.website,
        industry=data.industry,
        sub_industry=data.sub_industry,
        description=data.description,
        employee_count_range=data.employee_count_range,
        city=data.city,
        state=data.state,
        zip_code=data.zip_code,
        country=data.country,
        phone=data.phone,
        source=data.source,
        source_url=data.source_url,
        scrape_job_id=job_id,
    ))

    await job_service.add_log(db, job_id, "info", f"Found: {data.name} ({data.domain})", url=data.source_url)
    return company


async def _check_job_status(db, job_id: int):
    """Check if job is still active; raise if paused/cancelled."""
    job = await job_service.get_job(db, job_id)
    if not job:
        raise asyncio.CancelledError()
    if job.status == "cancelled":
        raise asyncio.CancelledError()
    if job.status == "paused":
        # Wait until resumed or cancelled
        while True:
            await asyncio.sleep(2)
            await db.refresh(job)
            if job.status == "running":
                return
            if job.status in ("cancelled", "failed"):
                raise asyncio.CancelledError()
