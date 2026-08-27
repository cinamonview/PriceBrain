"""Persist service — identity safety boundary before repository writes.

All application persist entry points (ingest API, runner, search batch) must pass
through this module. Repository ``write_validated_product`` performs Firestore I/O only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from google.cloud.firestore_v1 import Client as FirestoreClient

from pricebrain_app.pipeline.persist_boundary import (
    DeferredPersistItem,
    PersistBoundaryMember,
    PersistBoundaryState,
    blocked_canonical_ids_from_state,
    review_reason_for_canonical,
)
from pricebrain_app.repository.exceptions import (
    IdentityReviewBlockedError,
    RepositoryError,
    RepositoryValidationError,
    UnknownGpuModelError,
)
from pricebrain_app.repository.gpu_repository import GpuRepository
from pricebrain_app.repository.stored_product_collision import (
    review_against_stored_product,
    review_reason_from_report,
)
from pricebrain_app.repository.service import _write_validated_product
from pricebrain_app.repository.validation import validate_for_persist


class PersistDecision(StrEnum):
    PERSISTED = "persisted"
    PERSIST_CANDIDATE = "persist_candidate"
    IDENTITY_REVIEW_BLOCKED = "identity_review_blocked"
    FAILED = "failed"


@dataclass(frozen=True)
class PersistOutcome:
    external_product_id: str
    product_name: str
    canonical_product_id: str | None
    decision: PersistDecision
    review_required: bool = False
    review_reason: str | None = None
    save_result: dict[str, str | bool] | None = None
    error_category: str | None = None
    message: str | None = None


@dataclass
class PersistBoundarySession:
    """Batch-scoped persist boundary — register candidates, finalize once."""

    db: FirestoreClient
    dry_run: bool = False
    _state: PersistBoundaryState = field(default_factory=PersistBoundaryState)

    @property
    def state(self) -> PersistBoundaryState:
        return self._state

    def register(
        self,
        validated: Mapping[str, Any],
        *,
        external_product_id: str,
        product_name: str,
    ) -> None:
        defer_validated_product(
            self._state,
            validated,
            external_product_id=external_product_id,
            product_name=product_name,
        )

    def finalize(self) -> list[PersistOutcome]:
        return finalize_boundary_state(
            self._state,
            db=self.db,
            dry_run=self.dry_run,
        )


def finalize_boundary_state(
    state: PersistBoundaryState,
    *,
    db: FirestoreClient,
    dry_run: bool,
) -> list[PersistOutcome]:
    """Preflight all candidates, then persist allowed items in one write phase."""
    if not state.deferred:
        return []

    blocked_batch = blocked_canonical_ids_from_state(state)
    preflight: list[tuple[DeferredPersistItem, PersistOutcome | None]] = []

    for item in state.deferred:
        canonical_id = str(item.validated.get("canonical_product_id") or "")
        if canonical_id in blocked_batch:
            reason = review_reason_for_canonical(
                canonical_id,
                state.all_members(),
                mpn_by_external=state.mpn_by_external,
            )
            preflight.append(
                (
                    item,
                    PersistOutcome(
                        external_product_id=item.external_product_id,
                        product_name=item.product_name,
                        canonical_product_id=canonical_id or None,
                        decision=PersistDecision.IDENTITY_REVIEW_BLOCKED,
                        review_required=True,
                        review_reason=reason,
                        error_category="identity_review",
                        message="persist blocked by collision review gate",
                    ),
                )
            )
            continue

        stored_report = review_against_stored_product(
            db,
            item.validated,
            external_product_id=item.external_product_id,
            product_name=item.product_name,
        )
        if stored_report is not None and stored_report.review_required:
            preflight.append(
                (
                    item,
                    PersistOutcome(
                        external_product_id=item.external_product_id,
                        product_name=item.product_name,
                        canonical_product_id=canonical_id or None,
                        decision=PersistDecision.IDENTITY_REVIEW_BLOCKED,
                        review_required=True,
                        review_reason=review_reason_from_report(stored_report),
                        error_category="identity_review",
                        message="persist blocked by stored product identity review",
                    ),
                )
            )
            continue

        if dry_run:
            preflight.append(
                (
                    item,
                    PersistOutcome(
                        external_product_id=item.external_product_id,
                        product_name=item.product_name,
                        canonical_product_id=canonical_id or None,
                        decision=PersistDecision.PERSIST_CANDIDATE,
                        message="persist candidate",
                    ),
                )
            )
            continue

        preflight.append((item, None))

    outcomes: list[PersistOutcome] = []
    for item, predetermined in preflight:
        if predetermined is not None:
            outcomes.append(predetermined)
            continue

        canonical_id = str(item.validated.get("canonical_product_id") or "")
        try:
            save_result = _write_validated_product(db, item.validated)
        except IdentityReviewBlockedError as exc:
            outcomes.append(
                PersistOutcome(
                    external_product_id=item.external_product_id,
                    product_name=item.product_name,
                    canonical_product_id=canonical_id or None,
                    decision=PersistDecision.IDENTITY_REVIEW_BLOCKED,
                    review_required=True,
                    review_reason=exc.review_reason,
                    error_category="identity_review",
                    message=str(exc),
                )
            )
            continue
        except Exception as exc:  # noqa: BLE001 - isolate one persist, keep batch alive
            outcomes.append(
                PersistOutcome(
                    external_product_id=item.external_product_id,
                    product_name=item.product_name,
                    canonical_product_id=canonical_id or None,
                    decision=PersistDecision.FAILED,
                    error_category=type(exc).__name__,
                    message=str(exc),
                )
            )
            continue

        outcomes.append(
            PersistOutcome(
                external_product_id=item.external_product_id,
                product_name=item.product_name,
                canonical_product_id=canonical_id or None,
                decision=PersistDecision.PERSISTED,
                save_result=save_result,
                message="persisted",
            )
        )

    return outcomes


def _ensure_eligible_for_persist(
    db: FirestoreClient,
    validated: Mapping[str, Any],
) -> None:
    """Mirror search-batch eligibility checks before boundary registration."""
    validate_for_persist(validated)
    gpu_repo = GpuRepository(db)
    partner_id = str(validated["board_partner_id"])
    if gpu_repo.get_partner(partner_id) is None:
        raise RepositoryValidationError(
            f"board_partner_id not found in GPU master: {partner_id}",
            field="board_partner_id",
        )
    model_id = str(validated["gpu_model_id"])
    if gpu_repo.get_model(model_id) is None:
        raise UnknownGpuModelError(
            f"gpu_model_id not found in GPU master: {model_id}",
            gpu_model_id=model_id,
        )


def persist_validated_product(
    db: FirestoreClient,
    validated: Mapping[str, Any],
    *,
    external_product_id: str,
    product_name: str,
    dry_run: bool = False,
    boundary_session: PersistBoundarySession | None = None,
) -> dict[str, str | bool]:
    """Persist one validated product through the identity safety boundary.

    When ``boundary_session`` is supplied the candidate is registered for batch
    finalize; otherwise a single-item session finalizes immediately.
    """
    _ensure_eligible_for_persist(db, validated)
    if boundary_session is not None:
        boundary_session.register(
            validated,
            external_product_id=external_product_id,
            product_name=product_name,
        )
        return {}

    session = PersistBoundarySession(db, dry_run=dry_run)
    session.register(
        validated,
        external_product_id=external_product_id,
        product_name=product_name,
    )
    outcomes = session.finalize()
    if not outcomes:
        raise RepositoryError("persist boundary produced no outcome")
    outcome = outcomes[0]
    if outcome.decision is PersistDecision.IDENTITY_REVIEW_BLOCKED:
        raise IdentityReviewBlockedError(
            outcome.message or "identity review blocked",
            canonical_product_id=str(outcome.canonical_product_id or ""),
            review_reason=outcome.review_reason,
        )
    if outcome.decision is PersistDecision.PERSIST_CANDIDATE:
        return {
            "status": "persist_candidate",
            "canonical_product_id": outcome.canonical_product_id or "",
        }
    if outcome.save_result is None:
        raise RepositoryError("persist boundary missing save result")
    return outcome.save_result


def defer_validated_product(
    state: PersistBoundaryState,
    validated: Mapping[str, Any],
    *,
    external_product_id: str,
    product_name: str,
) -> None:
    """Register a candidate for deferred batch finalize (multi-query / shared boundary)."""
    canonical_id = str(validated.get("canonical_product_id") or "")
    if not external_product_id or not canonical_id:
        return
    state.register(
        PersistBoundaryMember.from_validated(
            validated,
            external_product_id=external_product_id,
            product_name=product_name,
        )
    )
    state.deferred.append(
        DeferredPersistItem(
            external_product_id=external_product_id,
            product_name=product_name,
            validated=dict(validated),
        )
    )
