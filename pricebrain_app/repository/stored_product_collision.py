"""Cross-session identity review — compare new candidates against stored products."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from google.cloud.firestore_v1 import Client as FirestoreClient

from pricebrain_app.pipeline.collision_review import (
    CollisionClass,
    CollisionGroupReport,
    classify_collision_group,
)
from pricebrain_app.pipeline.persist_boundary import PersistBoundaryMember
from pricebrain_app.repository.identity_snapshot import (
    differing_variant_tokens,
    variant_tokens_for_candidate,
    variant_tokens_from_stored_product,
)
from pricebrain_app.repository.product_repository import ProductRepository

_EXISTING_PRODUCT_EXTERNAL_ID = "__existing_product__"


@dataclass(frozen=True)
class StoredProductCollisionMember:
    external_product_id: str
    product_name: str
    canonical_product_id: str
    board_partner_id: str | None = None
    gpu_model_id: str | None = None


def review_reason_from_report(report: CollisionGroupReport) -> str:
    if report.detected_variant_differences:
        return ",".join(report.detected_variant_differences)
    return report.collision_class.value


def review_stored_mapping(
    stored: Mapping[str, Any],
    validated: Mapping[str, Any],
    *,
    external_product_id: str,
    product_name: str,
) -> CollisionGroupReport | None:
    """Compare candidate identity against an already-loaded product document."""
    canonical_id = str(validated.get("canonical_product_id") or "")
    if not canonical_id:
        return None

    candidate_title = str(
        validated.get("normalized_product_name") or product_name
    )

    stored_vram = stored.get("vram_gb")
    candidate_vram = validated.get("vram_gb")
    if stored_vram is not None and candidate_vram is not None:
        if int(stored_vram) != int(candidate_vram):
            return CollisionGroupReport(
                canonical_product_id=canonical_id,
                member_count=2,
                external_product_ids=(_EXISTING_PRODUCT_EXTERNAL_ID, external_product_id),
                titles=(
                    str(stored.get("normalized_product_name") or ""),
                    candidate_title,
                ),
                detected_variant_differences=("vram_mismatch",),
                collision_class=CollisionClass.C4_HIGH_RISK,
                review_required=True,
                mpn_values=(
                    stored.get("manufacturer_part_number"),
                    validated.get("manufacturer_part_number"),
                ),
            )

    stored_signals = variant_tokens_from_stored_product(stored)
    candidate_signals = variant_tokens_for_candidate(
        validated,
        product_name=product_name,
    )
    signal_diff = differing_variant_tokens(stored_signals, candidate_signals)
    if signal_diff:
        return CollisionGroupReport(
            canonical_product_id=canonical_id,
            member_count=2,
            external_product_ids=(_EXISTING_PRODUCT_EXTERNAL_ID, external_product_id),
            titles=(
                str(stored.get("normalized_product_name") or ""),
                candidate_title,
            ),
            detected_variant_differences=signal_diff,
            collision_class=CollisionClass.C3_VARIANT_COLLISION,
            review_required=True,
            mpn_values=(
                stored.get("manufacturer_part_number"),
                validated.get("manufacturer_part_number"),
            ),
        )

    stored_member = StoredProductCollisionMember(
        external_product_id=_EXISTING_PRODUCT_EXTERNAL_ID,
        product_name=str(stored.get("normalized_product_name") or ""),
        canonical_product_id=canonical_id,
        board_partner_id=(
            str(stored["board_partner_id"]) if stored.get("board_partner_id") else None
        ),
        gpu_model_id=(
            str(stored["gpu_model_id"]) if stored.get("gpu_model_id") else None
        ),
    )
    candidate_member = PersistBoundaryMember.from_validated(
        validated,
        external_product_id=external_product_id,
        product_name=candidate_title,
    )
    mpn_lookup = {
        _EXISTING_PRODUCT_EXTERNAL_ID: (
            str(stored["manufacturer_part_number"])
            if stored.get("manufacturer_part_number")
            else None
        ),
        external_product_id: (
            str(validated["manufacturer_part_number"])
            if validated.get("manufacturer_part_number")
            else None
        ),
    }
    return classify_collision_group(
        canonical_product_id=canonical_id,
        members=(stored_member, candidate_member),
        mpn_by_external=mpn_lookup,
    )


def review_against_stored_product(
    db: FirestoreClient,
    validated: Mapping[str, Any],
    *,
    external_product_id: str,
    product_name: str,
) -> CollisionGroupReport | None:
    """Compare one candidate with an existing Firestore product (single-doc lookup)."""
    canonical_id = str(validated.get("canonical_product_id") or "")
    if not canonical_id:
        return None

    stored = ProductRepository(db).get_by_canonical_id(canonical_id)
    if stored is None:
        return None
    return review_stored_mapping(
        stored,
        validated,
        external_product_id=external_product_id,
        product_name=product_name,
    )
