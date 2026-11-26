from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.trusted_contact import TrustedContact
from app.models.user import User
from app.schemas.trusted_contact import (
    TrustedContactCreate,
    TrustedContactResponse,
    TrustedContactUpdate,
)

router = APIRouter(tags=["Trusted Contacts"])


@router.post(
    "",
    response_model=TrustedContactResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a new trusted contact",
)
@router.post(
    "/",
    response_model=TrustedContactResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
async def create_trusted_contact(
    contact_in: TrustedContactCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TrustedContactResponse:
    new_contact = TrustedContact(
        user_id=current_user.id,
        name=contact_in.name.strip(),
        phone_number=contact_in.phone_number.strip(),
        relationship=contact_in.relationship.strip() if contact_in.relationship else None,
    )
    db.add(new_contact)
    await db.commit()
    await db.refresh(new_contact)
    return TrustedContactResponse.model_validate(new_contact)


@router.get(
    "",
    response_model=list[TrustedContactResponse],
    status_code=status.HTTP_200_OK,
    summary="List all trusted contacts for current user",
)
@router.get(
    "/",
    response_model=list[TrustedContactResponse],
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
async def list_trusted_contacts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[TrustedContactResponse]:
    stmt = (
        select(TrustedContact)
        .where(TrustedContact.user_id == current_user.id)
        .order_by(TrustedContact.created_at.desc())
    )
    result = await db.execute(stmt)
    contacts = result.scalars().all()
    return [TrustedContactResponse.model_validate(c) for c in contacts]


@router.get(
    "/{contact_id}",
    response_model=TrustedContactResponse,
    status_code=status.HTTP_200_OK,
    summary="Get a trusted contact by ID",
)
async def get_trusted_contact(
    contact_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TrustedContactResponse:
    stmt = select(TrustedContact).where(
        TrustedContact.id == contact_id,
        TrustedContact.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    contact = result.scalar_one_or_none()
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trusted contact not found",
        )
    return TrustedContactResponse.model_validate(contact)


@router.patch(
    "/{contact_id}",
    response_model=TrustedContactResponse,
    status_code=status.HTTP_200_OK,
    summary="Update a trusted contact",
)
async def update_trusted_contact(
    contact_id: UUID,
    contact_in: TrustedContactUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TrustedContactResponse:
    stmt = select(TrustedContact).where(
        TrustedContact.id == contact_id,
        TrustedContact.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    contact = result.scalar_one_or_none()
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trusted contact not found",
        )

    update_data = contact_in.model_dump(exclude_unset=True)
    if "name" in update_data and update_data["name"] is not None:
        contact.name = update_data["name"].strip()
    if "phone_number" in update_data and update_data["phone_number"] is not None:
        contact.phone_number = update_data["phone_number"].strip()
    if "relationship" in update_data:
        contact.relationship = (
            update_data["relationship"].strip()
            if update_data["relationship"] is not None
            else None
        )

    await db.commit()
    await db.refresh(contact)
    return TrustedContactResponse.model_validate(contact)


@router.delete(
    "/{contact_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a trusted contact",
)
async def delete_trusted_contact(
    contact_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    stmt = select(TrustedContact).where(
        TrustedContact.id == contact_id,
        TrustedContact.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    contact = result.scalar_one_or_none()
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trusted contact not found",
        )

    await db.delete(contact)
    await db.commit()
    return None
