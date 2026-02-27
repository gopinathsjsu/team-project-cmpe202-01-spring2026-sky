import os
import boto3

from fastapi import Request, HTTPException, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.User import User, UserRole



cognito_client = boto3.client("cognito-idp")
USER_POOL_ID = os.environ["COGNITO_USER_POOL_ID"]


def fetch_cognito_user(sub: str):
    response = cognito_client.admin_get_user(
        UserPoolId=USER_POOL_ID,
        Username=sub
    )

    attributes = {
        attr["Name"]: attr["Value"]
        for attr in response["UserAttributes"]
    }

    return attributes


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    claims = (
        request.scope.get("aws.event", {})
        .get("requestContext", {})
        .get("authorizer", {})
        .get("jwt", {})
        .get("claims", {})
    )

    groups = claims.get("cognito:groups", [])
    role = UserRole.admin if "admin" in groups else UserRole.attendee

    if not claims:
        raise HTTPException(status_code=401, detail="Unauthorized")

    print(claims)
    sub = claims.get("sub")

    if not sub:
        raise HTTPException(status_code=401, detail="Unauthorized")
    user = db.query(User).filter_by(cognito_sub=sub).first()
    if user:
        return user
    
    cognito_attributes = fetch_cognito_user(sub)

    email = cognito_attributes.get("email")

    user = User(
        cognito_sub=sub,
        email=email,
        role=role)

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


def require_role(required_role: UserRole):
    def wrapper(user: User = Depends(get_current_user)):
        if user.role != required_role:
            raise HTTPException(status_code=403, detail="Forbidden")
        return user
    return wrapper