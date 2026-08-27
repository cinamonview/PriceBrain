"""11번가 ingest adapter tests — fixture HTML only."""

from __future__ import annotations

from pathlib import Path

import pytest

from pricebrain_app.crawler.adapters.elevenst import ElevenstCrawler, ElevenstProductParser
from pricebrain_app.crawler.parser.elevenst import parse_elevenst_product_detail_html
from pricebrain_app.crawler.exceptions import CrawlerParseError
from pricebrain_app.crawler.malls.elevenst import (
    extract_elevenst_product_id,
    validate_elevenst_product_url,
)

FIXTURES = Path(__file__).parent / "fixtures" / "elevenst"
TEST_URL = "https://www.11st.co.kr/products/8083397777"


def _read_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_validate_elevenst_product_url() -> None:
    assert validate_elevenst_product_url(TEST_URL) == TEST_URL
    assert extract_elevenst_product_id(TEST_URL) == "8083397777"


def test_elevenst_product_parser_extracts_fields_from_fixture() -> None:
    parser = ElevenstProductParser()
    html = _read_fixture("product_detail_gpu.html")
    raw = parse_elevenst_product_detail_html(html, product_url=TEST_URL)
    assert raw is not None
    assert raw.get("manufacturer_part_number") == "GV-N5070A"

    payload = parser.parse(html, url=TEST_URL)

    assert payload.product_id == "8083397777"
    assert "RTX 5070" in payload.product_name
    assert payload.mall_id == "elevenst"
    assert payload.price == 1_159_000
    assert payload.seller == "공식지정점_클릭"
    assert payload.product_url == TEST_URL
    assert payload.crawled_at is not None


def test_elevenst_product_parser_raises_on_empty_html() -> None:
    parser = ElevenstProductParser()
    with pytest.raises(CrawlerParseError, match="did not contain a parseable product"):
        parser.parse("<html><body></body></html>", url=TEST_URL)


def test_elevenst_crawler_parse_offline_fixture() -> None:
    crawler = ElevenstCrawler()
    parser = ElevenstProductParser()
    payload = parser.parse(_read_fixture("product_detail_gpu.html"), url=TEST_URL)
    assert payload.product_id == "8083397777"
    crawler.close()
