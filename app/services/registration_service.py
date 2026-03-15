from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.Event import Event, EventStatus
from app.models.Registration import Registration, RegistrationStatus
from app.models.User import User, UserRole


def register_user_for_event(db, user, event_id, quantity = 1,):
    event = db.query(Event).filter(Event.id == event_id).first()
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

    if confirmed_registrations + quantity > event.capacity:
        raise HTTPException(400, "Event is full")

    if existing_registration:
        existing_registration.status = RegistrationStatus.confirmed
        existing_registration.quantity = quantity
        existing_registration.registered_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(existing_registration)
        registration = existing_registration
    else:
        registration = Registration(
            user_id=user.id,
            event_id=event.id,
            quantity=quantity,
            status=RegistrationStatus.confirmed,
            registered_at=datetime.now(timezone.utc),
        )
        db.add(registration)
        db.commit()
        db.refresh(registration)

    remaining_capacity = event.capacity - (confirmed_registrations + registration.quantity)
    return event, registration, remaining_capacity


def cancel_user_registration(
    db: Session,
    user: User,
    event_id: UUID,
):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(404, "Event not found")

    

    if event.status == EventStatus.cancelled:
        raise HTTPException(400, "Event is already cancelled")

    if user.role == UserRole.attendee:
        registration = db.query(Registration).filter(
            Registration.user_id == user.id,
            Registration.event_id == event.id,
        ).first()
        if not registration:
            raise HTTPException(404, "Registration not found")

        if registration.status == RegistrationStatus.cancelled:
            raise HTTPException(400, "Registration is already cancelled")

        registration.status = RegistrationStatus.cancelled
        db.commit()
        db.refresh(registration)
        return event, registration
        

def cancel_event_by_organizer(db, user, event_id):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(404, "Event not found")

    if event.organizer_id != user.id:
        raise HTTPException(403, "You can only cancel your own events")
    
    if event.status == EventStatus.cancelled:
        raise HTTPException(400, "Event has already been cancelled")
    
    registrations = db.query(Registration).filter(
        Registration.event_id == event.id,
        Registration.status == RegistrationStatus.confirmed).all()

    for registration in registrations:
        registration.status = RegistrationStatus.cancelled

    event.status = EventStatus.cancelled
    db.commit()
    db.refresh(event)

    return {
        "message": "Event cancelled",
        "event_id": str(event.id),
        "status": event.status,
        "cancelled_registrations": len(registrations),
    }