from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from pricebrain_app.crawler.parser.price import parse_price_attribute, parse_price_text
from pricebrain_app.crawler.parser.ssg import (
    parse_ssg_product_detail_html,
    parse_ssg_product_html,
    parse_ssg_search_html,
)

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def ssg_search_html() -> str:
    return (FIXTURES / "ssg_search_result.html").read_text(encoding="utf-8")


@pytest.fixture
def ssg_incomplete_html() -> str:
    return (FIXTURES / "ssg_search_incomplete.html").read_text(encoding="utf-8")


def test_parse_ssg_search_html_extracts_multiple_products(
    ssg_search_html: str,
) -> None:
    fixed_time = datetime(2026, 8, 19, 10, 0, 0, tzinfo=timezone.utc)
    items = parse_ssg_search_html(ssg_search_html, crawled_at=fixed_time)

    assert len(items) == 2

    first = items[0]
    assert first["mall"] == "SSG"
    assert first["product_id"] == "1000832367906"
    assert first["price"] == 2429000
    assert first["seller"] == "히트정보"
    assert first["product_url"] == (
        "https://www.ssg.com/item/itemView.ssg?itemId=1000832367906"
    )
    assert first["image_url"] == (
        "https://sitem.ssgcdn.com/itemimage/1000832367906.jpg"
    )
    assert "RTX 5080" in first["product_name"]
    assert "ZOTAC" in first["product_name"]
    assert first["crawled_at"] == fixed_time


def test_parse_ssg_product_html_single_unit(ssg_search_html: str) -> None:
    item = parse_ssg_product_html(ssg_search_html)
    assert item is not None
    assert item["product_id"] == "1000832367906"


def test_parse_price_attribute_and_text() -> None:
    assert parse_price_attribute("2429000") == 2429000
    assert parse_price_text("2,429,000원") == 2429000
    assert parse_price_text("") is None


def test_parse_ssg_search_html_skips_invalid_units(ssg_incomplete_html: str) -> None:
    items = parse_ssg_search_html(ssg_incomplete_html)
    assert items == []


def test_parse_ssg_search_html_empty_page() -> None:
    assert parse_ssg_search_html("<html><body></body></html>") == []


def test_parse_ssg_product_detail_html_extracts_fields() -> None:
    html = (
        Path(__file__).parent / "fixtures" / "ssg" / "product_detail_gpu.html"
    ).read_text(encoding="utf-8")
    fixed_time = datetime(2026, 8, 21, 12, 0, 0, tzinfo=timezone.utc)
    item = parse_ssg_product_detail_html(
        html,
        product_url="https://www.ssg.com/item/itemView.ssg?itemId=1000832367906",
        crawled_at=fixed_time,
    )
    assert item is not None
    assert item["product_id"] == "1000832367906"
    assert item["price"] == 1_599_000
    assert item["seller"] == "히트정보"
    assert item["crawled_at"] == fixed_time
