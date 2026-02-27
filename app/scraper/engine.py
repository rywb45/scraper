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
from app.scraper.extractors.data_enricher import enrich_company
from app.scraper.extractors.email_discoverer import discover_email_pattern, generate_email_candidates
from app.scraper.http_client import HttpClient
from app.scraper.sources.google_search import GoogleSearchScraper
from app.scraper.sources.thomasnet import ThomasNetScraper
from app.scraper.sources.kompass import KompassScraper
from app.scraper.sources.industrynet import IndustryNetScraper
from app.services import company_service, contact_service, job_service

logger = logging.getLogger(__name__)

_active_jobs: dict[int, asyncio.Task] = {}


async def cleanup_stale_jobs():
    """Mark any 'running' or 'pending' jobs as failed on startup (orphaned from restart)."""
    from sqlalchemy import select, update
    async with async_session() as db:
        result = await db.execute(
            update(ScrapeJob)
            .where(ScrapeJob.status.in_(["running", "pending"]))
            .values(status="failed")
        )
        if result.rowcount:
            await db.commit()
            logger.info(f"Cleaned up {result.rowcount} stale job(s)")


async def start_job(job_id: int):
    if job_id in _active_jobs:
        return
    task = asyncio.create_task(_run_job(job_id))
    _active_jobs[job_id] = task
    task.add_done_callback(lambda t: _active_jobs.pop(job_id, None))


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

            # For enrichment-only jobs, run batch enrichment on existing companies
            if job_type == "enrichment":
                await _phase_data_enrichment(db, job_id)

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
    await job_service.add_log(db, job_id, "info", "Starting discovery phase")
    scraper = GoogleSearchScraper()

    total_urls = 0
    processed = 0
    companies_found = 0
    errors = 0
    seen_domains = set()

    for industry in industries:
        await _check_job_status(db, job_id)
        queries = generate_queries(industry)
        await job_service.add_log(db, job_id, "info", f"Searching {industry} ({len(queries)} queries)")

        for query in queries:
            await _check_job_status(db, job_id)

            try:
                urls = await scraper.search(query, num_results=10)
                if not urls:
                    continue

                # Deduplicate by domain before scraping
                new_urls = []
                for url in urls:
                    domain = urlparse(url).netloc.lower().removeprefix("www.")
                    if domain not in seen_domains:
                        seen_domains.add(domain)
                        new_urls.append(url)

                total_urls += len(new_urls)
                await job_service.update_job_progress(db, job_id, total_urls=total_urls)

                for url in new_urls:
                    await _check_job_status(db, job_id)
                    try:
                        company_data = await scraper.scrape_company(url)
                        processed += 1

                        if company_data and company_data.name and company_data.domain:
                            # Skip if domain already saved
                            if await company_service.get_company_by_domain(db, company_data.domain):
                                await job_service.update_job_progress(db, job_id, processed_urls=processed)
                                continue

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
                        processed += 1
                        await job_service.add_log(db, job_id, "error", f"Scrape error: {e}", url=url)
                        await job_service.update_job_progress(
                            db, job_id, processed_urls=processed, errors_count=errors
                        )

            except Exception as e:
                errors += 1
                await job_service.add_log(db, job_id, "warning", f"Search failed: {e}")

    # Phase 2: Directory sources (ThomasNet, Kompass, IndustryNet) — uses site: Google searches
    directory_scrapers = [
        ("ThomasNet", ThomasNetScraper()),
        ("Kompass", KompassScraper()),
        ("IndustryNet", IndustryNetScraper()),
    ]

    for source_name, dir_scraper in directory_scrapers:
        await _check_job_status(db, job_id)
        await job_service.add_log(db, job_id, "info", f"Searching {source_name}...")
        dir_found = 0

        for industry in industries:
            await _check_job_status(db, job_id)
            try:
                results = await dir_scraper.search(industry, num_results=10)
                if not results:
                    continue

                for result in results:
                    await _check_job_status(db, job_id)
                    try:
                        company_data = await dir_scraper.scrape_company(result)
                        processed += 1

                        if company_data and company_data.name and company_data.domain:
                            # Skip duplicates
                            domain = company_data.domain.lower().removeprefix("www.")
                            if domain in seen_domains:
                                continue
                            seen_domains.add(domain)

                            if await company_service.get_company_by_domain(db, domain):
                                continue

                            company_data.industry = industry
                            saved = await _save_company(db, job_id, company_data)
                            if saved:
                                companies_found += 1
                                dir_found += 1

                        await job_service.update_job_progress(
                            db, job_id,
                            processed_urls=processed,
                            companies_found=companies_found,
                            errors_count=errors,
                        )
                    except Exception as e:
                        errors += 1
                        processed += 1

            except Exception as e:
                await job_service.add_log(db, job_id, "warning", f"{source_name} search failed: {e}")

        await job_service.add_log(db, job_id, "info", f"{source_name}: found {dir_found} new companies")

    await job_service.add_log(
        db, job_id, "info",
        f"Discovery complete: {companies_found} companies from {processed} URLs across {len(industries)} industries"
    )


async def _phase_data_enrichment(db, job_id: int):
    """Use Google search to fill in missing revenue, employee count, and location."""
    await job_service.add_log(db, job_id, "info", "Starting data enrichment (revenue, employees, location)")

    from sqlalchemy import select
    from app.db.models import Company
    from app.scraper.extractors.data_enricher import enrich_company

    result = await db.execute(select(Company).where(Company.scrape_job_id == job_id))
    companies = result.scalars().all()
    enriched = 0

    for company in companies:
        await _check_job_status(db, job_id)

        needs_revenue = not company.estimated_revenue
        needs_employees = not company.employee_count
        needs_state = not company.state

        if not (needs_revenue or needs_employees or needs_state):
            continue

        try:
            data = await enrich_company(company.name, company.domain)

            updated = False
            if needs_revenue and data["estimated_revenue"]:
                company.estimated_revenue = data["estimated_revenue"]
                company.revenue_source = data["revenue_source"]
                updated = True
            if needs_employees and data["employee_count"]:
                company.employee_count = data["employee_count"]
                company.employee_count_range = data["employee_count_range"]
                updated = True
            if needs_state and data["state"]:
                company.state = data["state"]
                company.city = data["city"]
                updated = True

            if updated:
                await db.commit()
                enriched += 1
                await job_service.add_log(
                    db, job_id, "info",
                    f"Enriched {company.name}: "
                    + ", ".join(filter(None, [
                        data["estimated_revenue"] and f"rev={data['estimated_revenue']}",
                        data["employee_count"] and f"emp={data['employee_count']}",
                        data["state"] and f"loc={data['city']}, {data['state']}",
                    ]))
                )
        except Exception as e:
            await job_service.add_log(db, job_id, "warning", f"Enrich failed for {company.name}: {e}")

    await job_service.add_log(db, job_id, "info", f"Data enrichment complete: {enriched}/{len(companies)} companies enriched")


async def _phase_enrichment(db, job_id: int):
    await job_service.add_log(db, job_id, "info", "Starting contact enrichment phase")
    http = HttpClient()

    from sqlalchemy import select
    from app.db.models import Company
    result = await db.execute(select(Company).where(Company.scrape_job_id == job_id))
    companies = result.scalars().all()
    contacts_found = 0

    for company in companies:
        await _check_job_status(db, job_id)
        if not company.website:
            continue

        base = company.website.rstrip("/")
        contact_pages = [
            f"{base}/contact",
            f"{base}/contact-us",
            f"{base}/about",
            f"{base}/about-us",
            f"{base}/team",
            f"{base}/our-team",
            f"{base}/leadership",
        ]

        for page_url in contact_pages:
            try:
                resp = await http.get(page_url)
                if resp and resp.status_code == 200:
                    page_html = resp.text
                    contacts = extract_contacts(page_html, source_url=page_url)
                    for c in contacts:
                        try:
                            await contact_service.create_contact(db, ContactCreate(
                                company_id=company.id,
                                first_name=c.first_name, last_name=c.last_name,
                                full_name=c.full_name, title=c.title,
                                email=c.email, email_confidence=c.email_confidence,
                                phone=c.phone, linkedin_url=c.linkedin_url,
                                source=c.source, source_url=c.source_url,
                            ))
                            contacts_found += 1
                        except Exception:
                            pass

                    # Try to fill in missing revenue/employee data from about pages
                    if not company.estimated_revenue or not company.employee_count:
                        from app.scraper.extractors.revenue_extractor import (
                            estimate_revenue, extract_employee_count, extract_revenue,
                        )
                        if not company.estimated_revenue:
                            rev, rev_src = extract_revenue(page_html)
                            if rev:
                                company.estimated_revenue = rev
                                company.revenue_source = rev_src
                        if not company.employee_count:
                            emp, emp_range = extract_employee_count(page_html)
                            if emp:
                                company.employee_count = emp
                                if emp_range:
                                    company.employee_count_range = emp_range
                        if not company.estimated_revenue and company.employee_count:
                            est_rev, est_src = estimate_revenue(
                                company.employee_count, company.employee_count_range or "",
                                company.industry or ""
                            )
                            if est_rev:
                                company.estimated_revenue = est_rev
                                company.revenue_source = est_src
                        await db.commit()
            except Exception:
                pass

        await job_service.update_job_progress(db, job_id, contacts_found=contacts_found)

    await job_service.add_log(db, job_id, "info", f"Enrichment complete: {contacts_found} contacts")


async def _phase_email_patterns(db, job_id: int):
    await job_service.add_log(db, job_id, "info", "Starting email pattern matching")

    from sqlalchemy import select
    from app.db.models import Company, Contact

    result = await db.execute(select(Company).where(Company.scrape_job_id == job_id))
    companies = result.scalars().all()
    generated = 0

    for company in companies:
        await _check_job_status(db, job_id)
        if not company.domain:
            continue

        contacts_result = await db.execute(
            select(Contact).where(Contact.company_id == company.id)
        )
        contacts = list(contacts_result.scalars().all())
        known_emails = [c.email for c in contacts if c.email]
        pattern = discover_email_pattern(known_emails, company.domain)

        for contact in contacts:
            if contact.email or not contact.first_name or not contact.last_name:
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

    await job_service.add_log(db, job_id, "info", f"Email patterns: generated {generated} guesses")


async def _save_company(db, job_id: int, data: ScrapedCompany):
    company = await company_service.create_company(db, CompanyCreate(
        name=data.name, domain=data.domain, website=data.website,
        industry=data.industry, sub_industry=data.sub_industry,
        description=data.description, employee_count_range=data.employee_count_range,
        employee_count=data.employee_count,
        estimated_revenue=data.estimated_revenue, revenue_source=data.revenue_source,
        city=data.city, state=data.state, zip_code=data.zip_code,
        country=data.country, phone=data.phone,
        source=data.source, source_url=data.source_url,
        scrape_job_id=job_id,
    ))
    await job_service.add_log(db, job_id, "info", f"Found: {data.name} ({data.domain})", url=data.source_url)

    # Enrich immediately — revenue, employees, location via Google search
    try:
        await _enrich_single_company(db, job_id, company)
    except Exception as e:
        await job_service.add_log(db, job_id, "warning", f"Enrich failed for {data.name}: {e}")

    return company


async def _enrich_single_company(db, job_id: int, company):
    """Enrich a single company with revenue, employee count, and location right after saving."""
    needs_revenue = not company.estimated_revenue
    needs_employees = not company.employee_count
    needs_state = not company.state

    if not (needs_revenue or needs_employees or needs_state):
        return

    data = await enrich_company(company.name, company.domain)

    updated = False
    if needs_revenue and data["estimated_revenue"]:
        company.estimated_revenue = data["estimated_revenue"]
        company.revenue_source = data["revenue_source"]
        updated = True
    if needs_employees and data["employee_count"]:
        company.employee_count = data["employee_count"]
        company.employee_count_range = data["employee_count_range"]
        updated = True
    if needs_state and data["state"]:
        company.state = data["state"]
        company.city = data["city"]
        updated = True

    if updated:
        await db.commit()
        enriched_fields = ", ".join(filter(None, [
            data["estimated_revenue"] and f"rev={data['estimated_revenue']}",
            data["employee_count"] and f"emp={data['employee_count']}",
            data["state"] and f"loc={data['city']}, {data['state']}",
        ]))
        await job_service.add_log(db, job_id, "info", f"Enriched {company.name}: {enriched_fields}")


async def _check_job_status(db, job_id: int):
    job = await job_service.get_job(db, job_id)
    if not job or job.status == "cancelled":
        raise asyncio.CancelledError()
    if job.status == "paused":
        while True:
            await asyncio.sleep(2)
            await db.refresh(job)
            if job.status == "running":
                return
            if job.status in ("cancelled", "failed"):
                raise asyncio.CancelledError()
