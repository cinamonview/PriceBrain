"""Canonical mall ID policy and listing lookup consistency — V2 Phase 2.

Policy under test:
  canonical mall_id  = lowercase (crawl targets, API params, filters)
  mall code          = UPPERCASE (listings document ID prefix, docs/05 §2)
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from pricebrain_app.crawler.operations_view import resolve_listing_id_for_target
from pricebrain_app.crawler.price_operations_view import PriceOperationsView
from pricebrain_app.crawler.price_ops_models import (
    HISTORY_EXISTS,
    HISTORY_NOT_FOUND,
    LISTING_NOT_FOUND,
)
from pricebrain_app.crawler.target_repository import CrawlTargetRepository
from pricebrain_app.pipeline.constants import MALL_CODE_MAP
from pricebrain_app.pipeline.runner import run_pipeline
from pricebrain_app.pipeline.utils import normalize_mall_code, normalize_mall_id
from pricebrain_app.repository.listing_repository import (
    ListingRepository,
    build_listing_document_id,
)
from pricebrain_app.repository._testing.persist_helpers import save_validated_product
from pricebrain_app.tests.fake_firestore import FakeFirestoreClient

ELEVENST_URL = "https://www.11st.co.kr/products/8083397777"
SSG_URL = "https://www.ssg.com/item/itemView.ssg?itemId=1000832367906"
CRAWLED_AT = datetime(2026, 8, 26, 10, 0, 0, tzinfo=timezone.utc)

ELEVENST_RAW = {
    "mall": "ELEVENST",
    "product_id": "8083397777",
    "product_name": "GIGABYTE 지포스 RTX 5070 GAMING OC D7 12GB",
    "price": 1_159_000,
    "seller": "공식지정점",
    "product_url": ELEVENST_URL,
}
SSG_RAW = {
    "mall": "SSG",
    "product_id": "1000832367906",
    "product_name": "HIT ZOTAC GAMING 지포스 RTX 5080 SOLID CORE OC D7 16GB",
    "price": 2_429_000,
    "seller": "히트정보",
    "product_url": SSG_URL,
}


def _ingest(db: FakeFirestoreClient, raw: dict) -> dict:
    payload = dict(raw)
    payload["crawled_at"] = CRAWLED_AT
    return dict(save_validated_product(db, dict(run_pipeline(payload))))


# --- canonical mall ID normalization -----------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("ELEVENST", "elevenst"),
        ("elevenst", "elevenst"),
        ("ElevenSt", "elevenst"),
        ("  elevenst  ", "elevenst"),
        ("11번가", "elevenst"),
        ("SSG", "ssg"),
        ("ssg", "ssg"),
        ("Ssg", "ssg"),
        ("신세계몰", "ssg"),
    ],
)
def test_normalize_mall_id_canonical_lowercase(value: str, expected: str) -> None:
    assert normalize_mall_id(value) == expected


@pytest.mark.parametrize("value", [None, "", "   "])
def test_normalize_mall_id_rejects_blank(value: str | None) -> None:
    assert normalize_mall_id(value) is None


def test_normalize_mall_id_passes_through_unknown_mall() -> None:
    """Unknown malls are lowercased rather than silently dropped."""
    assert normalize_mall_id("GMARKET") == "gmarket"
    assert normalize_mall_id("some_new_mall") == "some_new_mall"


def test_mall_id_and_mall_code_stay_in_sync() -> None:
    """Guard: the two representations must never diverge (Phase 1 drift lesson)."""
    for alias in MALL_CODE_MAP:
        code = normalize_mall_code(alias)
        assert code is not None
        assert normalize_mall_id(alias) == code.lower()


def test_listing_document_id_agrees_with_mall_code_for_canonical_values() -> None:
    """Every value that can reach the doc-ID builder must map to the mall code.

    Only canonical forms reach it: ingest passes the pipeline-normalized
    uppercase code, ops passes the lowercase crawl-target mall_id.
    """
    for code in set(MALL_CODE_MAP.values()):
        assert build_listing_document_id(code, "X") == f"{code}_X"
        assert build_listing_document_id(code.lower(), "X") == f"{code}_X"


def test_listing_document_id_does_not_resolve_display_aliases() -> None:
    """Korean aliases are resolved by the pipeline, never by the doc-ID builder."""
    assert normalize_mall_code("11번가") == "ELEVENST"
    assert build_listing_document_id("11번가", "X") != "ELEVENST_X"


# --- listing document ID is casing-insensitive on input ----------------------


@pytest.mark.parametrize(
    ("mall", "external_id", "expected"),
    [
        ("elevenst", "8083397777", "ELEVENST_8083397777"),
        ("ELEVENST", "8083397777", "ELEVENST_8083397777"),
        ("ElevenSt", "8083397777", "ELEVENST_8083397777"),
        ("  elevenst ", "8083397777", "ELEVENST_8083397777"),
        ("ssg", "1000832367906", "SSG_1000832367906"),
        ("SSG", "1000832367906", "SSG_1000832367906"),
    ],
)
def test_build_listing_document_id_normalizes_mall_casing(
    mall: str, external_id: str, expected: str
) -> None:
    assert build_listing_document_id(mall, external_id) == expected


# --- listing repository lookup ------------------------------------------------


def test_elevenst_listing_found_by_id_and_by_canonical_mall() -> None:
    db = FakeFirestoreClient()
    result = _ingest(db, ELEVENST_RAW)
    assert result["listing_id"] == "ELEVENST_8083397777"

    repo = ListingRepository(db)
    assert repo.get_by_mall_product("elevenst", "8083397777") is not None
    assert repo.get_by_mall_product("ELEVENST", "8083397777") is not None

    stored = repo.get_by_mall_product("elevenst", "8083397777")
    assert stored is not None
    assert stored["current_price"] == 1_159_000
    assert stored["product_id"] == "GIGABYTE-RTX5070-GAMINGOC-12GB"


def test_ssg_listing_found_by_canonical_mall_regression() -> None:
    db = FakeFirestoreClient()
    result = _ingest(db, SSG_RAW)
    assert result["listing_id"] == "SSG_1000832367906"

    repo = ListingRepository(db)
    assert repo.get_by_mall_product("ssg", "1000832367906") is not None
    assert repo.get_by_mall_product("SSG", "1000832367906") is not None


# --- ops target → listing resolution -----------------------------------------


@pytest.mark.parametrize(
    ("mall", "url", "expected_listing_id"),
    [
        ("elevenst", ELEVENST_URL, "ELEVENST_8083397777"),
        ("ssg", SSG_URL, "SSG_1000832367906"),
    ],
)
def test_resolve_listing_id_matches_ingested_document(
    mall: str, url: str, expected_listing_id: str
) -> None:
    db = FakeFirestoreClient()
    target = CrawlTargetRepository(db).upsert(mall_id=mall, product_url=url)
    assert resolve_listing_id_for_target(target) == expected_listing_id


# --- price operations ---------------------------------------------------------


def test_price_operations_reads_elevenst_listing() -> None:
    db = FakeFirestoreClient()
    _ingest(db, ELEVENST_RAW)
    repo = CrawlTargetRepository(db)
    target = repo.upsert(mall_id="elevenst", product_url=ELEVENST_URL)

    summary = PriceOperationsView(repo, db).get_price_summary(target.target_id)

    assert summary is not None
    assert summary.listing_id == "ELEVENST_8083397777"
    assert summary.listing_exists is True
    assert summary.current_price == 1_159_000
    assert summary.history_count >= 1
    assert summary.listing_state == HISTORY_EXISTS
    assert summary.product_id == "GIGABYTE-RTX5070-GAMINGOC-12GB"
    assert summary.mall_id == "elevenst"


def test_price_operations_reads_ssg_listing_regression() -> None:
    db = FakeFirestoreClient()
    _ingest(db, SSG_RAW)
    repo = CrawlTargetRepository(db)
    target = repo.upsert(mall_id="ssg", product_url=SSG_URL)

    summary = PriceOperationsView(repo, db).get_price_summary(target.target_id)

    assert summary is not None
    assert summary.listing_id == "SSG_1000832367906"
    assert summary.listing_exists is True
    assert summary.current_price == 2_429_000
    assert summary.listing_state == HISTORY_EXISTS


def test_price_operations_distinguishes_missing_listing_from_missing_history() -> None:
    db = FakeFirestoreClient()
    repo = CrawlTargetRepository(db)
    target = repo.upsert(mall_id="elevenst", product_url=ELEVENST_URL)
    view = PriceOperationsView(repo, db)

    missing = view.get_price_summary(target.target_id)
    assert missing is not None
    assert missing.listing_exists is False
    assert missing.listing_state == LISTING_NOT_FOUND

    ListingRepository(db).upsert_listing(
        "ELEVENST_8083397777",
        {
            "product_id": "GIGABYTE-RTX5070-GAMINGOC-12GB",
            "mall_id": "ELEVENST",
            "external_product_id": "8083397777",
            "current_price": 1_159_000,
        },
    )
    without_history = PriceOperationsView(repo, db).get_price_summary(target.target_id)
    assert without_history is not None
    assert without_history.listing_exists is True
    assert without_history.history_count == 0
    assert without_history.listing_state == HISTORY_NOT_FOUND


# --- Firestore → repository → ops view → API ----------------------------------


@pytest.mark.parametrize("mall", ["elevenst", "ssg"])
def test_operations_api_reports_price_for_ingested_listing(
    monkeypatch: pytest.MonkeyPatch, mall: str
) -> None:
    """Full read chain: Firestore → Repository → Operations View → HTTP API."""
    from fastapi.testclient import TestClient

    from pricebrain_app.api.auth.dependencies import viewer_auth_header
    from pricebrain_app.api.auth.verifier import (
        FakeTokenVerifier,
        get_token_verifier,
        reset_token_verifier,
    )
    from pricebrain_app.api.operations.dependencies import get_dashboard_operations_view
    from pricebrain_app.config.settings import clear_settings_cache
    from pricebrain_app.crawler.alert_operations_view import AlertOperationsView
    from pricebrain_app.crawler.audit_operations_view import AuditOperationsView
    from pricebrain_app.crawler.dashboard_operations_view import DashboardOperationsView
    from pricebrain_app.crawler.operations_view import CrawlerOperationsView
    from pricebrain_app.crawler.price_alert_repository import PriceAlertRepository
    from pricebrain_app.main import app
    from pricebrain_app.repository.gpu_master_seed import seed_gpu_master

    raw, url = (ELEVENST_RAW, ELEVENST_URL) if mall == "elevenst" else (SSG_RAW, SSG_URL)
    expected_price = int(raw["price"])

    db = FakeFirestoreClient()
    seed_gpu_master(db)
    _ingest(db, raw)
    target_repo = CrawlTargetRepository(db)
    target_repo.merge_catalog(
        mall_id=mall,
        product_url=url,
        product_name=str(raw["product_name"]),
        category="gpu",
    )

    alert_repo = PriceAlertRepository(db)
    price_view = PriceOperationsView(target_repo, db)
    dashboard_view = DashboardOperationsView(
        CrawlerOperationsView(target_repo, db),
        price_view,
        AlertOperationsView(alert_repo, target_repo, price_view),
        AuditOperationsView(alert_repo),
    )

    monkeypatch.setenv("PRICEBRAIN_AUTH_ENABLED", "true")
    clear_settings_cache()
    reset_token_verifier()
    app.dependency_overrides[get_token_verifier] = lambda: FakeTokenVerifier()
    app.dependency_overrides[get_dashboard_operations_view] = lambda: dashboard_view
    try:
        client = TestClient(app)
        response = client.get(
            f"/api/operations/dashboard?mall={mall}",
            headers=viewer_auth_header(),
        )
        assert response.status_code == 200
        body = response.json()

        # with_price == 1 proves the ops layer resolved the ingested listing;
        # before the casing fix this was without_price == 1.
        price = body["price"]
        assert price["read_error"] is None
        assert price["targets"] == 1
        assert price["with_price"] == 1
        assert price["without_price"] == 0

        # Canonical lowercase mall_id is what the API exposes to the frontend.
        crawler = body["crawler"]
        assert crawler["read_error"] is None
        assert list(crawler["by_mall"]) == [mall]

        # The resolved listing carries the real ingested price.
        summary = price_view.get_price_summary(f"{mall}_{raw['product_id']}")
        assert summary is not None
        assert summary.current_price == expected_price
        assert summary.listing_state == HISTORY_EXISTS
    finally:
        app.dependency_overrides.clear()
        reset_token_verifier()
        clear_settings_cache()
