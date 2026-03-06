from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import func
from fastapi import Request, APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from app.dependencies import get_current_user, require_role
from app.models.Event import Event, EventStatus
from app.models.Registration import Registration, RegistrationStatus
from app.models.User import User, UserRole
from app.services.organizer_request_service import (
    create_request,
    get_pending_request,
)


        
router = APIRouter(prefix="/users", tags=["users"])


class RegisterEventRequest(BaseModel):
    event_id: UUID
    quantity: int = Field(default=1, gt=0)

@router.get("/me")
def get_profile(request:Request, user: User = Depends(get_current_user)):
    event = request.scope.get("aws.event", {})
    print("EVENT:", event)

@router.patch("/me")
def update_profile(user: User = Depends(get_current_user)):
    pass

@router.get("/", dependencies=[Depends(require_role(UserRole.admin))])
def list_users():
    pass

@router.post("/me/request-organizer")
def request_organizer_upgrade(
    user: User = Depends(require_role(UserRole.attendee)),
    db: Session = Depends(get_db)
):
    existing = get_pending_request(db, user.id)
    if existing:
        raise HTTPException(400, "Request already pending")

    create_request(db, user.id)

    return {"message": "Organizer request submitted"}

@router.post("/registerEvent")
def register_for_event(
    payload: RegisterEventRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    event = db.query(Event).filter(Event.id == payload.event_id).first()
    if not event:
        raise HTTPException(404, "Event not found")

    if event.status != EventStatus.approved:
        raise HTTPException(400, "Event is not open for registration")

    existing_registration = db.query(Registration).filter(
        Registration.user_id == user.id,
        Registration.event_id == event.id,
    ).first()

    if existing_registration and existing_registration.status == RegistrationStatus.confirmed:
        raise HTTPException(400, "User is already registered for this event")

    confirmed_registrations = db.query(
        func.coalesce(func.sum(Registration.quantity), 0)
    ).filter(
        Registration.event_id == event.id,
        Registration.status == RegistrationStatus.confirmed,
    ).scalar()

    if confirmed_registrations + payload.quantity > event.capacity:
        raise HTTPException(400, "Event is full")

    if existing_registration:
        existing_registration.status = RegistrationStatus.confirmed
        existing_registration.quantity = payload.quantity
        existing_registration.registered_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(existing_registration)
        registration = existing_registration
    else:
        registration = Registration(
            user_id=user.id,
            event_id=event.id,
            quantity=payload.quantity,
            status=RegistrationStatus.confirmed,
            registered_at=datetime.now(timezone.utc),
        )
        db.add(registration)
        db.commit()
        db.refresh(registration)

    return {
        "message": "Event registration confirmed",
        "registration_id": str(registration.id),
        "event_id": str(event.id),
        "quantity": registration.quantity,
        "status": registration.status,
        "remaining_capacity": event.capacity - (confirmed_registrations + registration.quantity),
    }
