from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class TrustedContactBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Full name of trusted contact")
    phone_number: str = Field(..., min_length=3, max_length=50, description="Contact phone number")
    relationship: str | None = Field(
        default=None,
        max_length=100,
        description="Relationship to user (e.g., Parent, Sister, Friend)",
    )


class TrustedContactCreate(TrustedContactBase):
    pass


class TrustedContactUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    phone_number: str | None = Field(default=None, min_length=3, max_length=50)
    relationship: str | None = Field(default=None, max_length=100)


class TrustedContactResponse(TrustedContactBase):
    id: UUID
    user_id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
