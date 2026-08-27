"""Manufacturer-specific variant tokens for canonical product identity — Phase 10 pilot.

Global color/OC tokens are intentionally excluded. Tokens are matched longest-first
per board partner; see ``MANUFACTURER_VARIANT_TOKENS``.
"""

from __future__ import annotations

from typing import Final

# Global variant phrases already in production — longest first.
GLOBAL_VARIANT_PHRASES: Final[tuple[tuple[str, str], ...]] = (
    ("SOLID CORE", "SOLIDCORE"),
    ("WINDFORCE", "WINDFORCE"),
    ("GAMING OC", "GAMINGOC"),
    ("SUPER", "SUPER"),
)

# Manufacturer-bound phrases only — not applied across brands.
MANUFACTURER_VARIANT_TOKENS: Final[dict[str, tuple[tuple[str, str], ...]]] = {
    "ZOTAC": (
        ("AMP EXTREME", "AMPEXTREME"),
        ("SOLID OC", "SOLIDOC"),
        ("TRINITY", "TRINITY"),
        ("AMP", "AMP"),
    ),
    "GIGABYTE": (
        ("GAMING OC ICE", "GAMINGOCICE"),
        ("MASTER ICE", "MASTERICE"),
        ("INFINITY", "INFINITY"),
        ("STEALTH", "STEALTH"),
        ("MASTER", "MASTER"),
        ("AERO", "AERO"),
        ("EAGLE", "EAGLE"),
        ("AORUS", "AORUS"),
        ("ICE", "ICE"),
    ),
    "MSI": (
        ("GAMING TRIO", "GAMINGTRIO"),
        ("게이밍 트리오", "GAMINGTRIO"),
        ("GAMING X", "GAMINGX"),
        ("VANGUARD", "VANGUARD"),
        ("뱅가드", "VANGUARD"),
        ("VENTUS", "VENTUS"),
        ("벤투스", "VENTUS"),
        ("SUPRIM", "SUPRIM"),
        ("SHADOW", "SHADOW"),
    ),
    "ASUS": (
        ("ROG ASTRAL", "ROGASTRAL"),
        ("PROART", "PROART"),
        ("PRIME", "PRIME"),
        ("TUF", "TUF"),
        ("ROG", "ROG"),
    ),
    "POWERCOLOR": (
        ("HELLHOUND", "HELLHOUND"),
        ("헬 하운드", "HELLHOUND"),
        ("헬하운드", "HELLHOUND"),
        ("REAPER", "REAPER"),
        ("RED DEVIL", "REDDEVIL"),
        ("레드 데빌", "REDDEVIL"),
        ("레드데빌", "REDDEVIL"),
    ),
}


def extract_variant_token(*, brand: str | None, normalized_name: str) -> str | None:
    """Return a compact variant slug for canonical ID priority 3, or None."""
    if not normalized_name:
        return None

    compact = normalized_name.upper().replace(" ", "")
    brand_key = str(brand or "").upper()

    if brand_key in MANUFACTURER_VARIANT_TOKENS:
        for phrase, slug in MANUFACTURER_VARIANT_TOKENS[brand_key]:
            if phrase.replace(" ", "") in compact:
                return slug

    for phrase, slug in GLOBAL_VARIANT_PHRASES:
        if phrase.replace(" ", "") in compact:
            return slug

    return None
