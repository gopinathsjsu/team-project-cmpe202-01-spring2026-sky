import uuid
import enum
from typing import TYPE_CHECKING
from sqlalchemy import String, Boolean, Enum
from uuid import UUID as PyUUID
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship, Mapped, mapped_column
from .Base import Base, TimestampMixin

if TYPE_CHECKING:
    from .Event import Event
    from .Registration import Registration


class UserRole(str, enum.Enum):
    attendee = "attendee"
    organizer = "organizer"
    admin = "admin"


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[PyUUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cognito_sub: Mapped[str] = mapped_column(String, unique=True)
    email: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    events: Mapped[list["Event"]] = relationship("Event", back_populates="organizer")
    registrations: Mapped[list["Registration"]] = relationship("Registration", back_populates="user")
