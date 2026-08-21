"""Raw price extraction helpers — docs/07 §8 (validation/normalization is 08)."""

from __future__ import annotations


def parse_price_text(value: str | None) -> int | None:
    """Extract integer digits from a display price string (raw extraction only)."""
    if value is None:
        return None
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    return int(digits) if digits else None


def parse_price_attribute(value: str | None) -> int | None:
    """Parse SSG data-react-unit-price or similar raw attribute values."""
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return parse_price_text(str(value))
