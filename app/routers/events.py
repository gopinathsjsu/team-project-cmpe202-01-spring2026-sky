from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_role
from app.models.User import User, UserRole
from app.services.event_service import (
    create_event_service,
    delete_event_service,
    get_event_service,
    get_my_events_service,
    list_event_attendees_service,
    list_categories_service,
    list_events_service,
    update_event_service,
)

router = APIRouter(prefix="/events", tags=["events"])


class CreateEventRequest(BaseModel):
    title: str
    description: str | None = None
    category_id: UUID | None = None
    start_time: datetime
    end_time: datetime
    capacity: int = Field(gt=0)
    category: str | None = None
    location: str | None = None
    location_address: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class UpdateEventRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    category_id: UUID | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    capacity: int | None = Field(default=None, gt=0)
    category: str | None = None
    location: str | None = None
    location_address: str | None = None
    latitude: float | None = None
    longitude: float | None = None


@router.get("/")
def list_events(
    request: Request,
    category_id: UUID | None = None,
    category: str | None = Query(default=None, min_length=1),
    keyword: str | None = Query(default=None, min_length=1),
    db: Session = Depends(get_db),
):
    return list_events_service(
        request=request,
        db=db,
        category_id=category_id,
        category=category,
        keyword=keyword,
    )


@router.get("/categories")
def list_categories(
    db: Session = Depends(get_db),
):
    return list_categories_service(db=db)


@router.post("/create", dependencies=[Depends(require_role(UserRole.organizer))])
def create_event(
    payload: CreateEventRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return create_event_service(payload=payload, db=db, user=user)


@router.patch("/{event_id}")
def update_event(
    event_id: UUID,
    payload: UpdateEventRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.organizer)),
):
    return update_event_service(event_id=event_id, payload=payload, db=db, user=user)


@router.delete("/{event_id}")
def delete_event(
    event_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.organizer)),
):
    return delete_event_service(event_id=event_id, db=db, user=user)


@router.get("/mine")
def get_my_events(
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.organizer)),
):
    return get_my_events_service(db=db, user=user)


@router.get("/{event_id}/attendees")
def list_event_attendees(
    event_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.organizer)),
):
    return list_event_attendees_service(event_id=event_id, db=db, user=user)


@router.get("/{event_id}")
def get_event(
    event_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
):
    return get_event_service(event_id=event_id, request=request, db=db)
