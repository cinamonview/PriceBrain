"""11번가 search adapter/parser tests — V2 Phase 3."""

from __future__ import annotations

import json
import pathlib
from datetime import datetime, timezone

import pytest

from pricebrain_app.crawler.adapters.elevenst import ElevenstCrawler, ElevenstHtmlFetcher
from pricebrain_app.crawler.exceptions import (
    CrawlerHTTPError,
    CrawlerParseError,
    CrawlerTimeoutError,
)
from pricebrain_app.crawler.http_client import HttpResponse
from pricebrain_app.crawler.malls.elevenst import (
    build_elevenst_product_url,
    build_elevenst_search_url,
)
from pricebrain_app.crawler.parser.elevenst_search import (
    elevenst_search_total_pages,
    parse_elevenst_search_json,
)

FIXTURES = pathlib.Path(__file__).parent / "fixtures" / "elevenst"
CRAWLED_AT = datetime(2026, 8, 26, 12, 0, 0, tzinfo=timezone.utc)


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class StubHttpClient:
    """Minimal HttpClient stand-in: scripted responses, no network."""

    def __init__(self, responses: list[object]) -> None:
        self._responses = list(responses)
        self.urls: list[str] = []
        self.closed = False

    def get(self, url: str) -> HttpResponse:
        self.urls.append(url)
        item = self._responses.pop(0) if self._responses else HttpResponse(200, "{}", url)
        if isinstance(item, Exception):
            raise item
        return item

    def close(self) -> None:
        self.closed = True


def json_response(payload: dict, url: str = "https://apis.11st.co.kr/x") -> HttpResponse:
    return HttpResponse(200, json.dumps(payload, ensure_ascii=False), url)


# --- URL building -----------------------------------------------------------


def test_search_url_encodes_keyword_and_page():
    url = build_elevenst_search_url("RTX 5070", page=2)
    assert "searchKeyword=RTX%205070" in url
    assert "pageNo=2" in url
    assert url.startswith("https://apis.11st.co.kr/search/api/tab?")


def test_search_url_encodes_korean_keyword():
    url = build_elevenst_search_url("그래픽카드")
    assert "searchKeyword=%EA%B7%B8%EB%9E%98%ED%94%BD%EC%B9%B4%EB%93%9C" in url
    assert "pageNo=1" in url


@pytest.mark.parametrize("keyword", ["", "   "])
def test_search_url_rejects_empty_keyword(keyword: str):
    with pytest.raises(ValueError, match="keyword is required"):
        build_elevenst_search_url(keyword)


@pytest.mark.parametrize("page", [0, -1])
def test_search_url_rejects_non_positive_page(page: int):
    with pytest.raises(ValueError, match="page must be >= 1"):
        build_elevenst_search_url("RTX 5070", page=page)


def test_product_url_is_rebuilt_from_numeric_id():
    assert (
        build_elevenst_product_url("8875337696")
        == "https://www.11st.co.kr/products/8875337696"
    )


def test_product_url_rejects_non_numeric_id():
    with pytest.raises(ValueError, match="must be numeric"):
        build_elevenst_product_url("abc123")


# --- search JSON parsing ----------------------------------------------------


def test_parses_normal_search_results():
    items = parse_elevenst_search_json(load("search_rtx.json"), crawled_at=CRAWLED_AT)
    names = [item["product_name"] for item in items]

    assert "GIGABYTE 지포스 RTX 5070 GAMING OC D7 12GB" in names
    assert all(item["mall"] == "ELEVENST" for item in items)
    assert all(item["crawled_at"] == CRAWLED_AT for item in items)
    assert all(str(item["product_id"]).isdigit() for item in items)


def test_product_url_never_uses_ad_tracking_link():
    payload = {
        "data": [
            {
                "items": [
                    {
                        "id": 8875337696,
                        "title": "MSI 지포스 RTX 5070 D7 12GB",
                        "finalPrc": 1000000,
                        "linkUrl": "https://action.adoffice.11st.co.kr/act/click/v1/landing",
                    }
                ]
            }
        ]
    }
    (item,) = parse_elevenst_search_json(payload)
    assert item["product_url"] == "https://www.11st.co.kr/products/8875337696"


def test_prefers_final_price_over_list_price():
    items = parse_elevenst_search_json(load("search_rtx.json"))
    trio = next(i for i in items if "트리오" in i["product_name"])
    assert trio["price"] == 1259000


def test_parses_string_price_with_separators():
    payload = {
        "data": [
            {
                "items": [
                    {
                        "id": 111,
                        "title": "MSI 지포스 RTX 5070 D7 12GB",
                        "finalPrc": "1,259,000",
                    }
                ]
            }
        ]
    }
    (item,) = parse_elevenst_search_json(payload)
    assert item["price"] == 1259000


def test_maps_sold_out_to_availability():
    items = parse_elevenst_search_json(load("search_rtx_p2.json"))
    sold_out = next(i for i in items if i["product_id"] == "8123456711")
    available = next(i for i in items if i["product_id"] == "8123456710")
    assert sold_out["availability"] is False
    assert available["availability"] is True


def test_defaults_seller_when_absent():
    payload = {"data": [{"items": [{"id": 1, "title": "MSI RTX 5070", "finalPrc": 100}]}]}
    (item,) = parse_elevenst_search_json(payload)
    assert item["seller"] == "11번가"


def test_deduplicates_repeated_product_within_page():
    items = parse_elevenst_search_json(load("search_rtx.json"))
    ids = [item["product_id"] for item in items]
    assert ids.count("8875337696") == 1
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"data": None},
        {"data": []},
        {"data": [{"items": None}]},
        {"data": [{"items": []}]},
        {"data": ["not-a-dict"]},
        {"data": [{"no_items_key": 1}]},
    ],
)
def test_empty_or_missing_collections_return_no_items(payload: dict):
    assert parse_elevenst_search_json(payload) == []


def test_non_dict_payload_returns_no_items():
    assert parse_elevenst_search_json([]) == []  # type: ignore[arg-type]


def test_malformed_items_are_skipped_not_raised():
    """One bad row must not discard the rest of the page."""
    items = parse_elevenst_search_json(load("search_rtx.json"))
    ids = {item["product_id"] for item in items}

    assert "8123456707" not in ids  # empty title
    assert "8123456708" not in ids  # price 0
    assert not any(item["product_id"] == "" for item in items)  # missing id
    assert len(items) == 8


def test_boolean_price_is_not_treated_as_number():
    payload = {
        "data": [{"items": [{"id": 1, "title": "MSI RTX 5070", "finalPrc": True}]}]
    }
    assert parse_elevenst_search_json(payload) == []


def test_total_pages_reported_when_present():
    assert elevenst_search_total_pages(load("search_rtx.json")) == 105
    assert elevenst_search_total_pages({}) is None
    assert elevenst_search_total_pages({"totalPage": "many"}) is None


# --- fetcher / adapter ------------------------------------------------------


def test_fetcher_requests_expected_search_url():
    http = StubHttpClient([json_response(load("search_rtx.json"))])
    fetcher = ElevenstHtmlFetcher(http)
    payload = fetcher.fetch_search_json("RTX 5070", page=2)

    assert payload["curPage"] == 1
    assert "searchKeyword=RTX%205070" in http.urls[0]
    assert "pageNo=2" in http.urls[0]


def test_fetcher_raises_on_non_200():
    http = StubHttpClient([HttpResponse(503, "", "https://apis.11st.co.kr/x")])
    with pytest.raises(CrawlerHTTPError):
        ElevenstHtmlFetcher(http).fetch_search_json("RTX 5070")


def test_fetcher_raises_parse_error_on_non_json_body():
    http = StubHttpClient([HttpResponse(200, "<html>nope</html>", "u")])
    with pytest.raises(CrawlerParseError, match="not JSON"):
        ElevenstHtmlFetcher(http).fetch_search_json("RTX 5070")


def test_fetcher_raises_parse_error_when_json_is_not_object():
    http = StubHttpClient([HttpResponse(200, "[1, 2, 3]", "u")])
    with pytest.raises(CrawlerParseError, match="not a JSON object"):
        ElevenstHtmlFetcher(http).fetch_search_json("RTX 5070")


def test_fetcher_propagates_timeout():
    http = StubHttpClient([CrawlerTimeoutError("timed out", url="u")])
    with pytest.raises(CrawlerTimeoutError):
        ElevenstHtmlFetcher(http).fetch_search_json("RTX 5070")


def test_crawler_search_returns_raw_products():
    http = StubHttpClient([json_response(load("search_rtx.json"))])
    crawler = ElevenstCrawler(fetcher=ElevenstHtmlFetcher(http))
    items = crawler.search("RTX 5070", crawled_at=CRAWLED_AT)

    assert len(items) == 8
    assert items[0]["mall"] == "ELEVENST"
    assert items[0]["product_url"].startswith("https://www.11st.co.kr/products/")


def test_crawler_search_pagination_requests_each_page():
    http = StubHttpClient(
        [json_response(load("search_rtx.json")), json_response(load("search_rtx_p2.json"))]
    )
    crawler = ElevenstCrawler(fetcher=ElevenstHtmlFetcher(http))

    page1 = crawler.search("RTX 5070", page=1)
    page2 = crawler.search("RTX 5070", page=2)

    assert "pageNo=1" in http.urls[0]
    assert "pageNo=2" in http.urls[1]
    assert len(page2) == 3
    # Page 2 repeats one product from page 1 — dedup is the batch's job, not the parser's.
    assert {i["product_id"] for i in page1} & {i["product_id"] for i in page2} == {
        "8875337696"
    }


def test_search_does_not_touch_the_product_detail_path():
    """The search path must not fall back to per-product HTML fetches."""
    http = StubHttpClient([json_response(load("search_rtx.json"))])
    ElevenstCrawler(fetcher=ElevenstHtmlFetcher(http)).search("RTX 5070")
    assert len(http.urls) == 1
    assert "/search/api/tab" in http.urls[0]
