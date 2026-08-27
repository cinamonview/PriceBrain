"""Persist boundary gate — block live/dry-run persist when collision review requires human review."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from pricebrain_app.pipeline.collision_review import (
    CollisionGroupReport,
    classify_collision_group,
    review_canonical_collisions,
)


@dataclass(frozen=True)
class DeferredPersistItem:
    external_product_id: str
    product_name: str
    validated: dict[str, Any]


@dataclass
class PersistBoundaryMember:
    external_product_id: str
    product_name: str
    canonical_product_id: str
    board_partner_id: str | None = None
    gpu_model_id: str | None = None
    manufacturer_part_number: str | None = None

    @classmethod
    def from_validated(
        cls,
        validated: Mapping[str, Any],
        *,
        external_product_id: str,
        product_name: str,
    ) -> PersistBoundaryMember:
        return cls(
            external_product_id=external_product_id,
            product_name=product_name,
            canonical_product_id=str(validated["canonical_product_id"]),
            board_partner_id=(
                str(validated["board_partner_id"])
                if validated.get("board_partner_id")
                else None
            ),
            gpu_model_id=(
                str(validated["gpu_model_id"]) if validated.get("gpu_model_id") else None
            ),
            manufacturer_part_number=(
                str(validated["manufacturer_part_number"])
                if validated.get("manufacturer_part_number")
                else None
            ),
        )


@dataclass
class PersistBoundaryState:
    """Accumulates persist candidates across bounded batches (e.g. multi-query observation)."""

    members_by_canonical: dict[str, list[PersistBoundaryMember]] = field(
        default_factory=dict
    )
    mpn_by_external: dict[str, str | None] = field(default_factory=dict)
    deferred: list[DeferredPersistItem] = field(default_factory=list)

    def register(self, member: PersistBoundaryMember) -> None:
        self.members_by_canonical.setdefault(member.canonical_product_id, []).append(member)
        self.mpn_by_external[member.external_product_id] = member.manufacturer_part_number

    def all_members(self) -> tuple[PersistBoundaryMember, ...]:
        members: list[PersistBoundaryMember] = []
        for group in self.members_by_canonical.values():
            members.extend(group)
        return tuple(members)


def collision_reports_for_members(
    members: tuple[PersistBoundaryMember, ...] | list[PersistBoundaryMember],
    *,
    mpn_by_external: Mapping[str, str | None] | None = None,
) -> tuple[CollisionGroupReport, ...]:
    lookup = dict(mpn_by_external or {})
    for member in members:
        lookup.setdefault(member.external_product_id, member.manufacturer_part_number)
    return review_canonical_collisions(members, mpn_by_external=lookup)


def blocked_canonical_ids(
    members: tuple[PersistBoundaryMember, ...] | list[PersistBoundaryMember],
    *,
    mpn_by_external: Mapping[str, str | None] | None = None,
) -> set[str]:
    reports = collision_reports_for_members(members, mpn_by_external=mpn_by_external)
    return {report.canonical_product_id for report in reports if report.review_required}


def review_reason_for_canonical(
    canonical_product_id: str,
    members: tuple[PersistBoundaryMember, ...] | list[PersistBoundaryMember],
    *,
    mpn_by_external: Mapping[str, str | None] | None = None,
) -> str | None:
    group_members = [
        member
        for member in members
        if member.canonical_product_id == canonical_product_id
    ]
    if len(group_members) < 2:
        return None
    report = classify_collision_group(
        canonical_product_id=canonical_product_id,
        members=group_members,
        mpn_by_external=mpn_by_external,
    )
    if report is None or not report.review_required:
        return None
    if report.detected_variant_differences:
        return ",".join(report.detected_variant_differences)
    return report.collision_class.value


def blocked_canonical_ids_from_state(state: PersistBoundaryState) -> set[str]:
    return blocked_canonical_ids(state.all_members(), mpn_by_external=state.mpn_by_external)
