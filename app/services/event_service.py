from typing import Any
from uuid import UUID

from fastapi import HTTPException, Request
from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.dependencies import get_current_user
from app.models.Category import Category
from app.models.Event import Event, EventStatus
from app.models.Registration import Registration, RegistrationStatus
from app.models.User import User
from app.services.registration_service import cancel_event_by_organizer


def _confirmed_registration_subquery(db: Session):
    return (
        db.query(
            Registration.event_id.label("event_id"),
            func.coalesce(func.sum(Registration.quantity), 0).label(
                "confirmed_registrations"
            ),
        )
        .filter(Registration.status == RegistrationStatus.confirmed)
        .group_by(Registration.event_id)
        .subquery()
    )


def _resolve_category_id(
    db: Session,
    *,
    category_id: UUID | None = None,
    category_name: str | None = None,
):
    if category_name is not None:
        if not category_name.strip():
            raise HTTPException(status_code=400, detail="category cannot be blank")

        category = db.query(Category).filter_by(name=category_name.strip()).first()
        if not category:
            category = Category(name=category_name.strip())
            db.add(category)
            db.flush()
        return category.id

    if category_id is None:
        return None

    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    return category.id


def _confirmed_registration_count(db: Session, event_id: UUID) -> int:
    return int(
        db.query(func.coalesce(func.sum(Registration.quantity), 0))
        .filter(
            Registration.event_id == event_id,
            Registration.status == RegistrationStatus.confirmed,
        )
        .scalar()
        or 0
    )


def _resolve_optional_user(request: Request, db: Session) -> User | None:
    user = None
    auth_header = request.headers.get("Authorization")
    try:
        user = get_current_user(request, db)
    except HTTPException as exc:
        if exc.status_code != 401:
            raise
        if auth_header:
            raise
    return user


def event_payload(
    event: Event,
    category_name: str | None,
    confirmed_registrations: int | None,
    user_registration: Registration | None = None,
):
    confirmed = int(confirmed_registrations or 0)
    remaining_capacity = max(event.capacity - confirmed, 0)
    return {
        "id": str(event.id),
        "title": event.title,
        "description": event.description,
        "category_id": str(event.category_id) if event.category_id else None,
        "category": category_name,
        "start_time": event.start_time,
        "end_time": event.end_time,
        "location": event.location,
        "location_address": event.location_address,
        "latitude": float(event.latitude) if event.latitude is not None else None,
        "longitude": float(event.longitude) if event.longitude is not None else None,
        "capacity": event.capacity,
        "registered_count": confirmed,
        "remaining_capacity": remaining_capacity,
        "user_registration_status": (
            user_registration.status if user_registration else None
        ),
        "user_registration_quantity": (
            user_registration.quantity if user_registration else None
        ),
        "status": event.status,
    }


def list_events_service(
    request: Request,
    db: Session,
):
    confirmed_subquery = _confirmed_registration_subquery(db)
    user = _resolve_optional_user(request, db)

    query = (
        db.query(
            Event,
            Category.name.label("category_name"),
            confirmed_subquery.c.confirmed_registrations,
            Registration,
        )
        .outerjoin(Category, Event.category_id == Category.id)
        .outerjoin(confirmed_subquery, confirmed_subquery.c.event_id == Event.id)
    )

    if user:
        query = query.outerjoin(
            Registration,
            and_(
                Registration.event_id == Event.id,
                Registration.user_id == user.id,
            ),
        )
    else:
        query = query.outerjoin(
            Registration,
            Registration.event_id == Event.id,
        ).filter(Registration.id.is_(None))

    rows = (
        query.filter(
            Event.status == EventStatus.approved,
        )
        .order_by(Event.start_time)
        .all()
    )

    return [
        event_payload(event, category_name, confirmed_registrations, user_registration)
        for event, category_name, confirmed_registrations, user_registration in rows
    ]


def create_event_service(
    payload: Any,
    db: Session,
    user: User,
):
    if payload.end_time <= payload.start_time:
        raise HTTPException(status_code=400, detail="end_time must be after start_time")

    resolved_category_id = _resolve_category_id(
        db,
        category_id=payload.category_id,
        category_name=payload.category,
    )
    event = Event(
        organizer_id=user.id,
        category_id=resolved_category_id,
        title=payload.title,
        description=payload.description,
        start_time=payload.start_time,
        end_time=payload.end_time,
        location=payload.location,
        location_address=payload.location_address,
        latitude=payload.latitude,
        longitude=payload.longitude,
        capacity=payload.capacity,
        status=EventStatus.pending_approval,
    )

    db.add(event)
    db.commit()
    db.refresh(event)

    return {
        "message": "Event created",
        "event_id": str(event.id),
        "status": event.status,
    }


def update_event_service(
    event_id: UUID,
    payload: Any,
    db: Session,
    user: User,
):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    if event.organizer_id != user.id:
        raise HTTPException(status_code=403, detail="You can only edit your own events")

    if event.status == EventStatus.cancelled:
        raise HTTPException(status_code=400, detail="Cancelled events cannot be edited")

    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No updates were provided")

    next_start_time = updates.get("start_time", event.start_time)
    next_end_time = updates.get("end_time", event.end_time)
    if next_end_time <= next_start_time:
        raise HTTPException(status_code=400, detail="end_time must be after start_time")

    confirmed_registrations = _confirmed_registration_count(db, event.id)
    if "capacity" in updates and updates["capacity"] < confirmed_registrations:
        raise HTTPException(
            status_code=400,
            detail="capacity cannot be less than confirmed registrations",
        )

    if "title" in updates:
        event.title = updates["title"]
    if "description" in updates:
        event.description = updates["description"]
    if "start_time" in updates:
        event.start_time = updates["start_time"]
    if "end_time" in updates:
        event.end_time = updates["end_time"]
    if "capacity" in updates:
        event.capacity = updates["capacity"]
    if "location" in updates:
        event.location = updates["location"]
    if "location_address" in updates:
        event.location_address = updates["location_address"]
    if "latitude" in updates:
        event.latitude = updates["latitude"]
    if "longitude" in updates:
        event.longitude = updates["longitude"]

    if "category" in payload.model_fields_set:
        event.category_id = _resolve_category_id(db, category_name=payload.category)
    elif "category_id" in payload.model_fields_set:
        event.category_id = _resolve_category_id(db, category_id=payload.category_id)

    previous_status = event.status
    event.status = EventStatus.pending_approval

    db.commit()
    db.refresh(event)

    return {
        "message": (
            "Event updated and resubmitted for approval"
            if previous_status != EventStatus.pending_approval
            else "Event updated"
        ),
        "event": event_payload(
            event,
            event.category.name if event.category else None,
            confirmed_registrations,
        ),
    }


def delete_event_service(
    event_id: UUID,
    db: Session,
    user: User,
):
    return cancel_event_by_organizer(db, user, event_id)


def get_my_events_service(
    db: Session,
    user: User,
):
    confirmed_subquery = _confirmed_registration_subquery(db)
    rows = (
        db.query(
            Event,
            Category.name.label("category_name"),
            confirmed_subquery.c.confirmed_registrations,
        )
        .outerjoin(Category, Event.category_id == Category.id)
        .outerjoin(confirmed_subquery, confirmed_subquery.c.event_id == Event.id)
        .filter(Event.organizer_id == user.id)
        .order_by(Event.start_time)
        .all()
    )

    return [
        event_payload(event, category_name, confirmed_registrations)
        for event, category_name, confirmed_registrations in rows
    ]


def get_event_service(
    event_id: UUID,
    request: Request,
    db: Session,
):
    row = (
        db.query(
            Event,
            Category.name.label("category_name"),
        )
        .outerjoin(Category, Event.category_id == Category.id)
        .filter(
            Event.id == event_id,
            Event.status == EventStatus.approved,
        )
        .first()
    )

    if not row:
        raise HTTPException(status_code=404, detail="Event not found")

    event, category_name = row
    confirmed_registrations = _confirmed_registration_count(db, event.id)
    user = _resolve_optional_user(request, db)

    user_registration = None
    if user:
        user_registration = (
            db.query(Registration)
            .filter(
                Registration.user_id == user.id,
                Registration.event_id == event.id,
            )
            .first()
        )

    return event_payload(event, category_name, confirmed_registrations, user_registration)
