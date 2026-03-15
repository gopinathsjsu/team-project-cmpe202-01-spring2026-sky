from uuid import UUID

from pydantic import BaseModel, Field
from fastapi import Request, APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from app.dependencies import get_current_user, require_role
from app.models.User import User, UserRole
from app.services.registration_service import register_user_for_event
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
    }
