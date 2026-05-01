import json
import os
from functools import lru_cache

import requests
from jose import JWTError, jwt
from fastapi import Request, HTTPException, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.cognito_utils import get_cognito_client, get_user_pool_id, get_aws_region
from app.models.User import User, UserRole


def fetch_cognito_user(sub: str):
    response = get_cognito_client().admin_get_user(
        UserPoolId=get_user_pool_id(),
        Username=sub
    )

    attributes = {
        attr["Name"]: attr["Value"]
        for attr in response["UserAttributes"]
    }

    return attributes


def _normalize_groups(groups) -> list[str]:
    if groups is None:
        return []

    parsed_groups = groups
    if isinstance(groups, str):
        groups = groups.strip()
        if not groups:
            return []
        try:
            parsed_groups = json.loads(groups)
        except json.JSONDecodeError:
            parsed_groups = [group.strip() for group in groups.split(",") if group.strip()]

    if isinstance(parsed_groups, str):
        parsed_groups = [parsed_groups]
    elif not isinstance(parsed_groups, (list, tuple, set)):
        parsed_groups = [parsed_groups]

    normalized = []
    for group in parsed_groups:
        if group is None:
            continue
        value = str(group).strip().strip("[]\"' ").lower()
        if value:
            normalized.append(value)
    return normalized


def resolve_user_role(groups) -> UserRole | None:
    normalized_groups = _normalize_groups(groups)
    if not normalized_groups:
        return None

    if "admin" in normalized_groups:
        return UserRole.admin
    if "organizer" in normalized_groups:
        return UserRole.organizer
    if "attendee" in normalized_groups:
        return UserRole.attendee
    return None


@lru_cache(maxsize=1)
def _get_cognito_jwks_cached():
    url = (
        f"https://cognito-idp.{get_aws_region()}.amazonaws.com/"
        f"{get_user_pool_id()}/.well-known/jwks.json"
    )
    response = requests.get(url, timeout=5)
    response.raise_for_status()
    return response.json().get("keys", [])


def _get_cognito_jwks(*, force_refresh: bool = False):
    if force_refresh:
        _get_cognito_jwks_cached.cache_clear()
    return _get_cognito_jwks_cached()


def _get_cognito_issuer() -> str:
    return f"https://cognito-idp.{get_aws_region()}.amazonaws.com/{get_user_pool_id()}"


def _has_expected_client(claims: dict) -> bool:
    client_id = os.getenv("COGNITO_CLIENT_ID")
    if not client_id:
        return False

    token_use = claims.get("token_use")
    if token_use == "id":
        return claims.get("aud") == client_id
    if token_use == "access":
        return claims.get("client_id") == client_id
    return False


def _get_bearer_token(request: Request) -> str | None:
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return None
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()
    return None


def _decode_cognito_token(token: str) -> dict | None:
    try:
        header = jwt.get_unverified_header(token)
    except JWTError:
        return None

    kid = header.get("kid")
    if not kid:
        return None

    jwks = _get_cognito_jwks()
    key = next((k for k in jwks if k.get("kid") == kid), None)
    if not key:
        jwks = _get_cognito_jwks(force_refresh=True)
        key = next((k for k in jwks if k.get("kid") == kid), None)
        if not key:
            return None

    try:
        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            issuer=_get_cognito_issuer(),
            options={"verify_aud": False, "verify_exp": True, "verify_iss": True},
        )
        if not _has_expected_client(claims):
            return None
        return claims
    except JWTError:
        return None


def _extract_claims(request: Request) -> tuple[dict, str]:
    claims = (
        request.scope.get("aws.event", {})
        .get("requestContext", {})
        .get("authorizer", {})
        .get("jwt", {})
        .get("claims", {})
    )
    if claims:
        return claims, "aws.event"

    token = _get_bearer_token(request)
    if not token:
        return {}, "none"

    decoded = _decode_cognito_token(token)
    if not decoded:
        return {}, "authorization_header_invalid"
    return decoded, "authorization_header"


def _clean_optional_string(value) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    claims, _ = _extract_claims(request)
    if not claims:
        raise HTTPException(status_code=401, detail="Unauthorized")

    groups = claims.get("cognito:groups")
    resolved_role = resolve_user_role(groups) or UserRole.attendee

    sub = claims.get("sub")

    if not sub:
        raise HTTPException(status_code=401, detail="Unauthorized")
    user = db.query(User).filter_by(cognito_sub=sub).first()

    if user:
        name = _clean_optional_string(claims.get("name"))
        if not name and not user.name:
            try:
                cognito_attributes = fetch_cognito_user(sub)
                name = _clean_optional_string(cognito_attributes.get("name"))
            except Exception:
                name = None
        changed = False
        if user.role != resolved_role:
            user.role = resolved_role
            changed = True
        if name and user.name != name:
            user.name = name
            changed = True
        if changed:
            db.commit()
            db.refresh(user)
        return user

    try:
        cognito_attributes = fetch_cognito_user(sub)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Unable to load user profile from identity provider",
        ) from exc

    email = claims.get("email") or cognito_attributes.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="Authenticated user email is missing")

    name = _clean_optional_string(claims.get("name")) or _clean_optional_string(
        cognito_attributes.get("name")
    )

    user = User(
        cognito_sub=sub,
        name=name,
        email=email,
        role=resolved_role,
    )

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
