from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from app.dependencies import get_current_user, require_role
from app.models.User import User, UserRole
from app.services.organizer_request_service import (
    create_request,
    get_pending_request,
)

router = APIRouter(prefix="/users", tags=["users"])


def _serialize_user(user: User) -> dict:
    return {
        "id": str(user.id),
        "cognito_sub": user.cognito_sub,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "is_active": user.is_active,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
    }
@router.get("/me")
def get_profile(user: User = Depends(get_current_user)):
    return _serialize_user(user)


@router.patch("/me")
def update_profile(_user: User = Depends(get_current_user)):
    raise HTTPException(status_code=501, detail="Profile updates are not implemented")


@router.get("/", dependencies=[Depends(require_role(UserRole.admin))])
def list_users():
    raise HTTPException(status_code=501, detail="Listing users is not implemented")


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
