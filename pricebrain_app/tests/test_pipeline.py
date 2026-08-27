from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from pricebrain_app.pipeline.cleaner import clean
from pricebrain_app.pipeline.exceptions import GpuProductFilteredError, PipelineValidationError
from pricebrain_app.pipeline.gpu_parser import has_gpu_keyword, parse_gpu
from pricebrain_app.pipeline.normalizer import normalize
from pricebrain_app.pipeline.product_matcher import build_canonical_product_id, match_product
from pricebrain_app.pipeline.runner import run_pipeline
from pricebrain_app.pipeline.validator import validate


@pytest.fixture
def sample_raw_product() -> dict:
    return {
        "mall": "SSG",
        "product_id": "1000832367906",
        "product_name": "HIT ZOTAC GAMING 지포스 RTX 5080 SOLID CORE OC D7 16GB",
        "price": 2429000,
        "seller": "히트정보",
        "product_url": (
            "https://www.ssg.com/item/itemView.ssg?"
            "itemId=1000832367906&click=itemMidArea02"
        ),
        "image_url": "//sitem.ssgcdn.com/itemimage/1000832367906.jpg",
        "crawled_at": datetime(2026, 8, 19, 10, 0, 0, tzinfo=timezone.utc),
    }


def test_cleaner_normal_input(sample_raw_product: dict) -> None:
    cleaned = clean(sample_raw_product)
    assert cleaned["product_name"].startswith("HIT ZOTAC")
    assert cleaned["seller"] == "히트정보"


def test_cleaner_empty_and_whitespace_input() -> None:
    cleaned = clean(
        {
            "product_name": "  ",
            "seller": "  HIT   정보  ",
            "product_url": "",
        }
    )
    assert cleaned["product_name"] is None
    assert cleaned["seller"] == "HIT 정보"


def test_normalizer_maps_fields(sample_raw_product: dict) -> None:
    data = normalize(clean(sample_raw_product))
    assert data["raw_product_name"] == sample_raw_product["product_name"]
    assert "RTX 5080" in data["normalized_product_name"]
    assert "지포스" not in data["normalized_product_name"]
    assert data["price"] == 2429000
    assert data["mall_id"] == "SSG"
    assert "click=" not in data["product_url"]
    assert data["image_url"].startswith("https://")


def test_gpu_parser_extracts_gpu_fields(sample_raw_product: dict) -> None:
    data = parse_gpu(normalize(clean(sample_raw_product)))
    assert data["brand"] == "ZOTAC"
    assert data["gpu_series"] == "RTX"
    assert data["gpu_model"] == "RTX 5080"
    assert data["gpu_model_id"] == "rtx_5080"
    assert data["vram_gb"] == 16


def test_gpu_parser_no_gpu_match() -> None:
    data = parse_gpu(
        normalize(
            clean(
                {
                    "product_name": "일반 USB 케이블 1m",
                    "mall": "SSG",
                }
            )
        )
    )
    assert "gpu_model" not in data
    assert has_gpu_keyword("일반 USB 케이블 1m") is False


@pytest.mark.parametrize(
    ("product_name", "expected_partner"),
    [
        ("SAPPHIRE PULSE 라데온 RX 9070 OC D6 16GB", "SAPPHIRE"),
        ("XFX 라데온 RX 9070 QUICK 319 D6 16GB", "XFX"),
    ],
)
def test_gpu_parser_extracts_amd_board_partners(
    product_name: str, expected_partner: str
) -> None:
    data = parse_gpu(
        normalize(
            clean(
                {
                    "mall": "ELEVENST",
                    "product_id": "amd-partner-001",
                    "product_name": product_name,
                    "price": 899000,
                    "seller": "테스트셀러",
                    "product_url": "https://www.11st.co.kr/products/8083397777",
                }
            )
        )
    )
    assert data["brand"] == expected_partner
    assert data["board_partner_id"] == expected_partner
    assert data["gpu_series"] == "RX"
    assert data["gpu_model"] == "RX 9070"
    assert data["gpu_model_id"] == "rx_9070"


def test_matcher_builds_canonical_id(sample_raw_product: dict) -> None:
    data = match_product(parse_gpu(normalize(clean(sample_raw_product))))
    assert data["canonical_product_id"] == "ZOTAC-RTX5080-SOLIDCORE-16GB"
    assert data["board_partner_id"] == "ZOTAC"
    assert data["seller_id"].startswith("SSG_")


def test_matcher_canonical_generation_failure() -> None:
    assert build_canonical_product_id({}) is None


def test_validator_accepts_valid_product(sample_raw_product: dict) -> None:
    pipeline_data = match_product(
        parse_gpu(normalize(clean(sample_raw_product)))
    )
    validated = validate(pipeline_data)
    assert validated["canonical_product_id"] == "ZOTAC-RTX5080-SOLIDCORE-16GB"
    assert validated["price"] == 2429000


def test_validator_missing_required_field(sample_raw_product: dict) -> None:
    data = match_product(parse_gpu(normalize(clean(sample_raw_product))))
    data.pop("product_id")
    with pytest.raises(PipelineValidationError, match="product_id"):
        validate(data)


def test_validator_invalid_price(sample_raw_product: dict) -> None:
    data = match_product(parse_gpu(normalize(clean(sample_raw_product))))
    data["price"] = 0
    with pytest.raises(PipelineValidationError, match="price"):
        validate(data)


def test_validator_filters_non_gpu_product() -> None:
    data = match_product(
        parse_gpu(
            normalize(
                clean(
                    {
                        "mall": "SSG",
                        "product_id": "1",
                        "product_name": "일반 키보드",
                        "price": 10000,
                        "product_url": "https://www.ssg.com/item/itemView.ssg?itemId=1",
                    }
                )
            )
        )
    )
    with pytest.raises(GpuProductFilteredError):
        validate(data)


def test_run_pipeline_end_to_end(sample_raw_product: dict) -> None:
    validated = run_pipeline(sample_raw_product)
    assert validated["product_id"] == "1000832367906"
    assert validated["gpu_model_id"] == "rtx_5080"
    assert validated["canonical_product_id"] == "ZOTAC-RTX5080-SOLIDCORE-16GB"


def test_run_pipeline_from_ssg_parser_fixture() -> None:
    from pricebrain_app.crawler.parser.ssg import parse_ssg_search_html

    html = (Path(__file__).parent / "fixtures" / "ssg_search_result.html").read_text(
        encoding="utf-8"
    )
    raw_items = parse_ssg_search_html(html)
    validated = run_pipeline(dict(raw_items[0]))
    assert validated["brand"] == "ZOTAC"
    assert validated["price"] == 2429000
