"""08 pipeline orchestration — persist delegated to 09 (docs/08 §29)."""

from __future__ import annotations

from typing import Any

from pricebrain_app.pipeline.cleaner import clean
from pricebrain_app.pipeline.gpu_parser import parse_gpu
from pricebrain_app.pipeline.normalizer import normalize
from pricebrain_app.pipeline.product_classifier import classify_product
from pricebrain_app.pipeline.product_matcher import match_product
from pricebrain_app.pipeline.types import ValidatedProduct
from pricebrain_app.pipeline.validator import validate


def run_pipeline(raw_data: dict[str, Any]) -> ValidatedProduct:
    data = clean(raw_data)
    data = normalize(data)
    data = classify_product(data)
    data = parse_gpu(data)
    data = match_product(data)
    return validate(data)
