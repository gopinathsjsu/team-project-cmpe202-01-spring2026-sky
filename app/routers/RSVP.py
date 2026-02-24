from fastapi import APIRouter, Depends
from app.dependencies import require_group, get_current_user, CurrentUser

router = APIRouter(prefix="/rsvp", tags=["RSVP"])


@router.post("/{event_id}", dependencies=[Depends(require_group("attendee"))])
def rsvp_event(event_id: str, user: CurrentUser = Depends(get_current_user)):
    return {"message": "RSVP created", "event_id": event_id}


@router.delete("/{event_id}", dependencies=[Depends(require_group("attendee"))])
def cancel_rsvp(event_id: str, user: CurrentUser = Depends(get_current_user)):
    return {"message": "RSVP cancelled"}


@router.get("/me")
def my_rsvps(user: CurrentUser = Depends(get_current_user)):
    return {"message": "List my RSVPs"}
