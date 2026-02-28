import asyncio
import json
import logging
import re
from urllib.parse import urlparse

import httpx

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

# US state names and abbreviations for location matching
_STATE_NAMES = {
    "AL": "alabama", "AK": "alaska", "AZ": "arizona", "AR": "arkansas",
    "CA": "california", "CO": "colorado", "CT": "connecticut", "DE": "delaware",
    "FL": "florida", "GA": "georgia", "HI": "hawaii", "ID": "idaho",
    "IL": "illinois", "IN": "indiana", "IA": "iowa", "KS": "kansas",
    "KY": "kentucky", "LA": "louisiana", "ME": "maine", "MD": "maryland",
    "MA": "massachusetts", "MI": "michigan", "MN": "minnesota", "MS": "mississippi",
    "MO": "missouri", "MT": "montana", "NE": "nebraska", "NV": "nevada",
    "NH": "new hampshire", "NJ": "new jersey", "NM": "new mexico", "NY": "new york",
    "NC": "north carolina", "ND": "north dakota", "OH": "ohio", "OK": "oklahoma",
    "OR": "oregon", "PA": "pennsylvania", "RI": "rhode island", "SC": "south carolina",
    "SD": "south dakota", "TN": "tennessee", "TX": "texas", "UT": "utah",
    "VT": "vermont", "VA": "virginia", "WA": "washington", "WV": "west virginia",
    "WI": "wisconsin", "WY": "wyoming", "DC": "district of columbia",
}
_NAME_TO_ABBREV = {v: k for k, v in _STATE_NAMES.items()}


_CITY_ALIASES = {
    "nyc": ("new york", "NY"),
    "new york city": ("new york", "NY"),
    "la": ("los angeles", "CA"),
    "sf": ("san francisco", "CA"),
    "philly": ("philadelphia", "PA"),
    "dc": ("washington", "DC"),
    "chi": ("chicago", "IL"),
}


def _normalize_location(requested: str) -> tuple[set[str], set[str]]:
    """Parse a location filter into sets of matching state abbreviations and city names.
    Handles: 'New York', 'NY', 'New York, New Jersey', 'Dallas, TX',
    'Chicago IL', 'New York City', 'NYC'."""
    if not requested:
        return set(), set()

    import re
    states = set()
    cities = set()

    # Split on comma to handle multiple locations
    parts = [p.strip() for p in requested.split(",") if p.strip()]

    for part in parts:
        part_lower = part.lower().strip()
        part_upper = part.upper().strip()

        # Check city aliases first (NYC, LA, etc.)
        if part_lower in _CITY_ALIASES:
            city_name, st = _CITY_ALIASES[part_lower]
            cities.add(city_name)
            states.add(st)
            continue

        # Check if it's a state abbreviation
        if part_upper in _STATE_NAMES:
            states.add(part_upper)
            continue

        # Check if it's a full state name
        if part_lower in _NAME_TO_ABBREV:
            states.add(_NAME_TO_ABBREV[part_lower])
            continue

        # Check "City ST" format (e.g., "Chicago IL")
        m = re.match(r"(.+?)\s+([A-Za-z]{2})$", part.strip())
        if m:
            st = m.group(2).upper()
            if st in _STATE_NAMES:
                states.add(st)
                cities.add(m.group(1).strip().lower())
                continue

        # Otherwise treat as a city name
        cities.add(part_lower)

    return states, cities


def _location_matches(company_state: str, company_city: str, requested_location: str) -> bool:
    """Check if a company's location matches the requested location filter.
    - No location filter → keep
    - Company has a confirmed WRONG state → reject
    - Company has matching state or city → keep
    - Company has no location data → keep (search was geo-targeted)"""
    if not requested_location:
        return True

    target_states, target_cities = _normalize_location(requested_location)
    state = (company_state or "").strip().upper()
    city = (company_city or "").strip().lower()

    # Reject garbage city/state data
    if city and len(city) > 30:
        city = ""
    if state and len(state) != 2:
        state = ""

    # No location data — keep it, search was already geo-targeted
    if not state and not city:
        return True

    # Company has a state — it must match (reject confirmed wrong states)
    if state and target_states:
        return state in target_states

    # No target states parsed (city-only filter like "Dallas")
    if city and target_cities:
        for tc in target_cities:
            if tc == city or tc in city or city in tc:
                return True
        return False

    return True

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
            config = json.loads(job.config or "{}")
            sources = config.get("sources", [])  # empty = all sources
            location = config.get("location", "")

            if job_type in ("discovery", "full"):
                await _phase_discovery(db, job_id, industries, sources, location)

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


async def _phase_discovery(db, job_id: int, industries: list[str], sources: list[str] | None = None, location: str = ""):
    await job_service.add_log(db, job_id, "info", "Starting discovery phase")
    run_google = not sources or "google" in sources
    run_thomasnet = not sources or "thomasnet" in sources
    run_kompass = not sources or "kompass" in sources
    run_industrynet = not sources or "industrynet" in sources

    source_names = []
    if run_google:
        source_names.append("Google")
    if run_thomasnet:
        source_names.append("ThomasNet")
    if run_kompass:
        source_names.append("Kompass")
    if run_industrynet:
        source_names.append("IndustryNet")
    info = f"Sources: {', '.join(source_names)}"
    if location:
        info += f" | Location: {location}"
    await job_service.add_log(db, job_id, "info", info)

    scraper = GoogleSearchScraper()

    total_urls = 0
    processed = 0
    companies_found = 0
    errors = 0
    seen_domains = set()

    # Phase 1: Google Search (Serper API) — uses rich results to skip HTTP fetches
    if run_google:
        for industry in industries:
            await _check_job_status(db, job_id)
            queries = generate_queries(industry, location=location)
            await job_service.add_log(db, job_id, "info", f"Searching {industry} ({len(queries)} queries)")

            for query in queries:
                await _check_job_status(db, job_id)

                try:
                    results = await scraper.search(query, num_results=10, location=location)
                    if not results:
                        continue

                    # Deduplicate by domain
                    new_results = []
                    for r in results:
                        domain = r.get("domain", "")
                        if not domain:
                            domain = urlparse(r["url"]).netloc.lower().removeprefix("www.")
                        if domain not in seen_domains:
                            seen_domains.add(domain)
                            new_results.append(r)

                    total_urls += len(new_results)
                    await job_service.update_job_progress(db, job_id, total_urls=total_urls)

                    for r in new_results:
                        await _check_job_status(db, job_id)
                        try:
                            # Build ScrapedCompany directly from search result — no HTTP fetch
                            domain = r.get("domain", "")
                            if not domain:
                                domain = urlparse(r["url"]).netloc.lower().removeprefix("www.")
                            url = r["url"]
                            title = r.get("title", "")
                            snippet = r.get("snippet", "")
                            kg = r.get("knowledge_graph")

                            # Clean company name from title
                            name = _clean_company_name(title)
                            if not name or not domain:
                                processed += 1
                                await job_service.update_job_progress(db, job_id, processed_urls=processed)
                                continue

                            # Skip if domain already saved
                            if await company_service.get_company_by_domain(db, domain):
                                processed += 1
                                await job_service.update_job_progress(db, job_id, processed_urls=processed)
                                continue

                            company_data = ScrapedCompany(
                                name=name,
                                domain=domain,
                                website=f"{urlparse(url).scheme}://{urlparse(url).netloc}",
                                industry=industry,
                                description=snippet,
                                source="google_search",
                                source_url=url,
                            )

                            # Pre-populate from Knowledge Graph if available
                            if kg:
                                _apply_kg_to_company(kg, company_data)

                            processed += 1
                            saved = await _save_company(db, job_id, company_data, kg_data=kg)
                            if saved:
                                if location and not _location_matches(saved.state, saved.city, location):
                                    await db.delete(saved)
                                    await db.commit()
                                    continue
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
                            await job_service.add_log(db, job_id, "error", f"Scrape error: {e}", url=r.get("url", ""))
                            await job_service.update_job_progress(
                                db, job_id, processed_urls=processed, errors_count=errors
                            )

                except Exception as e:
                    errors += 1
                    await job_service.add_log(db, job_id, "warning", f"Search failed: {e}")

    # Phase 2: Directory sources — uses site: Google searches via Serper
    directory_scrapers = []
    if run_thomasnet:
        directory_scrapers.append(("ThomasNet", ThomasNetScraper()))
    if run_kompass:
        directory_scrapers.append(("Kompass", KompassScraper()))
    if run_industrynet:
        directory_scrapers.append(("IndustryNet", IndustryNetScraper()))

    for source_name, dir_scraper in directory_scrapers:
        await _check_job_status(db, job_id)
        await job_service.add_log(db, job_id, "info", f"Searching {source_name}...")
        dir_found = 0

        for industry in industries:
            await _check_job_status(db, job_id)
            try:
                search_query = f"{industry} {location}" if location else industry
                results = await dir_scraper.search(search_query, num_results=10)
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
                                if location and not _location_matches(saved.state, saved.city, location):
                                    await db.delete(saved)
                                    await db.commit()
                                    continue
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

    from sqlalchemy import select
    from app.db.models import Company
    result = await db.execute(select(Company).where(Company.scrape_job_id == job_id))
    companies = result.scalars().all()
    contacts_found = 0

    async def _fetch_page(url: str) -> str | None:
        """Fast page fetch — no rate limiting, short timeout, no retries."""
        try:
            async with httpx.AsyncClient(timeout=8, follow_redirects=True, headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,*/*;q=0.8",
            }) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    return resp.text
        except Exception:
            pass
        return None

    async def _enrich_company_contacts(company):
        """Fetch all contact pages for one company concurrently."""
        if not company.website:
            return []
        base = company.website.rstrip("/")
        pages = [f"{base}/contact", f"{base}/about", f"{base}/team"]
        results = await asyncio.gather(*[_fetch_page(url) for url in pages], return_exceptions=True)

        found = []
        for page_url, html in zip(pages, results):
            if isinstance(html, Exception) or not html:
                continue
            contacts = extract_contacts(html, source_url=page_url)
            found.extend(contacts)

            # Try to fill in missing revenue/employee data from about pages
            if not company.estimated_revenue or not company.employee_count:
                from app.scraper.extractors.revenue_extractor import (
                    estimate_revenue, extract_employee_count, extract_revenue,
                )
                if not company.estimated_revenue:
                    rev, rev_src = extract_revenue(html)
                    if rev:
                        company.estimated_revenue = rev
                        company.revenue_source = rev_src
                if not company.employee_count:
                    emp, emp_range = extract_employee_count(html)
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
        return found

    # Process companies in batches of 5 concurrently
    batch_size = 5
    for i in range(0, len(companies), batch_size):
        await _check_job_status(db, job_id)
        batch = companies[i:i + batch_size]
        batch_results = await asyncio.gather(
            *[_enrich_company_contacts(c) for c in batch],
            return_exceptions=True,
        )
        for company, result in zip(batch, batch_results):
            if isinstance(result, Exception):
                continue
            for c in result:
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
                    await db.rollback()
        await db.commit()
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


def _clean_company_name(title: str) -> str:
    """Clean a company name from a Google search result title.

    Strips common suffixes like ' | Company', ' - Home', ' - Official Site', etc.
    """
    if not title:
        return ""
    # Remove common suffixes
    for sep in [" | ", " - ", " — ", " – "]:
        if sep in title:
            parts = title.split(sep)
            # Take the first part unless it's very short
            if len(parts[0].strip()) >= 2:
                title = parts[0].strip()
            break
    # Remove trailing generic words
    title = re.sub(r"\s*(?:Home|Official Site|Homepage|Welcome)\s*$", "", title, flags=re.IGNORECASE).strip()
    return title[:200] if len(title) >= 2 else ""


def _apply_kg_to_company(kg: dict, company: ScrapedCompany):
    """Apply Knowledge Graph data to a ScrapedCompany, filling in missing fields."""
    from app.scraper.extractors.data_enricher import (
        _extract_from_kg, _count_to_range,
    )

    result = {
        "estimated_revenue": "",
        "revenue_source": "",
        "employee_count": None,
        "employee_count_range": "",
        "city": "",
        "state": "",
    }
    _extract_from_kg(kg, result)

    if not company.estimated_revenue and result["estimated_revenue"]:
        company.estimated_revenue = result["estimated_revenue"]
        company.revenue_source = result["revenue_source"]
    if not company.employee_count and result["employee_count"]:
        company.employee_count = result["employee_count"]
        company.employee_count_range = result["employee_count_range"]
    if not company.state and result["state"]:
        company.state = result["state"]
        company.city = result["city"]

    # Use KG description if better than snippet
    kg_desc = kg.get("description", "")
    if kg_desc and (not company.description or len(kg_desc) > len(company.description)):
        company.description = kg_desc


async def _save_company(db, job_id: int, data: ScrapedCompany, kg_data: dict | None = None):
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
        await _enrich_single_company(db, job_id, company, kg_data=kg_data)
    except Exception as e:
        await job_service.add_log(db, job_id, "warning", f"Enrich failed for {data.name}: {e}")

    return company


async def _enrich_single_company(db, job_id: int, company, kg_data: dict | None = None):
    """Enrich a single company with revenue, employee count, and location right after saving."""
    needs_revenue = not company.estimated_revenue
    needs_employees = not company.employee_count
    needs_state = not company.state

    if not (needs_revenue or needs_employees or needs_state):
        return

    needed = ", ".join(filter(None, [
        "revenue" if needs_revenue else "",
        "employees" if needs_employees else "",
        "location" if needs_state else "",
    ]))
    await job_service.add_log(db, job_id, "info", f"Enriching {company.name} (need: {needed})")

    data = await enrich_company(company.name, company.domain, kg_data=kg_data)

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
    else:
        await job_service.add_log(db, job_id, "warning", f"Enrichment returned no data for {company.name}")


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
