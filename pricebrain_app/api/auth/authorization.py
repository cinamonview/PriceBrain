"""Role-based authorization for operations API."""

from __future__ import annotations

from pricebrain_app.api.auth.models import OPS_READ_ROLES, AuthenticatedUser, OpsRole


def authorize_ops_read(user: AuthenticatedUser) -> None:
    if not user.has_any_role(OPS_READ_ROLES):
        raise PermissionError("Insufficient permissions")


def user_can_read_operations(user: AuthenticatedUser) -> bool:
    return user.has_any_role(OPS_READ_ROLES)
