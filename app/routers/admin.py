from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from app.dependencies import require_group, CurrentUser
import boto3
import os
from pydantic import BaseModel
from app.services.organizer_request_service import (
    get_all_pending_requests,
    get_request_by_id,
    update_request_status
)
from app.models.organizer_request import RequestStatus
from sqlalchemy.orm import Session
from app.database import SessionLocal


class PromoteRequest(BaseModel):
    role: str

AWS_REGION = os.getenv("AWS_REGION")
USER_POOL_ID = os.getenv("USER_POOL_ID")

cognito = boto3.client("cognito-idp", region_name=AWS_REGION)
router = APIRouter(prefix="/admin", tags=["admin"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/events/pending", dependencies=[Depends(require_group("admin"))])
def pending_events():
    pass

@router.patch("/events/{event_id}/approve", dependencies=[Depends(require_group("admin"))])
def approve_event(event_id: str):
    pass

@router.patch("/events/{event_id}/reject", dependencies=[Depends(require_group("admin"))])
def reject_event(event_id: str):
    pass

@router.patch("/users/{user_id}/promote")
def promote_user(
    user_id: str,
    payload: PromoteRequest,
    admin_user: CurrentUser = Depends(require_group("admin"))
):

    if payload.role != "admin":
        raise HTTPException(400, "Only admin promotion allowed here")

    if admin_user.sub == user_id:
        raise HTTPException(403, "Cannot modify your own admin role")

    cognito.admin_add_user_to_group(
        UserPoolId=USER_POOL_ID,
        Username=user_id,
        GroupName="admin"
    )

    return {"message": "User promoted to admin"}

@router.get("/organizer-requests")
def list_requests(
    db: Session = Depends(get_db),
    admin=Depends(require_group("admin"))
):
    return get_all_pending_requests(db)


@router.patch("/organizer-requests/{request_id}/approve")
def approve_request(
    request_id: UUID,
    db: Session = Depends(get_db),
    admin_user: CurrentUser = Depends(require_group("admin"))
):
    request = get_request_by_id(db, request_id)

    if not request or request.status != RequestStatus.pending:
        raise HTTPException(404, "Invalid request")

    user_id = request.user_id

    # Remove attendee
    cognito.admin_remove_user_from_group(
        UserPoolId=USER_POOL_ID,
        Username=user_id,
        GroupName="attendee"
    )

    # Add organizer
    cognito.admin_add_user_to_group(
        UserPoolId=USER_POOL_ID,
        Username=user_id,
        GroupName="organizer"
    )

    update_request_status(
        db=db,
        request=request,
        status=RequestStatus.approved,
        reviewed_by=admin_user.sub
    )

    return {"message": "Approved", "force_refresh": True}


@router.patch("/organizer-requests/{request_id}/reject")
def reject_request(
    request_id: UUID,
    db: Session = Depends(get_db),
    admin_user: CurrentUser = Depends(require_group("admin"))
):
    request = get_request_by_id(db, request_id)

    if not request or request.status != RequestStatus.pending:
        raise HTTPException(404, "Invalid request")

    update_request_status(
        db=db,
        request=request,
        status=RequestStatus.rejected,
        reviewed_by=admin_user.sub
    )

    return {"message": "Rejected"}