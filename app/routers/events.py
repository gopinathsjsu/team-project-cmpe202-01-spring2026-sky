from fastapi import APIRouter, Depends
from app.dependencies import get_current_user, require_group, CurrentUser

router = APIRouter(prefix="/events", tags=["events"])

# Public
@router.get("/")
def list_events():
    pass

@router.get("/{event_id}")
def get_event(event_id: str):
    pass

# Organizer
@router.post("/", dependencies=[Depends(require_group("organizer"))])
def create_event(user: CurrentUser = Depends(get_current_user)):
    pass

@router.patch("/{event_id}")
def update_event(event_id: str, user: CurrentUser = Depends(get_current_user)):
    # Check ownership in real implementation
    pass

@router.delete("/{event_id}")
def delete_event(event_id: str, user: CurrentUser = Depends(get_current_user)):
    pass

@router.get("/mine")
def get_my_events(user: CurrentUser = Depends(require_group("organizer"))):
    pass
