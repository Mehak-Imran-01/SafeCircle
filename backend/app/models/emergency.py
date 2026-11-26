from datetime import datetime, timezone
import enum
from typing import TYPE_CHECKING
import uuid

from sqlalchemy import DateTime, Float, ForeignKey, Index, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship as orm_relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class EmergencyStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    CANCELLED = "CANCELLED"
    RESOLVED = "RESOLVED"


class Emergency(Base):
    __tablename__ = "emergencies"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    latitude: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    longitude: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    location_accuracy: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        default=None,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default=EmergencyStatus.ACTIVE.value,
        server_default=EmergencyStatus.ACTIVE.value,
        nullable=False,
        index=True,
    )
    emergency_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        default=None,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Composite index for efficient querying of active emergencies per user
    __table_args__ = (
        Index("ix_emergencies_user_id_status", "user_id", "status"),
    )

    # Relationship to owning user
    user: Mapped["User"] = orm_relationship(
        "User",
        back_populates="emergencies",
    )

    def __repr__(self) -> str:
        return f"<Emergency id={self.id} user_id={self.user_id} status={self.status} lat={self.latitude} lon={self.longitude}>"
