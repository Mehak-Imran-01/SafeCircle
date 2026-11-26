from datetime import datetime
import enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EmergencyStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    CANCELLED = "CANCELLED"
    RESOLVED = "RESOLVED"


class EmergencyCreate(BaseModel):
    latitude: float = Field(
        ...,
        ge=-90.0,
        le=90.0,
        description="GPS latitude between -90.0 and 90.0 degrees",
    )
    longitude: float = Field(
        ...,
        ge=-180.0,
        le=180.0,
        description="GPS longitude between -180.0 and 180.0 degrees",
    )
    location_accuracy: float | None = Field(
        default=None,
        gt=0.0,
        description="Location accuracy in meters (must be positive when provided)",
    )
    emergency_message: str | None = Field(
        default=None,
        max_length=1000,
        description="Optional SOS message or distress note",
    )


class EmergencyStatusUpdate(BaseModel):
    status: EmergencyStatus


class EmergencyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    latitude: float
    longitude: float
    location_accuracy: float | None
    status: EmergencyStatus
    emergency_message: str | None
    created_at: datetime
    updated_at: datetime
