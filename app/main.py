from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.db.database import init_db
from app.routers import companies, contacts, export, jobs, stats

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="Lead Scraper", version="1.0.0", lifespan=lifespan)

# Static files & templates
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(FRONTEND_DIR / "templates"))

# API routers
app.include_router(companies.router, prefix="/api/companies", tags=["companies"])
app.include_router(contacts.router, prefix="/api/contacts", tags=["contacts"])
app.include_router(stats.router, prefix="/api/stats", tags=["stats"])
app.include_router(export.router, prefix="/api/export", tags=["export"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["jobs"])


# Page routes
@app.get("/")
async def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/companies")
async def companies_page(request: Request):
    return templates.TemplateResponse("companies.html", {"request": request})


@app.get("/companies/{company_id}")
async def company_detail_page(request: Request, company_id: int):
    return templates.TemplateResponse("company_detail.html", {"request": request, "company_id": company_id})


@app.get("/jobs")
async def jobs_page(request: Request):
    return templates.TemplateResponse("jobs.html", {"request": request})


@app.get("/jobs/new")
async def new_job_page(request: Request):
    return templates.TemplateResponse("job_new.html", {"request": request})


@app.get("/jobs/{job_id}")
async def job_detail_page(request: Request, job_id: int):
    return templates.TemplateResponse("job_detail.html", {"request": request, "job_id": job_id})
