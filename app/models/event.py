import uuid
import enum
from sqlalchemy import Column, String, Text, DateTime, Integer, Enum, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from .Base import Base, TimestampMixin

class EventStatus(str, enum.Enum):
    draft = "draft"
    pending_approval = "pending_approval"
    approved = "approved"
    rejected = "rejected"
    cancelled = "cancelled"

class Event(Base, TimestampMixin):
    __tablename__ = "events"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organizer_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    category_id = Column(UUID(as_uuid=True), ForeignKey("categories.id"))
    title = Column(String, nullable=False)
    description = Column(Text)

    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=False)

    location = Column(String)
    location_address = Column(Text)
    latitude = Column(Numeric(9,6))
    longitude = Column(Numeric(9,6))

    capacity = Column(Integer, nullable=False)
    status = Column(Enum(EventStatus), default=EventStatus.draft)

    organizer = relationship("User", back_populates="events")
    category = relationship("Category", back_populates="events")
    registrations = relationship("Registration", back_populates="event", cascade="all, delete")
