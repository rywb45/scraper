from datetime import datetime

from pydantic import BaseModel


class ContactBase(BaseModel):
    company_id: int
    first_name: str | None = None
    last_name: str | None = None
    full_name: str | None = None
    title: str | None = None
    email: str | None = None
    email_confidence: float = 0.0
    phone: str | None = None
    linkedin_url: str | None = None
    source: str | None = None
    source_url: str | None = None


class ContactCreate(ContactBase):
    pass


class ContactUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    full_name: str | None = None
    title: str | None = None
    email: str | None = None
    email_confidence: float | None = None
    phone: str | None = None
    linkedin_url: str | None = None


class ContactOut(ContactBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
