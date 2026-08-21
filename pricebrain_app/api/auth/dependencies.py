"""FastAPI authentication dependencies for operations API."""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from pricebrain_app.api.auth.authorization import authorize_ops_read
from pricebrain_app.api.auth.models import AuthenticatedUser, OpsRole
from pricebrain_app.api.auth.verifier import (
    FakeTokenVerifier,
    TokenExpiredError,
    TokenInvalidError,
    TokenVerificationError,
    TokenVerifier,
    get_token_verifier,
    reset_token_verifier,
    TEST_VIEWER_TOKEN,
)
from pricebrain_app.config.settings import get_settings

bearer_scheme = HTTPBearer(auto_error=False, scheme_name="BearerAuth", description="Firebase ID token")


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    verifier: TokenVerifier = Depends(get_token_verifier),
) -> AuthenticatedUser:
    settings = get_settings()
    if not settings.pricebrain_auth_enabled:
        return AuthenticatedUser(
            uid="local-dev",
            email=None,
            roles=(OpsRole.OPS_VIEWER,),
        )
    if credentials is None or not credentials.credentials.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return verifier.verify(credentials.credentials)
    except TokenExpiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except (TokenInvalidError, TokenVerificationError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def require_ops_viewer(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
    try:
        authorize_ops_read(user)
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        ) from exc
    return user


def clear_auth_dependency_overrides() -> None:
    from pricebrain_app.main import app

    app.dependency_overrides.pop(get_token_verifier, None)


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def viewer_auth_header() -> dict[str, str]:
    return auth_header(TEST_VIEWER_TOKEN)
