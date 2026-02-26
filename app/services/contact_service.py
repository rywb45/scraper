from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Contact
from app.schemas.contact import ContactCreate, ContactUpdate


async def get_contacts_for_company(db: AsyncSession, company_id: int):
    result = await db.execute(
        select(Contact).where(Contact.company_id == company_id).order_by(Contact.email_confidence.desc())
    )
    return result.scalars().all()


async def get_contact(db: AsyncSession, contact_id: int):
    result = await db.execute(select(Contact).where(Contact.id == contact_id))
    return result.scalar_one_or_none()


async def create_contact(db: AsyncSession, data: ContactCreate) -> Contact:
    contact = Contact(**data.model_dump())
    db.add(contact)
    await db.commit()
    await db.refresh(contact)
    return contact


async def update_contact(db: AsyncSession, contact_id: int, data: ContactUpdate) -> Contact | None:
    contact = await get_contact(db, contact_id)
    if not contact:
        return None
    for key, val in data.model_dump(exclude_unset=True).items():
        setattr(contact, key, val)
    await db.commit()
    await db.refresh(contact)
    return contact


async def delete_contact(db: AsyncSession, contact_id: int) -> bool:
    contact = await get_contact(db, contact_id)
    if not contact:
        return False
    await db.delete(contact)
    await db.commit()
    return True
