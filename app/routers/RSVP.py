from app.models.User import User, UserRole
from fastapi import APIRouter, Depends
from app.dependencies import get_current_user, require_role

router = APIRouter(prefix="/rsvp", tags=["RSVP"])


@router.post("/{event_id}", dependencies=[Depends(require_role(UserRole.attendee))])
def rsvp_event(event_id: str, user: User = Depends(get_current_user)):
    return {"message": "RSVP created", "event_id": event_id}


@router.delete("/{event_id}", dependencies=[Depends(require_role(UserRole.attendee))])
def cancel_rsvp(event_id: str, user: User = Depends(get_current_user)):
    return {"message": "RSVP cancelled"}


@router.get("/me")
def my_rsvps(user: User = Depends(get_current_user)):
    return {"message": "List my RSVPs"}
