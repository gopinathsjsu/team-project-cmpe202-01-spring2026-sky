from fastapi import Header, HTTPException, Depends
from typing import Optional, List


class CurrentUser:
    def __init__(self, sub: str, email: Optional[str], groups: List[str]):
        self.sub = sub
        self.email = email
        self.groups = groups


def get_current_user(
    sub: Optional[str] = Header(None, alias="x-user-sub"),
    email: Optional[str] = Header(None, alias="x-user-email"),
    groups: Optional[str] = Header("", alias="x-user-groups"),
) -> CurrentUser:

    if not sub:
        raise HTTPException(401, "Unauthorized")

    return CurrentUser(
        sub=sub,
        email=email,
        groups=groups.split(",") if groups else [],
    )


def require_group(group: str):
    def wrapper(user: CurrentUser = Depends(get_current_user)):
        if group not in user.groups:
            raise HTTPException(403, "Forbidden")
        return user
    return wrapper