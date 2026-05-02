from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.database import get_db
from app.models.User import User, UserRole
from app.dependencies import get_current_user, require_role
from app.services.registration_service import (
    cancel_user_registration,
    list_user_registrations,
    register_user_for_event,
)
from app.services.calendar_service import build_event_google_calendar_url

router = APIRouter(prefix="/rsvp", tags=["RSVP"])


class RegisterEventRequest(BaseModel):
    event_id: UUID
    quantity: int = Field(default=1, gt=0)


@router.post("/", dependencies=[Depends(require_role(UserRole.attendee))])
def register_for_event(
    payload: RegisterEventRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    event, registration, remaining_capacity = register_user_for_event(
        db,
        user,
        payload.event_id,
        payload.quantity,
    )

    return {
        "message": "Event registration confirmed",
        "registration_id": str(registration.id),
        "event_id": str(event.id),
        "quantity": registration.quantity,
        "status": registration.status,
        "remaining_capacity": remaining_capacity,
        "google_calendar_url": build_event_google_calendar_url(event),
    }

@router.post("/{event_id}", dependencies=[Depends(require_role(UserRole.attendee))])
def rsvp_event(
    event_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    event, registration, remaining_capacity = register_user_for_event(db, user, event_id)

    return {
        "message": "RSVP created",
        "registration_id": str(registration.id),
        "event_id": str(event.id),
        "quantity": registration.quantity,
        "status": registration.status,
        "remaining_capacity": remaining_capacity,
        "google_calendar_url": build_event_google_calendar_url(event),
    }

@router.delete("/{event_id}", dependencies=[Depends(require_role(UserRole.attendee))])
def cancel_rsvp(
    event_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    event, registration = cancel_user_registration(db, user, event_id)
    return {
        "message": "RSVP cancelled",
        "registration_id": str(registration.id),
        "event_id": str(event.id),
        "status": registration.status,
    }


@router.get("/me")
def my_rsvps(
    user: User = Depends(require_role(UserRole.attendee)),
    db: Session = Depends(get_db),
):
    return list_user_registrations(db, user)
