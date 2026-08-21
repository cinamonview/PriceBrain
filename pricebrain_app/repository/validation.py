"""ValidatedProduct persist validation — docs/09 §6, docs/05 §3."""

from __future__ import annotations

from typing import Any

from pricebrain_app.repository.exceptions import RepositoryValidationError

_REQUIRED_FIELDS = (
    "canonical_product_id",
    "mall_id",
    "product_id",
    "raw_product_name",
    "normalized_product_name",
    "brand",
    "board_partner_id",
    "gpu_model_id",
    "vram_gb",
    "price",
    "product_url",
)


def validate_for_persist(data: dict[str, Any]) -> None:
    for field in _REQUIRED_FIELDS:
        value = data.get(field)
        if value is None or value == "":
            raise RepositoryValidationError(
                f"{field} is required for Firestore persist",
                field=field,
            )

    if not isinstance(data.get("price"), int) or data["price"] <= 0:
        raise RepositoryValidationError("price must be a positive integer", field="price")

    if not data.get("seller_id"):
        raise RepositoryValidationError(
            "seller_id is required for listings persist; Pipeline must provide "
            "seller_id (seller slug policy not defined in 05/09 — no Repository-side "
            "slug generation).",
            field="seller_id",
        )
