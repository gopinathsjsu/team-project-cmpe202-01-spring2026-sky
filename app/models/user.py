import uuid
import enum
from sqlalchemy import Column, String, Boolean, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from .Base import Base, TimestampMixin

class UserRole(str, enum.Enum):
    attendee = "attendee"
    organizer = "organizer"
    admin = "admin"

class User(Base, TimestampMixin):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    full_name = Column(String, nullable=False)
    password_hash = Column(String, nullable=False)
    email = Column(String, nullable=False)
    role = Column(Enum(UserRole), nullable=False)  # type: ignore[var-annotated]
    is_active = Column(Boolean, nullable=False, default=True)

    events = relationship("Event", back_populates="organizer")
    registrations = relationship("Registration", back_populates="user")
