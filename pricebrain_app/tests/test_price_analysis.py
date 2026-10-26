"""Phase 2 price analysis — PRD §11 통계, §13 구매 적정성, §14 지표."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from pricebrain_app.analysis.models import PricePoint, PriceTrend, PurchaseVerdict
from pricebrain_app.analysis.price_stats import compute_price_stats, lowest_price_series
from pricebrain_app.analysis.product_analysis import ListingHistory, analyze_product
from pricebrain_app.analysis.purchase import assess_purchase
from pricebrain_app.api.analysis import _utcnow
from pricebrain_app.api.auth.dependencies import viewer_auth_header
from pricebrain_app.api.auth.verifier import FakeTokenVerifier, get_token_verifier, reset_token_verifier
from pricebrain_app.api.deps import get_firestore
from pricebrain_app.config.settings import clear_settings_cache
from pricebrain_app.main import app
from pricebrain_app.repository import constants as c
from pricebrain_app.tests.fake_firestore import FakeFirestoreClient

NOW = datetime(2026, 10, 20, 0, 0, tzinfo=timezone.utc)
PRODUCT_ID = "ZOTAC-RTX5080-SOLIDCORE-16GB"


def _days_ago(days: float) -> datetime:
    return NOW - timedelta(days=days)


def _series(*pairs: tuple[float, int]) -> list[PricePoint]:
    return [PricePoint(crawled_at=_days_ago(days), price=price) for days, price in pairs]


def _assess(points: list[PricePoint]):
    return assess_purchase(
        compute_price_stats(points, window_days=30, now=NOW),
        compute_price_stats(points, window_days=7, now=NOW),
    )


# --- 가격 통계 -------------------------------------------------------------


def test_stats_are_time_weighted_with_carried_in_price() -> None:
    points = _series((40, 1_000_000), (20, 900_000), (10, 950_000))

    stats = compute_price_stats(points, window_days=30, now=NOW)

    # 1,000,000 carried in for 10 days, then 900,000 for 10, then 950,000 for 10.
    assert stats.start_price == 1_000_000
    assert stats.current_price == 950_000
    assert stats.min_price == 900_000
    assert stats.max_price == 1_000_000
    assert stats.price_range == 100_000
    assert stats.average_price == 950_000
    assert stats.median_price == 950_000
    assert stats.price_change == -50_000
    assert stats.price_change_rate == -5.0
    assert stats.price_percentile == pytest.approx(33.3)
    assert stats.diff_from_min == 50_000
    assert stats.diff_from_average_rate == 0.0
    assert stats.coverage_days == 30.0
    assert stats.data_points == 3


def test_stats_window_shorter_than_history_ignores_older_changes() -> None:
    points = _series((40, 1_000_000), (20, 900_000), (10, 950_000))

    stats = compute_price_stats(points, window_days=7, now=NOW)

    assert stats.start_price == 950_000
    assert stats.min_price == stats.max_price == 950_000
    assert stats.price_change_rate == 0.0
    assert stats.price_percentile == 0.0


def test_stats_coverage_starts_at_first_observation() -> None:
    stats = compute_price_stats(_series((5, 1_000_000)), window_days=30, now=NOW)

    assert stats.observed_from == _days_ago(5)
    assert stats.coverage_days == 5.0
    assert stats.average_price == 1_000_000


def test_stats_without_points() -> None:
    stats = compute_price_stats([], window_days=30, now=NOW)

    assert stats.has_data is False
    assert stats.current_price is None
    assert stats.data_points == 0


def test_stats_drop_future_and_invalid_prices_and_accept_naive_datetimes() -> None:
    points = [
        PricePoint(crawled_at=(NOW - timedelta(days=10)).replace(tzinfo=None), price=1_000_000),
        PricePoint(crawled_at=NOW + timedelta(days=1), price=1),
        PricePoint(crawled_at=_days_ago(5), price=0),
    ]

    stats = compute_price_stats(points, window_days=30, now=NOW)

    assert stats.min_price == stats.max_price == 1_000_000
    assert stats.data_points == 1


def test_stats_single_point_at_now() -> None:
    stats = compute_price_stats(_series((0, 1_000_000)), window_days=30, now=NOW)

    assert stats.average_price == 1_000_000
    assert stats.price_percentile == 0.0


def test_lowest_price_series_tracks_cheapest_listing_over_time() -> None:
    merged = lowest_price_series(
        {
            "SSG_1": _series((30, 1_000_000), (10, 980_000)),
            "SSG_2": _series((20, 990_000), (5, 1_010_000)),
        }
    )

    assert [(point.crawled_at, point.price) for point in merged] == [
        (_days_ago(30), 1_000_000),
        (_days_ago(20), 990_000),
        (_days_ago(10), 980_000),
    ]


# --- 구매 적정성 -----------------------------------------------------------


def test_purchase_buy_consider_when_below_average_and_at_recent_low() -> None:
    assessment = _assess(_series((40, 1_000_000), (3, 920_000)))

    assert assessment.verdict is PurchaseVerdict.BUY_CONSIDER
    assert assessment.label == "구매 고려"
    assert assessment.trend is PriceTrend.DOWN
    assert "현재 가격은 최근 30일 평균보다 7.3% 낮습니다." in assessment.reasons
    assert "현재 가격이 최근 30일 최저가입니다." in assessment.reasons


def test_purchase_not_recommended_when_above_average_and_falling() -> None:
    assessment = _assess(_series((40, 900_000), (10, 1_200_000), (2, 1_050_000)))

    assert assessment.verdict is PurchaseVerdict.NOT_RECOMMENDED
    assert assessment.trend is PriceTrend.DOWN
    assert "현재 가격은 최근 30일 최저가와 150,000원 차이입니다." in assessment.reasons


def test_purchase_wait_when_price_is_flat() -> None:
    assessment = _assess(_series((40, 1_000_000)))

    assert assessment.verdict is PurchaseVerdict.WAIT
    assert assessment.trend is PriceTrend.FLAT


def test_purchase_wait_when_above_average_and_rising() -> None:
    assessment = _assess(_series((40, 900_000), (2, 1_000_000)))

    assert assessment.verdict is PurchaseVerdict.WAIT
    assert assessment.trend is PriceTrend.UP


def test_purchase_insufficient_data_for_short_history() -> None:
    assessment = _assess(_series((1, 1_000_000)))

    assert assessment.verdict is PurchaseVerdict.INSUFFICIENT_DATA


# --- 상품 분석 (판매처 포함) -----------------------------------------------


def test_analyze_product_uses_available_listings_for_lowest_price() -> None:
    analysis = analyze_product(
        product_id=PRODUCT_ID,
        product_name="ZOTAC RTX 5080 SOLID CORE 16GB",
        listings=[
            ListingHistory(
                listing_id="SSG_A",
                data={"mall_id": "SSG", "seller_id": "SSG_A", "status": "AVAILABLE", "availability": True},
                points=_series((40, 1_000_000), (3, 950_000)),
            ),
            ListingHistory(
                listing_id="SSG_SOLDOUT",
                data={"mall_id": "SSG", "status": "UNAVAILABLE", "availability": False},
                points=_series((40, 800_000)),
            ),
            ListingHistory(
                listing_id="SSG_B",
                data={"mall_id": "SSG", "status": "AVAILABLE", "availability": True},
                points=_series((40, 990_000)),
            ),
        ],
        window_days=30,
        now=NOW,
    )

    assert analysis.lowest_listing_id == "SSG_A"
    assert [item.listing_id for item in analysis.listings] == ["SSG_A", "SSG_B", "SSG_SOLDOUT"]
    assert analysis.stats.current_price == 950_000
    assert analysis.stats.min_price == 950_000
    assert analysis.stats.max_price == 990_000
    assert analysis.lowest_price_series[0].crawled_at == analysis.stats.window_start
    assert [point.price for point in analysis.lowest_price_series] == [990_000, 950_000]


def test_analyze_product_falls_back_to_listing_current_price() -> None:
    analysis = analyze_product(
        product_id=PRODUCT_ID,
        product_name=None,
        listings=[
            ListingHistory(
                listing_id="SSG_A",
                data={"current_price": 1_000_000, "crawled_at": _days_ago(10)},
                points=[],
            )
        ],
        window_days=30,
        now=NOW,
    )

    assert analysis.stats.current_price == 1_000_000
    assert analysis.purchase.verdict is PurchaseVerdict.WAIT


# --- API -------------------------------------------------------------------


@pytest.fixture
def analysis_client(monkeypatch: pytest.MonkeyPatch):
    db = FakeFirestoreClient()

    def override_get_firestore():
        yield db

    monkeypatch.setenv("PRICEBRAIN_AUTH_ENABLED", "true")
    clear_settings_cache()
    reset_token_verifier()
    verifier = FakeTokenVerifier()
    app.dependency_overrides[get_token_verifier] = lambda: verifier
    app.dependency_overrides[get_firestore] = override_get_firestore
    app.dependency_overrides[_utcnow] = lambda: NOW
    base = TestClient(app)

    class AuthedClient:
        def get(self, url: str, **kwargs):
            headers = dict(kwargs.pop("headers", {}))
            headers.setdefault("Authorization", viewer_auth_header()["Authorization"])
            return base.get(url, headers=headers, **kwargs)

    try:
        yield db, AuthedClient(), base
    finally:
        app.dependency_overrides.clear()
        reset_token_verifier()
        clear_settings_cache()


def _seed_listing(db: FakeFirestoreClient, listing_id: str, product_id: str, prices: list[tuple[float, int]]) -> None:
    db.collection(c.LISTINGS).document(listing_id).set(
        {
            "product_id": product_id,
            "mall_id": "SSG",
            "seller_id": f"SSG_{listing_id}",
            "current_price": prices[-1][1],
            "availability": True,
            "status": "AVAILABLE",
            "crawled_at": _days_ago(prices[-1][0]),
        }
    )
    for days, price in prices:
        crawled_at = _days_ago(days)
        db.collection(c.LISTINGS).document(listing_id).collection(c.PRICE_HISTORY).document(
            str(int(crawled_at.timestamp() * 1000))
        ).set({"price": price, "crawled_at": crawled_at})


def test_api_product_analysis(analysis_client) -> None:
    db, client, _ = analysis_client
    db.collection(c.PRODUCTS).document(PRODUCT_ID).set({"normalized_product_name": "ZOTAC RTX 5080"})
    _seed_listing(db, "SSG_1", PRODUCT_ID, [(40, 1_000_000), (3, 920_000)])
    _seed_listing(db, "SSG_OTHER", "OTHER-PRODUCT", [(40, 500_000)])

    response = client.get(f"/api/analysis/products/{PRODUCT_ID}", params={"window_days": 30})

    assert response.status_code == 200
    body = response.json()
    assert body["product_name"] == "ZOTAC RTX 5080"
    assert body["lowest_listing_id"] == "SSG_1"
    assert [item["listing_id"] for item in body["listings"]] == ["SSG_1"]
    assert body["stats"]["current_price"] == 920_000
    assert body["purchase"]["verdict"] == "BUY_CONSIDER"
    assert body["purchase"]["label"] == "구매 고려"


def test_api_product_analysis_not_found(analysis_client) -> None:
    _, client, _ = analysis_client

    assert client.get("/api/analysis/products/NOPE").status_code == 404


def test_api_product_analysis_rejects_unsupported_window(analysis_client) -> None:
    db, client, _ = analysis_client
    _seed_listing(db, "SSG_1", PRODUCT_ID, [(40, 1_000_000)])

    response = client.get(f"/api/analysis/products/{PRODUCT_ID}", params={"window_days": 14})

    assert response.status_code == 422


def test_api_list_products_sorted_by_name(analysis_client) -> None:
    db, client, _ = analysis_client
    db.collection(c.PRODUCTS).document("B-ID").set({"normalized_product_name": "RTX 5080"})
    db.collection(c.PRODUCTS).document("A-ID").set({"normalized_product_name": "RTX 4070"})

    response = client.get("/api/analysis/products")

    assert response.status_code == 200
    assert response.json()["products"] == [
        {"product_id": "A-ID", "product_name": "RTX 4070"},
        {"product_id": "B-ID", "product_name": "RTX 5080"},
    ]


def test_api_analysis_requires_authentication(analysis_client) -> None:
    _, _, anonymous = analysis_client

    assert anonymous.get("/api/analysis/products").status_code == 401
    assert anonymous.get(f"/api/analysis/products/{PRODUCT_ID}").status_code == 401


# --- 리포트 / 민감도 -------------------------------------------------------


def _analysis_for(prices: list[tuple[float, int]]):
    return analyze_product(
        product_id="P",
        product_name="P",
        listings=[
            ListingHistory(
                listing_id="SSG_1",
                data={"status": "AVAILABLE", "availability": True},
                points=_series(*prices),
            )
        ],
        window_days=30,
        now=NOW,
    )


def test_sensitivity_counts_change_with_thresholds() -> None:
    from pricebrain_app.analysis.report import sensitivity

    # 30일 평균 대비 약 -2.1%, 현재가가 최저가: 기본(-3%)에서는 관망, -2%로 완화하면 구매 고려.
    analyses = [_analysis_for([(30, 1_000_000), (5, 980_000), (2, 975_000)])]

    rows = {
        (row.below_average_rate, row.near_min_rate): row.counts
        for row in sensitivity(analyses, now=NOW, below_average_rates=(-2.0, -3.0), near_min_rates=(3.0,))
    }

    assert rows[(-3.0, 3.0)][PurchaseVerdict.WAIT] == 1
    assert rows[(-3.0, 3.0)][PurchaseVerdict.BUY_CONSIDER] == 0
    assert rows[(-2.0, 3.0)][PurchaseVerdict.BUY_CONSIDER] == 1


def test_assess_purchase_respects_custom_rules() -> None:
    from pricebrain_app.analysis.purchase import PurchaseRules

    points = _series((40, 1_000_000), (3, 920_000))
    stats = compute_price_stats(points, window_days=30, now=NOW)
    trend = compute_price_stats(points, window_days=7, now=NOW)

    strict = PurchaseRules(below_average_rate=-20.0)

    assert assess_purchase(stats, trend, strict).verdict is PurchaseVerdict.WAIT
    assert assess_purchase(stats, trend).verdict is PurchaseVerdict.BUY_CONSIDER


def test_show_price_analysis_cli_report() -> None:
    from pricebrain_app.scripts.show_price_analysis import run

    db = FakeFirestoreClient()
    db.collection(c.PRODUCTS).document(PRODUCT_ID).set({"normalized_product_name": "ZOTAC RTX 5080"})
    _seed_listing(db, "SSG_1", PRODUCT_ID, [(40, 1_000_000), (3, 920_000)])

    output = run(db, window_days=30, show_sensitivity=True, now=NOW)

    assert "ZOTAC RTX 5080" in output
    assert "920,000" in output
    assert "구매 고려" in output
    assert "BUY_CONSIDER 1" in output
    assert "판정 기준 민감도 (상품 1개)" in output


def test_show_price_analysis_cli_handles_no_products() -> None:
    from pricebrain_app.scripts.show_price_analysis import run

    assert run(FakeFirestoreClient(), now=NOW) == "분석할 상품이 없습니다."
