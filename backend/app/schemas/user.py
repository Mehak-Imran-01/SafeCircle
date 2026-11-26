from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserBase(BaseModel):
    email: EmailStr = Field(..., description="User email address")
    full_name: str = Field(..., min_length=1, max_length=255, description="User full name")
    phone_number: str = Field(..., min_length=3, max_length=50, description="Contact phone number")


class UserRegisterRequest(UserBase):
    password: str = Field(..., min_length=8, max_length=128, description="User password (min 8 characters)")


class UserLoginRequest(BaseModel):
    email: EmailStr = Field(..., description="User registered email")
    password: str = Field(..., min_length=1, description="User password")


class UserResponse(UserBase):
    id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
