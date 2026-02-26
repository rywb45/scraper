from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(500), nullable=False)
    domain = Column(String(500), unique=True, nullable=False)
    website = Column(String(1000))
    industry = Column(String(200))
    sub_industry = Column(String(200))
    description = Column(Text)
    employee_count_range = Column(String(50))
    city = Column(String(200))
    state = Column(String(100))
    zip_code = Column(String(20))
    country = Column(String(100), default="US")
    phone = Column(String(50))
    source = Column(String(100))
    source_url = Column(String(1000))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    scrape_job_id = Column(Integer, ForeignKey("scrape_jobs.id"), nullable=True)

    contacts = relationship("Contact", back_populates="company", cascade="all, delete-orphan")
    scrape_job = relationship("ScrapeJob", back_populates="companies")


class Contact(Base):
    __tablename__ = "contacts"
    __table_args__ = (
        UniqueConstraint("company_id", "email", name="uq_contact_company_email"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    first_name = Column(String(200))
    last_name = Column(String(200))
    full_name = Column(String(400))
    title = Column(String(300))
    email = Column(String(500))
    email_confidence = Column(Float, default=0.0)
    phone = Column(String(50))
    linkedin_url = Column(String(1000))
    source = Column(String(100))
    source_url = Column(String(1000))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    company = relationship("Company", back_populates="contacts")


class ScrapeJob(Base):
    __tablename__ = "scrape_jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(500), nullable=False)
    status = Column(String(50), default="pending")  # pending, running, paused, completed, failed, cancelled
    job_type = Column(String(100))  # discovery, enrichment, full
    config = Column(Text, default="{}")  # JSON
    industries = Column(Text, default="[]")  # JSON array
    total_urls = Column(Integer, default=0)
    processed_urls = Column(Integer, default=0)
    companies_found = Column(Integer, default=0)
    contacts_found = Column(Integer, default=0)
    errors_count = Column(Integer, default=0)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    companies = relationship("Company", back_populates="scrape_job")
    logs = relationship("ScrapeLog", back_populates="scrape_job", cascade="all, delete-orphan")
    queue_items = relationship("ScrapeQueue", back_populates="scrape_job", cascade="all, delete-orphan")


class ScrapeLog(Base):
    __tablename__ = "scrape_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    scrape_job_id = Column(Integer, ForeignKey("scrape_jobs.id"), nullable=False)
    level = Column(String(20), default="info")  # debug, info, warning, error
    message = Column(Text, nullable=False)
    url = Column(String(1000), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    scrape_job = relationship("ScrapeJob", back_populates="logs")


Index("ix_scrape_logs_job_id", ScrapeLog.scrape_job_id)


class ScrapeQueue(Base):
    __tablename__ = "scrape_queue"

    id = Column(Integer, primary_key=True, autoincrement=True)
    scrape_job_id = Column(Integer, ForeignKey("scrape_jobs.id"), nullable=False)
    url = Column(String(1000), nullable=False)
    url_type = Column(String(50), default="company_page")  # search_result, company_page, contact_page
    status = Column(String(50), default="pending")  # pending, processing, completed, failed
    priority = Column(Integer, default=0)
    retry_count = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    processed_at = Column(DateTime, nullable=True)

    scrape_job = relationship("ScrapeJob", back_populates="queue_items")


Index("ix_scrape_queue_job_status", ScrapeQueue.scrape_job_id, ScrapeQueue.status)
