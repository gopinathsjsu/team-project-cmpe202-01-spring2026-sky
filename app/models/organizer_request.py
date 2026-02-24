import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, Enum, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .Base import Base
import enum


class RequestStatus(enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class OrganizerRequest(Base):
    __tablename__ = "organizer_requests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True
    )

    status: Mapped[RequestStatus] = mapped_column(
        Enum(RequestStatus),
        default=RequestStatus.pending,
        index=True
    )

    message: Mapped[str] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    reviewed_by: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=True)

    __table_args__ = (
        UniqueConstraint("user_id", "status", name="uq_user_pending_request"),
    )

    user = relationship("User")