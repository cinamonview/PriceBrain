"""Board-partner alias resolution — pipeline layer only.

Canonical IDs live in GPU_BOARD_PARTNERS and must match GPU master slugs.
Language/input aliases are a separate lookup so parser matching never mutates
the master catalog.
"""

from __future__ import annotations

import re

from pricebrain_app.pipeline.constants import (
    GPU_BOARD_PARTNER_ALIASES,
    GPU_BOARD_PARTNERS,
)

_ASCII_TOKEN = re.compile(r"^[A-Za-z0-9]+$")


def _alias_pairs() -> tuple[tuple[str, str], ...]:
    pairs: list[tuple[str, str]] = [(name, name) for name in GPU_BOARD_PARTNERS]
    for alias, canonical in GPU_BOARD_PARTNER_ALIASES.items():
        pairs.append((alias, canonical))
    pairs.sort(key=lambda item: len(item[0]), reverse=True)
    return tuple(pairs)


_ALIAS_PAIRS = _alias_pairs()

# Partners deferred from master — title markers block brandEngNm fallback so a bad
# mall brandEngNm (e.g. MSI on an EMTEK SKU) cannot invent a canonical partner.
_DEFERRED_PARTNER_TITLE_MARKERS: tuple[str, ...] = (
    "이엠텍",
    "EMTEK",
    "ABOVETOP",
    "YESTON",
)


def title_blocks_brand_eng_nm_fallback(text: str | None) -> bool:
    """True when title names a deferred/unlisted partner — skip brandEngNm recovery."""
    if not text:
        return False
    upper = text.upper()
    for marker in _DEFERRED_PARTNER_TITLE_MARKERS:
        if _ASCII_TOKEN.match(marker):
            if re.search(rf"\b{re.escape(marker)}\b", upper, re.IGNORECASE):
                return True
        elif marker in text:
            return True
    return False


def board_partner_from_brand_eng_nm(
    brand_eng_nm: str | None,
    *,
    title: str | None = None,
) -> str | None:
    """Map mall brandEngNm to a seeded canonical partner, or None."""
    if not brand_eng_nm or title_blocks_brand_eng_nm_fallback(title):
        return None
    return canonical_board_partner(brand_eng_nm)


def canonical_board_partner(text: str | None) -> str | None:
    """Return the canonical partner ID if `text` contains a known alias.

    ASCII tokens use word boundaries so GALAX does not match GALAXY.
    Non-ASCII (Korean) aliases are substring matches against the original text.
    """
    if not text:
        return None
    upper = text.upper()
    for alias, canonical in _ALIAS_PAIRS:
        if _ASCII_TOKEN.match(alias):
            if re.search(rf"\b{re.escape(alias)}\b", upper, re.IGNORECASE):
                return canonical
        elif alias in text:
            return canonical
    return None
