from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.emergency import Emergency, EmergencyStatus
from app.models.user import User
from app.schemas.emergency import (
    EmergencyCreate,
    EmergencyResponse,
)

router = APIRouter(tags=["Emergencies / SOS"])


@router.post(
    "",
    response_model=EmergencyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new SOS emergency",
)
@router.post(
    "/",
    response_model=EmergencyResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
async def create_emergency(
    emergency_in: EmergencyCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EmergencyResponse:
    """Create a new SOS emergency.

    Prevents duplicate active emergencies for the same user.
    """
    # Check if user already has an active emergency
    stmt = select(Emergency).where(
        Emergency.user_id == current_user.id,
        Emergency.status == EmergencyStatus.ACTIVE.value,
    )
    result = await db.execute(stmt)
    existing_active = result.scalar_one_or_none()
    if existing_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An active emergency already exists for this user. Please resolve or cancel it before initiating a new one.",
        )

    new_emergency = Emergency(
        user_id=current_user.id,
        latitude=emergency_in.latitude,
        longitude=emergency_in.longitude,
        location_accuracy=emergency_in.location_accuracy,
        status=EmergencyStatus.ACTIVE.value,
        emergency_message=emergency_in.emergency_message.strip() if emergency_in.emergency_message else None,
    )
    db.add(new_emergency)
    await db.commit()
    await db.refresh(new_emergency)
    return EmergencyResponse.model_validate(new_emergency)


@router.get(
    "/active",
    response_model=EmergencyResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve current active emergency",
)
async def get_active_emergency(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EmergencyResponse:
    """Retrieve the authenticated user's active emergency, if one exists."""
    stmt = select(Emergency).where(
        Emergency.user_id == current_user.id,
        Emergency.status == EmergencyStatus.ACTIVE.value,
    )
    result = await db.execute(stmt)
    active_emergency = result.scalar_one_or_none()
    if not active_emergency:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active emergency found for this user.",
        )
    return EmergencyResponse.model_validate(active_emergency)


@router.get(
    "",
    response_model=list[EmergencyResponse],
    status_code=status.HTTP_200_OK,
    summary="Retrieve emergency history",
)
@router.get(
    "/",
    response_model=list[EmergencyResponse],
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
async def get_emergency_history(
    limit: int = Query(20, ge=1, le=100, description="Maximum number of emergencies to return"),
    offset: int = Query(0, ge=0, description="Number of emergencies to skip"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[EmergencyResponse]:
    """Retrieve the authenticated user's emergency history with pagination."""
    stmt = (
        select(Emergency)
        .where(Emergency.user_id == current_user.id)
        .order_by(Emergency.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    emergencies = result.scalars().all()
    return [EmergencyResponse.model_validate(e) for e in emergencies]


@router.patch(
    "/{emergency_id}/cancel",
    response_model=EmergencyResponse,
    status_code=status.HTTP_200_OK,
    summary="Cancel an active emergency",
)
async def cancel_emergency(
    emergency_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EmergencyResponse:
    """Cancel an active emergency belonging to the current user.

    Returns HTTP 404 if the emergency is not found or does not belong to the user.
    Returns HTTP 400 if the emergency is already cancelled or resolved.
    """
    stmt = select(Emergency).where(
        Emergency.id == emergency_id,
        Emergency.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    emergency = result.scalar_one_or_none()

    if not emergency:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Emergency not found.",
        )

    if emergency.status != EmergencyStatus.ACTIVE.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel emergency with status '{emergency.status}'. Only ACTIVE emergencies can be cancelled.",
        )

    emergency.status = EmergencyStatus.CANCELLED.value
    await db.commit()
    await db.refresh(emergency)
    return EmergencyResponse.model_validate(emergency)
