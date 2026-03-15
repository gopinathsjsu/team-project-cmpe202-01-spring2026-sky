import uuid
from datetime import datetime
import enum
from typing import TYPE_CHECKING

from sqlalchemy import String, DateTime, ForeignKey, Enum, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .Base import Base

if TYPE_CHECKING:
    from .User import User


class RequestStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class OrganizerRequest(Base):
    __tablename__ = "organizer_requests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False,)
    status: Mapped[RequestStatus] = mapped_column(Enum(RequestStatus), default=RequestStatus.pending, index=True, nullable=False,)
    message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True,)

    __table_args__ = (UniqueConstraint("user_id", "status", name="uq_user_pending_request"),)

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
