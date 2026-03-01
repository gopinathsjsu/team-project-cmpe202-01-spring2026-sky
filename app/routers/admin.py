from uuid import UUID

from ..database import get_db
from fastapi import APIRouter, Depends, HTTPException
from app.dependencies import require_role
import boto3
import os
from app.services.organizer_request_service import (
    get_all_pending_requests,
    get_request_by_id,
    update_request_status
)
from app.models.organizer_request import RequestStatus
from app.models.Event import Event, EventStatus
from app.models.User import User, UserRole
from sqlalchemy.orm import Session



AWS_REGION = os.getenv("AWS_REGION")
USER_POOL_ID = os.getenv("COGNITO_USER_POOL_ID") or os.getenv("USER_POOL_ID")

cognito = boto3.client("cognito-idp", region_name=AWS_REGION)
router = APIRouter(prefix="/admin", tags=["admin"])


def ensure_cognito_config():
    if not USER_POOL_ID:
        raise HTTPException(status_code=500, detail="COGNITO_USER_POOL_ID is not configured")


@router.get("/events/pending", dependencies=[Depends(require_role(UserRole.admin))])
def pending_events(db: Session = Depends(get_db)):
    return db.query(Event).filter(Event.status == EventStatus.pending_approval).all()


@router.patch("/events/{event_id}/approve", dependencies=[Depends(require_role(UserRole.admin))])
def approve_event(event_id: UUID, db: Session = Depends(get_db)):
    event = get_pending_event_or_raise_exception(db, event_id)
    event.status = EventStatus.approved
    db.commit()
    db.refresh(event)
    return {"message": "Event approved", "event_id": str(event.id), "status": event.status}

@router.patch("/events/{event_id}/reject", dependencies=[Depends(require_role(UserRole.admin))])
def reject_event(event_id: UUID, db: Session = Depends(get_db)):
    event = get_pending_event_or_raise_exception(db, event_id)
    event.status = EventStatus.rejected
    db.commit()
    db.refresh(event)
    return {"message": "Event rejected", "event_id": str(event.id), "status": event.status}

@router.patch("/users/{user_id}/promote")
def promote_user(
    user_id: str,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_role(UserRole.admin))
):
    ensure_cognito_config()
    
    user = db.query(User).filter_by(id=user_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    
    if admin_user.id == user.id:
        raise HTTPException(403, "Cannot modify your own admin role")

    cognito.admin_add_user_to_group(
        UserPoolId=USER_POOL_ID,
        Username=user.cognito_sub,
        GroupName="admin"
    )

    cognito.admin_remove_user_from_group(
        UserPoolId=USER_POOL_ID,
        Username=user.cognito_sub,
        GroupName="admin"
    )

    user.role = UserRole.admin
    db.commit()
    db.refresh(user)

    return {"message": "User promoted to admin"}

@router.patch("/users/{user_id}/revoke")
def revoke_admin_role(
    user_id: UUID,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_role(UserRole.admin))
):
    ensure_cognito_config()

    user = db.query(User).filter_by(id=user_id).first()
    if not user:
        raise HTTPException(404, "User not found")

    if admin_user.id == user.id:
        raise HTTPException(403, "Cannot modify your own admin role")

    if user.role != UserRole.admin:
        raise HTTPException(400, "User is not an admin")

    cognito.admin_remove_user_from_group(
        UserPoolId=USER_POOL_ID,
        Username=user.cognito_sub,
        GroupName="admin"
    )

    cognito.admin_add_user_to_group(
        UserPoolId=USER_POOL_ID,
        Username=user.cognito_sub,
        GroupName="attendee"
    )

    user.role = UserRole.attendee
    db.commit()
    db.refresh(user)

    return {"message": "User admin role revoked"}

@router.get("/organizer-requests")
def list_requests(
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_role(UserRole.admin))
):
    return get_all_pending_requests(db)


@router.patch("/organizer-requests/{request_id}/approve")
def approve_request(
    request_id: UUID,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_role(UserRole.admin))
):
    ensure_cognito_config()
    request = get_request_by_id(db, request_id)

    if not request:
        raise HTTPException(404, "Invalid request")
    
    if request.status != RequestStatus.pending:
        raise HTTPException(400, "Request already processed")
    
    user = db.query(User).filter_by(id=request.user_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    
    cognito_sub = user.cognito_sub


    # Remove attendee
    cognito.admin_remove_user_from_group(
        UserPoolId=USER_POOL_ID,
        Username=cognito_sub,
        GroupName="attendee"
    )

    # Add organizer
    cognito.admin_add_user_to_group(
        UserPoolId=USER_POOL_ID,
        Username=cognito_sub,
        GroupName="organizer"
    )

    user.role = UserRole.organizer

    update_request_status(
        db=db,
        request=request,
        status=RequestStatus.approved,
        reviewed_by=admin_user.id
    )

    return {"message": "Approved", "force_refresh": True}


@router.patch("/organizer-requests/{request_id}/reject")
def reject_request(
    request_id: UUID,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_role(UserRole.admin))
):
    request = get_request_by_id(db, request_id)

    if not request:
        raise HTTPException(404, "Invalid request")
    
    if request.status == RequestStatus.approved:
        raise HTTPException(400, "Request already approved")

    if request.status != RequestStatus.pending:
        raise HTTPException(400, "Request already processed")

    update_request_status(
        db=db,
        request=request,
        status=RequestStatus.rejected,
        reviewed_by=admin_user.id
    )

    return {"message": "Rejected"}


def get_pending_event_or_raise_exception(db: Session, event_id: UUID) -> Event:
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(404, "Event not found")
    if event.status != EventStatus.pending_approval:
        raise HTTPException(400, "Event is not pending approval")
    return event
