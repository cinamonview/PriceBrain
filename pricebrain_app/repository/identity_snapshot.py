"""Product identity snapshot — normalized metadata stored on persist for cross-session review."""

from __future__ import annotations

from typing import Any, Mapping

from pricebrain_app.pipeline.collision_review import review_signals_from_title


def build_identity_snapshot(validated: Mapping[str, Any]) -> dict[str, Any]:
    """Build a compact identity snapshot from a validated product."""
    normalized = str(validated.get("normalized_product_name") or "")
    raw = str(validated.get("raw_product_name") or normalized)
    signals = review_signals_from_title(normalized) | review_signals_from_title(raw)

    snapshot: dict[str, Any] = {
        "board_partner_id": str(validated["board_partner_id"]),
        "gpu_model_id": str(validated["gpu_model_id"]),
        "vram_gb": int(validated["vram_gb"]),
        "normalized_product_name": normalized,
        "variant_tokens": sorted(signals),
    }
    mpn = validated.get("manufacturer_part_number")
    if mpn:
        snapshot["manufacturer_part_number"] = str(mpn)
    model_name = validated.get("model_name")
    if model_name:
        snapshot["model_name"] = str(model_name)
    return snapshot


def variant_tokens_from_stored_product(stored: Mapping[str, Any]) -> frozenset[str]:
    """Read variant tokens from stored product, with backward-compatible fallback."""
    snapshot = stored.get("identity_snapshot")
    if not isinstance(snapshot, dict):
        normalized = str(stored.get("normalized_product_name") or "")
        return review_signals_from_title(normalized)

    if "variant_tokens" not in snapshot:
        normalized = str(
            snapshot.get("normalized_product_name")
            or stored.get("normalized_product_name")
            or ""
        )
        return review_signals_from_title(normalized)

    tokens = snapshot.get("variant_tokens")
    if tokens is None:
        normalized = str(
            snapshot.get("normalized_product_name")
            or stored.get("normalized_product_name")
            or ""
        )
        return review_signals_from_title(normalized)
    if isinstance(tokens, list):
        return frozenset(str(token) for token in tokens)
    normalized = str(stored.get("normalized_product_name") or "")
    return review_signals_from_title(normalized)


def variant_tokens_for_candidate(
    validated: Mapping[str, Any],
    *,
    product_name: str,
) -> frozenset[str]:
    normalized = str(validated.get("normalized_product_name") or product_name)
    raw = str(validated.get("raw_product_name") or product_name)
    return review_signals_from_title(normalized) | review_signals_from_title(raw)


def differing_variant_tokens(
    left: frozenset[str],
    right: frozenset[str],
) -> tuple[str, ...]:
    union = left | right
    return tuple(
        sorted(token for token in union if (token in left) != (token in right))
    )
