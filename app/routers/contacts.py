from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.schemas.contact import ContactCreate, ContactOut, ContactUpdate
from app.services import contact_service

router = APIRouter()


@router.get("", response_model=list[ContactOut])
async def list_contacts(
    company_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
):
    return await contact_service.get_contacts_for_company(db, company_id)


@router.get("/{contact_id}", response_model=ContactOut)
async def get_contact(contact_id: int, db: AsyncSession = Depends(get_db)):
    contact = await contact_service.get_contact(db, contact_id)
    if not contact:
        raise HTTPException(404, "Contact not found")
    return contact


@router.post("", response_model=ContactOut, status_code=201)
async def create_contact(data: ContactCreate, db: AsyncSession = Depends(get_db)):
    return await contact_service.create_contact(db, data)


@router.patch("/{contact_id}", response_model=ContactOut)
async def update_contact(contact_id: int, data: ContactUpdate, db: AsyncSession = Depends(get_db)):
    contact = await contact_service.update_contact(db, contact_id, data)
    if not contact:
        raise HTTPException(404, "Contact not found")
    return contact


@router.delete("/{contact_id}", status_code=204)
async def delete_contact(contact_id: int, db: AsyncSession = Depends(get_db)):
    if not await contact_service.delete_contact(db, contact_id):
        raise HTTPException(404, "Contact not found")
