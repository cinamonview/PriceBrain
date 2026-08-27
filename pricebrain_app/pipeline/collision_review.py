"""Read-only canonical collision review guard — Phase 10 pilot."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping, Protocol


class CollisionClass(str, Enum):
    C2_NORMAL_LISTING = "C2_NORMAL_LISTING"
    C3_VARIANT_COLLISION = "C3_VARIANT_COLLISION"
    C4_HIGH_RISK = "C4_HIGH_RISK"


_DISTRIBUTOR_SUFFIXES: tuple[str, ...] = (
    "제이씨현",
    "피씨디렉트",
    "대원씨티에스",
    "인텍앤컴퍼니",
    "이엠텍",
)

_REVIEW_SIGNALS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("WHITE", re.compile(r"\bWHITE\b|\bWhite\b|화이트|백색")),
    ("BLACK", re.compile(r"\bBLACK\b|\bBlack\b|블랙(?!웰)")),
    ("ICE", re.compile(r"\bICE\b")),
    ("HELLHOUND", re.compile(r"HELLHOUND|헬하운드", re.I)),
    ("REAPER", re.compile(r"\bREAPER\b|리퍼", re.I)),
    ("AORUS", re.compile(r"\bAORUS\b")),
    ("TUF", re.compile(r"\bTUF\b")),
    ("ROG", re.compile(r"\bROG\b")),
    ("WINDFORCE", re.compile(r"WINDFORCE|윈드포스", re.I)),
    ("SOLID OC", re.compile(r"SOLID\s+OC", re.I)),
    ("SOLID CORE", re.compile(r"SOLID\s+CORE", re.I)),
)


class CollisionMember(Protocol):
    external_product_id: str | None
    product_name: str
    canonical_product_id: str | None
    board_partner_id: str | None
    gpu_model_id: str | None


@dataclass(frozen=True)
class CollisionGroupReport:
    canonical_product_id: str
    member_count: int
    external_product_ids: tuple[str, ...]
    titles: tuple[str, ...]
    detected_variant_differences: tuple[str, ...]
    collision_class: CollisionClass
    review_required: bool
    mpn_values: tuple[str | None, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "canonical_product_id": self.canonical_product_id,
            "member_count": self.member_count,
            "external_product_ids": list(self.external_product_ids),
            "titles": list(self.titles),
            "detected_variant_differences": list(self.detected_variant_differences),
            "collision_class": self.collision_class.value,
            "review_required": self.review_required,
            "mpn_values": list(self.mpn_values),
        }


def _normalize_listing_title(title: str) -> str:
    normalized = title.strip()
    for suffix in _DISTRIBUTOR_SUFFIXES:
        normalized = normalized.removesuffix(suffix).removesuffix(f"{suffix}-").strip()
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.upper()


def review_signals_from_title(title: str) -> frozenset[str]:
    """Return collision-review variant signals detected in a title."""
    return frozenset(_title_signals(title))


def _title_signals(title: str) -> set[str]:
    signals: set[str] = set()
    for label, pattern in _REVIEW_SIGNALS:
        if pattern.search(title):
            signals.add(label)
    return signals


def _member_mpn(member: CollisionMember, mpn_by_external: Mapping[str, str | None]) -> str | None:
    external_id = member.external_product_id
    if not external_id:
        return None
    return mpn_by_external.get(external_id)


def classify_collision_group(
    *,
    canonical_product_id: str,
    members: Iterable[CollisionMember],
    mpn_by_external: Mapping[str, str | None] | None = None,
) -> CollisionGroupReport | None:
    """Classify one canonical collision group. Returns None when fewer than 2 members."""
    member_list = [member for member in members if member.external_product_id]
    if len(member_list) < 2:
        return None

    mpn_lookup = mpn_by_external or {}
    partners = {member.board_partner_id for member in member_list if member.board_partner_id}
    gpu_models = {member.gpu_model_id for member in member_list if member.gpu_model_id}

    external_ids = tuple(str(member.external_product_id) for member in member_list)
    titles = tuple(member.product_name for member in member_list)
    mpn_values = tuple(_member_mpn(member, mpn_lookup) for member in member_list)

    if len(partners) > 1 or len(gpu_models) > 1:
        return CollisionGroupReport(
            canonical_product_id=canonical_product_id,
            member_count=len(member_list),
            external_product_ids=external_ids,
            titles=titles,
            detected_variant_differences=("board_partner_or_gpu_model_mismatch",),
            collision_class=CollisionClass.C4_HIGH_RISK,
            review_required=True,
            mpn_values=mpn_values,
        )

    known_mpns = {value for value in mpn_values if value}
    if len(known_mpns) > 1:
        return CollisionGroupReport(
            canonical_product_id=canonical_product_id,
            member_count=len(member_list),
            external_product_ids=external_ids,
            titles=titles,
            detected_variant_differences=("mpn_mismatch",),
            collision_class=CollisionClass.C3_VARIANT_COLLISION,
            review_required=True,
            mpn_values=mpn_values,
        )

    normalized_titles = {_normalize_listing_title(title) for title in titles}
    if len(normalized_titles) == 1:
        return CollisionGroupReport(
            canonical_product_id=canonical_product_id,
            member_count=len(member_list),
            external_product_ids=external_ids,
            titles=titles,
            detected_variant_differences=(),
            collision_class=CollisionClass.C2_NORMAL_LISTING,
            review_required=False,
            mpn_values=mpn_values,
        )

    signal_sets = [_title_signals(title) for title in titles]
    union_signals = set().union(*signal_sets)
    differing_signals = tuple(
        sorted(
            signal
            for signal in union_signals
            if not all(signal in signals for signals in signal_sets)
        )
    )

    if differing_signals:
        return CollisionGroupReport(
            canonical_product_id=canonical_product_id,
            member_count=len(member_list),
            external_product_ids=external_ids,
            titles=titles,
            detected_variant_differences=differing_signals,
            collision_class=CollisionClass.C3_VARIANT_COLLISION,
            review_required=True,
            mpn_values=mpn_values,
        )

    return CollisionGroupReport(
        canonical_product_id=canonical_product_id,
        member_count=len(member_list),
        external_product_ids=external_ids,
        titles=titles,
        detected_variant_differences=("title_normalization_mismatch",),
        collision_class=CollisionClass.C3_VARIANT_COLLISION,
        review_required=True,
        mpn_values=mpn_values,
    )


def review_canonical_collisions(
    members: Iterable[CollisionMember],
    *,
    mpn_by_external: Mapping[str, str | None] | None = None,
) -> tuple[CollisionGroupReport, ...]:
    """Review all canonical groups with 2+ external IDs — read-only."""
    grouped: dict[str, list[CollisionMember]] = defaultdict(list)
    for member in members:
        canonical_id = member.canonical_product_id
        external_id = member.external_product_id
        if not canonical_id or not external_id:
            continue
        grouped[canonical_id].append(member)

    reports: list[CollisionGroupReport] = []
    for canonical_id, group_members in sorted(grouped.items()):
        if len(group_members) < 2:
            continue
        report = classify_collision_group(
            canonical_product_id=canonical_id,
            members=group_members,
            mpn_by_external=mpn_by_external,
        )
        if report is not None:
            reports.append(report)
    return tuple(reports)
