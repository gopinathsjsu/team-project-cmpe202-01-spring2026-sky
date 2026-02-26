from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.Category import Category
from app.models.Event import Event, EventStatus
from app.models.User import User, UserRole
from app.dependencies import get_current_user, require_role

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


# Public
@router.get("/")
def list_events():
    pass

@router.get("/{event_id}")
def get_event(event_id: str):
    pass

# Organizer
@router.post("/{organizer_id}", dependencies=[Depends(require_role(UserRole.organizer))])
def create_event(
    payload: CreateEventRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    if payload.end_time <= payload.start_time:
        raise HTTPException(status_code=400, detail="end_time must be after start_time")

    if payload.category:
        category = db.query(Category).filter_by(name=payload.category).first()
        if not category:
            category = Category(name=payload.category)
            db.add(category)
            db.flush()  # Ensure category is flushed to get an ID   
        payload.category_id = category.id
    event = Event(
        organizer_id=user.id,
        category_id=payload.category_id,
        title=payload.title,
        description=payload.description,
        start_time=payload.start_time,
        end_time=payload.end_time,
        location=payload.location,
        location_address=payload.location_address,
        latitude=payload.latitude,
        longitude=payload.longitude,
        capacity=payload.capacity,
        status=EventStatus.pending_approval
    )

    db.add(event)
    db.commit()
    db.refresh(event)

    return {
        "message": "Event created",
        "event_id": str(event.id),
        "status": event.status
    }

@router.patch("/{event_id}")
def update_event(event_id: str, user: User = Depends(get_current_user)):
    # Check ownership in real implementation
    pass

@router.delete("/{event_id}")
def delete_event(event_id: str, user: User = Depends(get_current_user)):
    pass

@router.get("/mine")
def get_my_events(user: User = Depends(require_role(UserRole.organizer))):
    pass
