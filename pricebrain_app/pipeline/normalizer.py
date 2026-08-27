"""Normalization — docs/08 §6–§11."""

from __future__ import annotations

import re
from typing import Any

from pricebrain_app.pipeline.board_partners import canonical_board_partner
from pricebrain_app.pipeline.utils import (
    normalize_image_url,
    normalize_mall_code,
    normalize_price,
    normalize_product_url,
    normalize_seller_name,
    parse_crawled_at,
)

_BRACKET_PREFIX = re.compile(r"^\[([^\]]+)\]\s*")
_TRAILING_PUNCT = re.compile(r"!+$")


def _unwrap_leading_brackets(name: str) -> str:
    """Strip marketing brackets; unwrap a leading board-partner token.

    docs/08 §6 uses `[특가]` as noise. `[INNO3D]` is identity, not noise.
    """
    while True:
        match = _BRACKET_PREFIX.match(name)
        if not match:
            return name
        inner = match.group(1).strip()
        partner = canonical_board_partner(inner)
        remainder = name[match.end() :]
        if partner:
            name = f"{partner} {remainder}".strip()
        else:
            name = remainder


def _normalize_product_name(raw_name: str) -> str:
    """Basic product-name cleaning — docs/08 §6 (raw preserved separately)."""
    name = _unwrap_leading_brackets(raw_name)
    name = _TRAILING_PUNCT.sub("", name)
    name = re.sub(r"\s+", " ", name).strip()
    name = re.sub(r"(?i)^hit\s+", "", name)
    name = re.sub(r"지포스\s*", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def normalize(data: dict[str, Any]) -> dict[str, Any]:
    result = dict(data)

    if "product_name" in result and result["product_name"]:
        raw_name = str(result["product_name"])
        result.setdefault("raw_product_name", raw_name)
        result["normalized_product_name"] = _normalize_product_name(raw_name)
    elif result.get("raw_product_name"):
        result["normalized_product_name"] = _normalize_product_name(
            str(result["raw_product_name"])
        )

    mall = result.get("mall") or result.get("mall_id")
    if mall:
        result["mall"] = str(mall).strip()
        result["mall_id"] = normalize_mall_code(str(mall))

    if "price" in result:
        result["price"] = normalize_price(result["price"])

    seller = result.get("seller")
    if seller:
        result["seller"] = normalize_seller_name(str(seller))
        result["normalized_seller_name"] = result["seller"]

    if "product_url" in result:
        result["product_url"] = normalize_product_url(
            str(result["product_url"]) if result["product_url"] else None
        )

    if "image_url" in result:
        result["image_url"] = normalize_image_url(
            str(result["image_url"]) if result["image_url"] else None
        )

    if "crawled_at" in result:
        parsed = parse_crawled_at(result["crawled_at"])
        if parsed is not None:
            result["crawled_at"] = parsed

    return result
