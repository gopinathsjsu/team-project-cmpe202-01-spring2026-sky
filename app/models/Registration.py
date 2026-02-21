import uuid
import enum
from sqlalchemy import Column, Integer, DateTime, ForeignKey, Enum, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .Base import Base

class RegistrationStatus(str, enum.Enum):
    confirmed = "Confirmed"
    cancelled = "Cancelled"

class Registration(Base):
    __tablename__ = 'registrations'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    event_id = Column(UUID(as_uuid=True), ForeignKey('events.id'), nullable=False)

    status = Column(Enum(RegistrationStatus), default=RegistrationStatus.confirmed)
    quantity = Column(Integer, nullable=False, default=1)
    registered_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "event_id", name="unique_user_event"),
    )

    user = relationship("User", back_populates="registrations")
    event = relationship("Event", back_populates="registrations")
