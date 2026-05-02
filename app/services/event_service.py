from typing import Any
from uuid import UUID

from fastapi import HTTPException, Request
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from app.dependencies import get_current_user
from app.models.Category import Category
from app.models.Event import Event, EventStatus
from app.models.Registration import Registration, RegistrationStatus
from app.models.User import User
from app.services.calendar_service import build_event_google_calendar_url
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
    google_calendar_url = build_event_google_calendar_url(event)
    return {
        "id": str(event.id),
        "title": event.title,
        "description": event.description,
        "rejection_reason": getattr(event, "rejection_reason", None),
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
        "google_calendar_url": google_calendar_url,
        "user_registration_status": (
            user_registration.status if user_registration else None
        ),
        "user_registration_quantity": (
            user_registration.quantity if user_registration else None
        ),
        "status": event.status,
    }


def event_detail_payload(
    event: Event,
    category_name: str | None,
    confirmed_registrations: int | None,
    organizer: User,
    user_registration: Registration | None = None,
):
    payload = event_payload(
        event,
        category_name,
        confirmed_registrations,
        user_registration,
    )
    payload["schedule"] = {
        "start_time": event.start_time,
        "end_time": event.end_time,
    }
    payload["organizer"] = {
        "name": organizer.name,
        "email": organizer.email,
    }
    return payload


def list_events_service(
    request: Request,
    db: Session,
    category_id: UUID | None = None,
    category: str | None = None,
    keyword: str | None = None,
):
    if category_id is not None and category is not None:
        raise HTTPException(
            status_code=400,
            detail="Use either category_id or category, not both",
        )

    confirmed_subquery = _confirmed_registration_subquery(db)
    user = _resolve_optional_user(request, db)

    base_query = (
        db.query(
            Event,
            Category.name.label("category_name"),
            confirmed_subquery.c.confirmed_registrations,
        )
        .outerjoin(Category, Event.category_id == Category.id)
        .outerjoin(confirmed_subquery, confirmed_subquery.c.event_id == Event.id)
    )

    filters = [Event.status == EventStatus.approved]
    if category_id is not None:
        filters.append(Event.category_id == category_id)
    elif category is not None:
        category_name = category.strip()
        if not category_name:
            raise HTTPException(status_code=400, detail="category cannot be blank")
        filters.append(func.lower(Category.name) == category_name.lower())
    if keyword is not None:
        search_term = keyword.strip()
        if not search_term:
            raise HTTPException(status_code=400, detail="keyword cannot be blank")
        search_pattern = f"%{search_term.lower()}%"
        filters.append(
            or_(
                func.lower(Event.title).like(search_pattern),
                func.lower(func.coalesce(Event.description, "")).like(search_pattern),
                func.lower(func.coalesce(Category.name, "")).like(search_pattern),
                func.lower(func.coalesce(Event.location, "")).like(search_pattern),
                func.lower(func.coalesce(Event.location_address, "")).like(
                    search_pattern
                ),
            )
        )

    if user:
        rows = (
            base_query.add_columns(Registration)
            .outerjoin(
                Registration,
                and_(
                    Registration.event_id == Event.id,
                    Registration.user_id == user.id,
                ),
            )
            .filter(*filters)
            .order_by(Event.start_time)
            .all()
        )

        return [
            event_payload(
                event, category_name, confirmed_registrations, user_registration
            )
            for event, category_name, confirmed_registrations, user_registration in rows
        ]

    rows = base_query.filter(*filters).order_by(Event.start_time).all()

    return [
        event_payload(event, category_name, confirmed_registrations)
        for event, category_name, confirmed_registrations in rows
    ]


def list_categories_service(db: Session):
    rows = (
        db.query(
            Category,
            func.count(Event.id).label("event_count"),
        )
        .join(Event, Event.category_id == Category.id)
        .filter(Event.status == EventStatus.approved)
        .group_by(Category.id)
        .order_by(Category.name)
        .all()
    )

    return [
        {
            "id": str(category.id),
            "name": category.name,
            "description": category.description,
            "event_count": int(event_count),
        }
        for category, event_count in rows
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
    if "rejection_reason" in updates:
        event.rejection_reason = updates["rejection_reason"]
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
    event.rejection_reason = None

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


def list_event_attendees_service(
    event_id: UUID,
    db: Session,
    user: User,
):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    if event.organizer_id != user.id:
        raise HTTPException(
            status_code=403,
            detail="You can only view attendees for your own events",
        )

    rows = (
        db.query(Registration, User)
        .join(User, User.id == Registration.user_id)
        .filter(
            Registration.event_id == event.id,
            Registration.status == RegistrationStatus.confirmed,
        )
        .order_by(Registration.registered_at, User.email)
        .all()
    )

    return [
        {
            "registration_id": str(registration.id),
            "user_id": str(attendee.id),
            "email": attendee.email,
            "quantity": registration.quantity,
            "status": registration.status,
            "registered_at": registration.registered_at,
        }
        for registration, attendee in rows
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
            User,
        )
        .join(User, Event.organizer_id == User.id)
        .outerjoin(Category, Event.category_id == Category.id)
        .filter(
            Event.id == event_id,
            Event.status == EventStatus.approved,
        )
        .first()
    )

    if not row:
        raise HTTPException(status_code=404, detail="Event not found")

    event, category_name, organizer = row
    confirmed_registrations = _confirmed_registration_count(db, event.id)
    current_user = _resolve_optional_user(request, db)

    user_registration = None
    if current_user:
        user_registration = (
            db.query(Registration)
            .filter(
                Registration.user_id == current_user.id,
                Registration.event_id == event.id,
            )
            .first()
        )

    return event_detail_payload(
        event,
        category_name,
        confirmed_registrations,
        organizer,
        user_registration,
    )
