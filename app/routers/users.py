from ..database import get_db
from app.models.User import User, UserRole
from fastapi import Request, APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.dependencies import get_current_user, require_role
from app.services.organizer_request_service import (
    create_request,
    get_pending_request,
)


        
router = APIRouter(prefix="/users", tags=["users"])

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