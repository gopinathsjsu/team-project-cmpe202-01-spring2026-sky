from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import SessionLocal
from app.dependencies import get_current_user, require_group, CurrentUser
from app.services.organizer_request_service import (
    create_request,
    get_pending_request,
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        
router = APIRouter(prefix="/users", tags=["users"])

@router.get("/me")
def get_profile(user: CurrentUser = Depends(get_current_user)):
    pass

@router.patch("/me")
def update_profile(user: CurrentUser = Depends(get_current_user)):
    pass

@router.get("/", dependencies=[Depends(require_group("admin"))])
def list_users():
    pass

@router.post("/me/request-organizer")
def request_organizer_upgrade(
    user: CurrentUser = Depends(require_group("attendee")),
    db: Session = Depends(get_db)
):
    existing = get_pending_request(db, user.sub)
    if existing:
        raise HTTPException(400, "Request already pending")

    create_request(db, user.sub)

    return {"message": "Organizer request submitted"}