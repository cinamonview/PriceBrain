"""Firebase ID token verification for operations API."""

from __future__ import annotations

from abc import ABC, abstractmethod

from pricebrain_app.api.auth.models import AuthenticatedUser, OpsRole


class TokenVerificationError(Exception):
    """Base token verification failure."""


class TokenExpiredError(TokenVerificationError):
    """Token is expired."""


class TokenInvalidError(TokenVerificationError):
    """Token is invalid or malformed."""


class TokenVerifier(ABC):
    @abstractmethod
    def verify(self, token: str) -> AuthenticatedUser:
        raise NotImplementedError


class FirebaseTokenVerifier(TokenVerifier):
    """Verify Firebase Authentication ID tokens via Admin SDK."""

    def verify(self, token: str) -> AuthenticatedUser:
        if not token or not token.strip():
            raise TokenInvalidError("Invalid authentication token")
        try:
            from firebase_admin import auth
        except ImportError as exc:
            raise TokenVerificationError("Authentication service unavailable") from exc
        try:
            decoded = auth.verify_id_token(token.strip())
        except auth.ExpiredIdTokenError as exc:
            raise TokenExpiredError("Authentication token expired") from exc
        except auth.InvalidIdTokenError as exc:
            raise TokenInvalidError("Invalid authentication token") from exc
        except auth.RevokedIdTokenError as exc:
            raise TokenInvalidError("Invalid authentication token") from exc
        except Exception as exc:
            raise TokenInvalidError("Invalid authentication token") from exc
        roles = roles_from_claims(decoded)
        claims = _safe_claims(decoded)
        return AuthenticatedUser(
            uid=str(decoded.get("uid", "")),
            email=decoded.get("email"),
            roles=roles,
            claims=claims,
        )


class FakeTokenVerifier(TokenVerifier):
    """In-memory token verifier for tests and local auth emulator mode."""

    def __init__(self) -> None:
        self._users: dict[str, AuthenticatedUser] = {}
        self._expired: set[str] = set()
        self._invalid: set[str] = set()
        self.seed_defaults()

    def seed_defaults(self) -> None:
        self.register(
            TEST_VIEWER_TOKEN,
            AuthenticatedUser(
                uid="test-viewer",
                email="viewer@example.com",
                roles=(OpsRole.OPS_VIEWER,),
            ),
        )
        self.register(
            TEST_OPERATOR_TOKEN,
            AuthenticatedUser(
                uid="test-operator",
                email="operator@example.com",
                roles=(OpsRole.OPS_OPERATOR,),
            ),
        )
        self.register(
            TEST_ADMIN_TOKEN,
            AuthenticatedUser(
                uid="test-admin",
                email="admin@example.com",
                roles=(OpsRole.OPS_ADMIN,),
            ),
        )
        self.register(
            TEST_NO_ROLE_TOKEN,
            AuthenticatedUser(uid="test-no-role", email="norole@example.com", roles=()),
        )
        self.register(
            TEST_UNKNOWN_ROLE_TOKEN,
            AuthenticatedUser(
                uid="test-unknown-role",
                email="unknown@example.com",
                roles=(),
                claims={"ops_roles": ["NOT_A_REAL_ROLE"]},
            ),
        )
        self._expired.add(TEST_EXPIRED_TOKEN)
        self._invalid.add(TEST_INVALID_TOKEN)

    def register(self, token: str, user: AuthenticatedUser) -> None:
        self._users[token] = user

    def verify(self, token: str) -> AuthenticatedUser:
        if not token or not token.strip():
            raise TokenInvalidError("Invalid authentication token")
        normalized = token.strip()
        if normalized in self._expired:
            raise TokenExpiredError("Authentication token expired")
        if normalized in self._invalid:
            raise TokenInvalidError("Invalid authentication token")
        user = self._users.get(normalized)
        if user is None:
            raise TokenInvalidError("Invalid authentication token")
        return user


TEST_VIEWER_TOKEN = "test-ops-viewer-token"
TEST_OPERATOR_TOKEN = "test-ops-operator-token"
TEST_ADMIN_TOKEN = "test-ops-admin-token"
TEST_NO_ROLE_TOKEN = "test-ops-no-role-token"
TEST_UNKNOWN_ROLE_TOKEN = "test-ops-unknown-role-token"
TEST_EXPIRED_TOKEN = "test-ops-expired-token"
TEST_INVALID_TOKEN = "test-ops-invalid-token"


def roles_from_claims(claims: dict) -> tuple[OpsRole, ...]:
    raw = claims.get("ops_roles") or claims.get("roles") or []
    if isinstance(raw, str):
        raw = [raw]
    roles: list[OpsRole] = []
    for item in raw:
        key = str(item).strip().upper()
        try:
            roles.append(OpsRole(key))
        except ValueError:
            continue
    return tuple(roles)


def _safe_claims(claims: dict) -> dict:
    blocked = frozenset({"token", "authorization", "access_token", "refresh_token", "id_token"})
    cleaned: dict = {}
    for key, value in claims.items():
        lowered = str(key).lower()
        if lowered in blocked:
            continue
        cleaned[key] = value
    return cleaned


_VERIFIER: TokenVerifier | None = None


def get_token_verifier() -> TokenVerifier:
    global _VERIFIER
    if _VERIFIER is not None:
        return _VERIFIER
    from pricebrain_app.config.settings import get_settings

    settings = get_settings()
    if settings.pricebrain_auth_emulator:
        _VERIFIER = FakeTokenVerifier()
    else:
        _VERIFIER = FirebaseTokenVerifier()
    return _VERIFIER


def reset_token_verifier() -> None:
    global _VERIFIER
    _VERIFIER = None
