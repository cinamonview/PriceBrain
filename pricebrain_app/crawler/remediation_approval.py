"""Human approval verification for remediation execution."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from threading import Lock


@dataclass(frozen=True)
class ApprovalVerificationResult:
    verified: bool
    error_code: str | None = None
    message: str = ""


class RemediationApprovalVerifier:
    """In-memory approval token verifier — not for production secrets."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._tokens: dict[str, str] = {}

    def issue_token(self, action_id: str) -> str:
        token = secrets.token_urlsafe(24)
        digest = _token_digest(token)
        with self._lock:
            self._tokens[digest] = action_id.strip()
        return token

    def verify(
        self,
        *,
        action_id: str,
        approval_token: str | None,
        human_approval_required: bool,
        auto_executable: bool,
    ) -> ApprovalVerificationResult:
        if approval_token is None or not str(approval_token).strip():
            return ApprovalVerificationResult(
                verified=False,
                error_code="MISSING_APPROVAL_TOKEN",
                message="Approval token is required for EXECUTE mode",
            )
        digest = _token_digest(str(approval_token).strip())
        with self._lock:
            bound_action = self._tokens.get(digest)
        if bound_action is None:
            return ApprovalVerificationResult(
                verified=False,
                error_code="INVALID_APPROVAL_TOKEN",
                message="Approval token is invalid or expired",
            )
        if bound_action != action_id.strip():
            return ApprovalVerificationResult(
                verified=False,
                error_code="ACTION_ID_MISMATCH",
                message="Approval token does not match action_id",
            )
        return ApprovalVerificationResult(verified=True, message="Approval verified")

    def clear(self) -> None:
        with self._lock:
            self._tokens.clear()


_VERIFIER = RemediationApprovalVerifier()


def get_remediation_approval_verifier() -> RemediationApprovalVerifier:
    return _VERIFIER


def reset_remediation_approval_verifier() -> None:
    _VERIFIER.clear()


def issue_test_approval_token(action_id: str) -> str:
    return get_remediation_approval_verifier().issue_token(action_id)


def _token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
