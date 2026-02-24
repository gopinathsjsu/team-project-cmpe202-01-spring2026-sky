from typing import Optional

from sqlalchemy.orm import Session
from app.models.organizer_request import OrganizerRequest, RequestStatus
from datetime import datetime
from uuid import UUID


def get_all_pending_requests(db: Session):
    return db.query(OrganizerRequest)\
        .filter(OrganizerRequest.status == RequestStatus.pending)\
        .all()


def get_request_by_id(db: Session, request_id: UUID):
    return db.query(OrganizerRequest)\
        .filter(OrganizerRequest.id == request_id)\
        .first()


def create_request(db: Session, user_id: str, message: Optional[str] = None):
    request = OrganizerRequest(
        user_id=user_id,
        message=message,
        status=RequestStatus.pending
    )
    db.add(request)
    db.commit()
    db.refresh(request)
    return request


def update_request_status(
    db: Session,
    request: OrganizerRequest,
    status: RequestStatus,
    reviewed_by: str
):
    request.status = status
    request.reviewed_by = reviewed_by
    request.reviewed_at = datetime.utcnow()

    db.commit()
    db.refresh(request)

    return request

def get_pending_request(db: Session, user_id: str):
    return db.query(OrganizerRequest)\
        .filter(
            OrganizerRequest.user_id == user_id,
            OrganizerRequest.status == RequestStatus.pending
        )\
        .first()
