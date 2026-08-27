"""Read-only identity audit over repository title corpora — Phase 18.

Does not crawl production. Sources are on-disk 11st search fixtures and
``_phase4_sample`` dumps only.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any, Iterable

from pricebrain_app.crawler.parser.elevenst_search import parse_elevenst_search_json
from pricebrain_app.pipeline.collision_review import review_signals_from_title
from pricebrain_app.pipeline.identity_variants import extract_variant_token

_REPO_ROOT = Path(__file__).resolve().parents[2]
_FIXTURE_SEARCH = _REPO_ROOT / "pricebrain_app" / "tests" / "fixtures" / "elevenst"
_PHASE4_SAMPLE = _REPO_ROOT / "_phase4_sample"
_CRAWLED = datetime(2026, 8, 26, tzinfo=timezone.utc)

# Line markers used only to classify audit rows — not identity tokens.
_LINE_MARKERS: dict[str, tuple[str, ...]] = {
    "ZOTAC": ("SOLID CORE", "SOLID OC", "TRINITY", "AMP"),
    "MSI": (
        "VENTUS",
        "벤투스",
        "GAMING X",
        "게이밍 트리오",
        "SUPRIM",
        "SHADOW",
        "VANGUARD",
        "뱅가드",
    ),
    "ASUS": ("ROG STRIX", "ASTRAL", "TUF", "PRIME", "PROART"),
    "GIGABYTE": ("WINDFORCE", "GAMING OC", "AORUS", "MASTER", "AERO", "EAGLE", "INFINITY"),
    "COLORFUL": ("BATTLE AX", "VULCAN", "ULTRA", "GAMING"),
    "INNO3D": ("TWIN X2", "X3"),
    "PALIT": ("INFINITY", "GAMINGPRO", "GAMING PRO"),
    "GALAX": ("HOF", "EX GAMER"),
    "XFX": ("SWIFT", "QUICKSILVER"),
}

_COLOR_MARKERS = (
    "WHITE",
    "BLACK",
    "화이트",
    "블랙",
    "백색",
    "White",
    "Black",
)


class IdentityAuditClass(StrEnum):
    SAME_IDENTITY = "SAME_IDENTITY"
    DIFFERENT_IDENTITY = "DIFFERENT_IDENTITY"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    FALSE_MERGE_CANDIDATE = "FALSE_MERGE_CANDIDATE"
    FALSE_SPLIT_CANDIDATE = "FALSE_SPLIT_CANDIDATE"


@dataclass(frozen=True)
class IdentityAuditRow:
    title_a: str
    title_b: str
    canonical_a: str | None
    canonical_b: str | None
    variant_a: str | None
    variant_b: str | None
    collision_signals: tuple[str, ...]
    classification: IdentityAuditClass
    source: str


def corpus_sources() -> list[Path]:
    paths: list[Path] = []
    if _FIXTURE_SEARCH.is_dir():
        paths.extend(sorted(_FIXTURE_SEARCH.glob("search_rtx*.json")))
    if _PHASE4_SAMPLE.is_dir():
        paths.extend(sorted(_PHASE4_SAMPLE.glob("p4_*.json")))
    return paths


def load_elevenst_titles() -> tuple[list[str], list[str]]:
    """Return (unique titles, source path strings). Empty titles if corpus missing."""
    sources = corpus_sources()
    titles: dict[str, None] = {}
    source_labels: list[str] = []
    for path in sources:
        payload = json.loads(path.read_text(encoding="utf-8"))
        items = parse_elevenst_search_json(payload, crawled_at=_CRAWLED)
        source_labels.append(f"{path.as_posix()}:{len(items)}")
        for item in items:
            name = str(item.get("product_name") or "").strip()
            if name:
                titles[name] = None
    return list(titles.keys()), source_labels


def _markers_in_title(brand: str | None, title: str) -> frozenset[str]:
    compact = title.upper()
    found: set[str] = set()
    key = str(brand or "").upper()
    for marker in _LINE_MARKERS.get(key, ()):
        if marker.upper() in compact or marker in title:
            found.add(marker)
    for marker in _COLOR_MARKERS:
        if marker.upper() in compact or marker in title:
            found.add(marker)
    return frozenset(found)


def classify_pair(
    *,
    title_a: str,
    title_b: str,
    canonical_a: str | None,
    canonical_b: str | None,
    variant_a: str | None,
    variant_b: str | None,
    brand: str | None,
    signals_a: Iterable[str],
    signals_b: Iterable[str],
) -> IdentityAuditClass:
    sig_a = frozenset(signals_a)
    sig_b = frozenset(signals_b)
    if canonical_a and canonical_b and canonical_a != canonical_b:
        markers_a = _markers_in_title(brand, title_a)
        markers_b = _markers_in_title(brand, title_b)
        line_a = markers_a - set(_COLOR_MARKERS)
        line_b = markers_b - set(_COLOR_MARKERS)
        if line_a and line_a == line_b and variant_a == variant_b:
            return IdentityAuditClass.FALSE_SPLIT_CANDIDATE
        return IdentityAuditClass.DIFFERENT_IDENTITY
    if canonical_a == canonical_b and canonical_a:
        if sig_a != sig_b:
            return IdentityAuditClass.REVIEW_REQUIRED
        markers_a = _markers_in_title(brand, title_a) - set(_COLOR_MARKERS)
        markers_b = _markers_in_title(brand, title_b) - set(_COLOR_MARKERS)
        if markers_a and markers_b and markers_a != markers_b:
            return IdentityAuditClass.FALSE_MERGE_CANDIDATE
        return IdentityAuditClass.SAME_IDENTITY
    return IdentityAuditClass.REVIEW_REQUIRED


def audit_validated_pairs(
    records: list[dict[str, Any]],
    *,
    source: str,
) -> list[IdentityAuditRow]:
    """Group pipeline-validated records by canonical and emit pairwise rows."""
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        cid = str(record.get("canonical_product_id") or "")
        if cid:
            groups[cid].append(record)

    rows: list[IdentityAuditRow] = []
    for cid, members in groups.items():
        if len(members) < 2:
            continue
        for i, left in enumerate(members):
            for right in members[i + 1 :]:
                title_a = str(left.get("raw_product_name") or left.get("normalized_product_name") or "")
                title_b = str(right.get("raw_product_name") or right.get("normalized_product_name") or "")
                brand = str(left.get("brand") or right.get("brand") or "")
                var_a = extract_variant_token(
                    brand=brand,
                    normalized_name=str(left.get("normalized_product_name") or ""),
                )
                var_b = extract_variant_token(
                    brand=brand,
                    normalized_name=str(right.get("normalized_product_name") or ""),
                )
                sig_a = review_signals_from_title(title_a) | review_signals_from_title(
                    str(left.get("normalized_product_name") or "")
                )
                sig_b = review_signals_from_title(title_b) | review_signals_from_title(
                    str(right.get("normalized_product_name") or "")
                )
                classification = classify_pair(
                    title_a=title_a,
                    title_b=title_b,
                    canonical_a=cid,
                    canonical_b=cid,
                    variant_a=var_a,
                    variant_b=var_b,
                    brand=brand,
                    signals_a=sig_a,
                    signals_b=sig_b,
                )
                rows.append(
                    IdentityAuditRow(
                        title_a=title_a,
                        title_b=title_b,
                        canonical_a=cid,
                        canonical_b=cid,
                        variant_a=var_a,
                        variant_b=var_b,
                        collision_signals=tuple(sorted(sig_a | sig_b)),
                        classification=classification,
                        source=source,
                    )
                )
    return rows
