"""Authentication and authorization models for operations API."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class OpsRole(str, Enum):
    OPS_VIEWER = "OPS_VIEWER"
    OPS_OPERATOR = "OPS_OPERATOR"
    OPS_ADMIN = "OPS_ADMIN"


OPS_READ_ROLES = frozenset(
    {
        OpsRole.OPS_VIEWER,
        OpsRole.OPS_OPERATOR,
        OpsRole.OPS_ADMIN,
    }
)


@dataclass(frozen=True)
class AuthenticatedUser:
    uid: str
    email: str | None = None
    roles: tuple[OpsRole, ...] = ()
    claims: dict[str, Any] = field(default_factory=dict)

    def has_any_role(self, roles: frozenset[OpsRole]) -> bool:
        return any(role in roles for role in self.roles)
