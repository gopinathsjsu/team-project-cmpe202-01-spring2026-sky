from fastapi import Request, HTTPException, Depends
from typing import Optional, List


class CurrentUser:
    def __init__(self, sub: str, email: Optional[str], groups: List[str]):
        self.sub = sub
        self.email = email
        self.groups = groups


def get_current_user(request: Request) -> CurrentUser:
    try:
        claims = (
            request.scope.get("aws.event", {})
            .get("requestContext", {})
            .get("authorizer", {})
            .get("jwt", {})
            .get("claims", {})
        )

        if not claims:
            raise HTTPException(status_code=401, detail="Unauthorized")

        print(claims)
        sub = claims.get("sub")
        email = claims.get("email")
        groups = claims.get("cognito:groups", [])
        print(sub)
        print(email)
        print(groups)

        if not sub:
            raise HTTPException(status_code=401, detail="Unauthorized")

        return CurrentUser(
            sub=sub,
            email=email,
            groups=groups if isinstance(groups, list) else [],
        )

    except Exception:
        raise HTTPException(status_code=401, detail="Unauthorized")


def require_group(group: str):
    def wrapper(user: CurrentUser = Depends(get_current_user)):
        if group not in user.groups:
            raise HTTPException(403, "Forbidden")
        return user
    return wrapper                  