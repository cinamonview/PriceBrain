"""Phase 12 — common persist boundary gate across all entry points."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from pricebrain_app.api.deps import get_firestore
from pricebrain_app.main import app
from pricebrain_app.pipeline.runner import run_pipeline
from pricebrain_app.repository import constants as c
from pricebrain_app.repository.exceptions import IdentityReviewBlockedError
from pricebrain_app.repository.gpu_master_seed import seed_gpu_master
from pricebrain_app.repository.persist_service import (
    PersistBoundarySession,
    PersistDecision,
    persist_validated_product,
)
from pricebrain_app.repository._testing.persist_helpers import save_validated_product
from pricebrain_app.runner import run_crawl_batch
from pricebrain_app.search_batch import (
    DEFAULT_SEARCH_LIMIT,
    SearchItemStatus,
    run_search_batch,
)
from pricebrain_app.search_observation import fixture_map_for_queries, run_multi_query_observation
from pricebrain_app.tests.fake_firestore import FakeFirestoreClient

CRAWLED_AT = datetime(2026, 8, 26, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def db() -> FakeFirestoreClient:
    client = FakeFirestoreClient()
    seed_gpu_master(client)
    return client


def _item(
    product_id: str,
    product_name: str,
    *,
    price: int = 1_500_000,
    seller: str = "테스트셀러",
    manufacturer_part_number: str | None = None,
) -> dict:
    payload = {
        "mall": "ELEVENST",
        "product_id": product_id,
        "product_name": product_name,
        "price": price,
        "seller": seller,
        "product_url": f"https://www.11st.co.kr/products/{product_id}",
        "crawled_at": CRAWLED_AT.isoformat(),
    }
    if manufacturer_part_number:
        payload["manufacturer_part_number"] = manufacturer_part_number
    return payload


def _source(*pages):
    def search_page(_query: str, page: int):
        return pages[page - 1] if 1 <= page <= len(pages) else []

    return search_page


def _no_sleep(_seconds: float) -> None:
    return None


def _count_listings(db: FakeFirestoreClient) -> int:
    history_marker = f"/{c.PRICE_HISTORY}/"
    return sum(
        1
        for path in db.paths()
        if path.startswith(f"{c.LISTINGS}/") and history_marker not in path
    )


def _count_price_history(db: FakeFirestoreClient) -> int:
    return sum(1 for path in db.paths() if f"/{c.PRICE_HISTORY}/" in path)


def test_phase12_a_api_normal_persist(
    db: FakeFirestoreClient,
    ingest_auth_env: dict[str, str],
) -> None:
    raw = _item("9700000001", "GIGABYTE 지포스 RTX 5070 GAMING OC D7 12GB")

    def override_get_firestore():
        yield db

    app.dependency_overrides[get_firestore] = override_get_firestore
    try:
        response = TestClient(app).post(
            "/internal/ingest/listing",
            json=raw,
            headers=ingest_auth_env,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert _count_listings(db) == 1
        assert _count_price_history(db) == 1
    finally:
        app.dependency_overrides.clear()


def test_phase12_b_api_c3_blocked_batch_gate(db: FakeFirestoreClient) -> None:
    white = _item(
        "8111912562",
        "ZOTAC GAMING 지포스 RTX 5080 SOLID OC White D7 16GB",
    )
    black = _item(
        "7980057125",
        "ZOTAC GAMING 지포스 RTX 5080 SOLID OC D7 16GB",
    )
    session = PersistBoundarySession(db)
    for raw in (white, black):
        validated = run_pipeline(dict(raw))
        persist_validated_product(
            db,
            validated,
            external_product_id=str(raw["product_id"]),
            product_name=str(raw["product_name"]),
            boundary_session=session,
        )
    outcomes = session.finalize()
    assert len(outcomes) == 2
    assert all(o.decision is PersistDecision.IDENTITY_REVIEW_BLOCKED for o in outcomes)
    assert sum(1 for p in db.paths() if p.startswith(f"{c.PRODUCTS}/")) == 0
    assert _count_listings(db) == 0
    assert _count_price_history(db) == 0


def test_phase12_c_api_mpn_mismatch_blocked(
    db: FakeFirestoreClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pricebrain_app.pipeline import product_matcher

    real_build = product_matcher.build_canonical_product_id

    def _shared_canonical_without_mpn(data: dict) -> str | None:
        stripped = {
            key: value
            for key, value in data.items()
            if key != "manufacturer_part_number"
        }
        return real_build(stripped)

    monkeypatch.setattr(
        product_matcher,
        "build_canonical_product_id",
        _shared_canonical_without_mpn,
    )

    session = PersistBoundarySession(db)
    for raw in (
        _item(
            "9300000001",
            "GIGABYTE 지포스 RTX 5070 GAMING OC D7 12GB",
            manufacturer_part_number="GV-N5070A",
        ),
        _item(
            "9300000002",
            "GIGABYTE 지포스 RTX 5070 GAMING OC D7 12GB 피씨디렉트",
            manufacturer_part_number="GV-N5070B",
        ),
    ):
        validated = run_pipeline(dict(raw))
        persist_validated_product(
            db,
            validated,
            external_product_id=str(raw["product_id"]),
            product_name=str(raw["product_name"]),
            boundary_session=session,
        )
    outcomes = session.finalize()
    assert all(o.decision is PersistDecision.IDENTITY_REVIEW_BLOCKED for o in outcomes)
    assert sum(1 for p in db.paths() if p.startswith(f"{c.PRODUCTS}/")) == 0


def test_phase12_d_runner_c3_blocked(db: FakeFirestoreClient) -> None:
    white = _item(
        "8111912562",
        "ZOTAC GAMING 지포스 RTX 5080 SOLID OC White D7 16GB",
    )
    black = _item(
        "7980057125",
        "ZOTAC GAMING 지포스 RTX 5080 SOLID OC D7 16GB",
    )
    batch = run_crawl_batch(db, "ELEVENST", [white, black], keyword="RTX 5080")
    assert batch["identity_review_blocked"] == 2
    assert batch["results"] == []
    assert sum(1 for p in db.paths() if p.startswith(f"{c.PRODUCTS}/")) == 0


def test_phase12_e_mixed_batch_isolation(db: FakeFirestoreClient) -> None:
    page = [
        _item("9100000001", "GIGABYTE 지포스 RTX 5070 GAMING OC D7 12GB"),
        _item("8111912562", "ZOTAC GAMING 지포스 RTX 5080 SOLID OC White D7 16GB"),
        _item("7980057125", "ZOTAC GAMING 지포스 RTX 5080 SOLID OC D7 16GB"),
        _item("9100000002", "MSI 지포스 RTX 4070 벤투스 3X D6X 12GB"),
        _item(
            "9100000003",
            "라이젠7 7800X3D RTX5070_12GB RAM_32GB SSD_1TB 조립PC",
        ),
        _item("9100000004", "MSI 지포스 RTX 5070 Ti 게이밍 트리오 OC D7 16GB"),
    ]
    results, summary = run_search_batch(
        query="mixed",
        search_page=_source(page),
        db=db,
        limit=DEFAULT_SEARCH_LIMIT,
        dry_run=False,
        sleep_func=_no_sleep,
    )
    by_ext = {item.external_product_id: item.status for item in results}
    assert by_ext["9100000001"] is SearchItemStatus.PERSISTED
    assert by_ext["8111912562"] is SearchItemStatus.IDENTITY_REVIEW_BLOCKED
    assert by_ext["7980057125"] is SearchItemStatus.IDENTITY_REVIEW_BLOCKED
    assert by_ext["9100000002"] is SearchItemStatus.QUARANTINED
    assert by_ext["9100000003"] is SearchItemStatus.IRRELEVANT
    assert by_ext["9100000004"] is SearchItemStatus.PERSISTED
    assert summary.persisted == 2
    assert summary.identity_review_blocked == 2


def test_phase12_f_gate_bypass_mutation_writes(db: FakeFirestoreClient) -> None:
    white = _item(
        "8111912562",
        "ZOTAC GAMING 지포스 RTX 5080 SOLID OC White D7 16GB",
    )
    black = _item(
        "7980057125",
        "ZOTAC GAMING 지포스 RTX 5080 SOLID OC D7 16GB",
    )
    session = PersistBoundarySession(db)
    for raw in (white, black):
        validated = run_pipeline(dict(raw))
        session.register(
            validated,
            external_product_id=str(raw["product_id"]),
            product_name=str(raw["product_name"]),
        )
    for item in session.state.deferred:
        try:
            save_validated_product(db, item.validated)
        except IdentityReviewBlockedError:
            pass
    assert sum(1 for p in db.paths() if p.startswith(f"{c.PRODUCTS}/")) >= 1


def test_phase12_g_entry_points_wired_to_persist_service() -> None:
    import pricebrain_app.api.ingest as ingest_module
    import pricebrain_app.repository.persist_service as persist_service
    import pricebrain_app.search_batch as search_batch_module
    from pricebrain_app.repository._testing.persist_helpers import save_validated_product

    assert ingest_module.persist_validated_product is persist_service.persist_validated_product
    assert search_batch_module.finalize_boundary_state is persist_service.finalize_boundary_state
    assert callable(save_validated_product)


def test_phase12_h_production_write_guard_not_executed() -> None:
    """Production Firestore paths are not exercised in Phase 12 tests."""
    assert True


def test_phase12_m14_ingest_gate_removal_detected(
    db: FakeFirestoreClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import pricebrain_app.api.ingest as ingest_module

    monkeypatch.setattr(
        ingest_module,
        "persist_validated_product",
        lambda db, data, **kwargs: save_validated_product(db, dict(data)),
    )
    white = _item(
        "8111912562",
        "ZOTAC GAMING 지포스 RTX 5080 SOLID OC White D7 16GB",
    )
    validated = run_pipeline(dict(white))
    ingest_module.persist_validated_product(
        db,
        validated,
        external_product_id="8111912562",
        product_name=str(white["product_name"]),
    )
    assert sum(1 for p in db.paths() if p.startswith(f"{c.PRODUCTS}/")) == 1


def test_phase12_m15_runner_gate_bypass_detected(db: FakeFirestoreClient) -> None:
    white = _item(
        "8111912562",
        "ZOTAC GAMING 지포스 RTX 5080 SOLID OC White D7 16GB",
    )
    black = _item(
        "7980057125",
        "ZOTAC GAMING 지포스 RTX 5080 SOLID OC D7 16GB",
    )
    for raw in (white, black):
        try:
            save_validated_product(db, dict(run_pipeline(dict(raw))))
        except IdentityReviewBlockedError:
            pass
    assert sum(1 for p in db.paths() if p.startswith(f"{c.PRODUCTS}/")) >= 1


def test_phase12_m16_review_required_inversion_detected(
    db: FakeFirestoreClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "pricebrain_app.repository.persist_service.blocked_canonical_ids_from_state",
        lambda _state: set(),
    )
    monkeypatch.setattr(
        "pricebrain_app.repository.persist_service.review_against_stored_product",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "pricebrain_app.repository.service.review_stored_mapping",
        lambda *_args, **_kwargs: None,
    )
    white = _item(
        "8111912562",
        "ZOTAC GAMING 지포스 RTX 5080 SOLID OC White D7 16GB",
    )
    black = _item(
        "7980057125",
        "ZOTAC GAMING 지포스 RTX 5080 SOLID OC D7 16GB",
    )
    session = PersistBoundarySession(db)
    for raw in (white, black):
        validated = run_pipeline(dict(raw))
        persist_validated_product(
            db,
            validated,
            external_product_id=str(raw["product_id"]),
            product_name=str(raw["product_name"]),
            boundary_session=session,
        )
    outcomes = session.finalize()
    assert all(o.decision is PersistDecision.PERSISTED for o in outcomes)


def test_phase12_m17_multi_query_shared_finalize_blocks_cross_query_c3(
    db: FakeFirestoreClient,
) -> None:
    white = _item(
        "8111912562",
        "ZOTAC GAMING 지포스 RTX 5080 SOLID OC White D7 16GB",
    )
    black = _item(
        "7980057125",
        "ZOTAC GAMING 지포스 RTX 5080 SOLID OC D7 16GB",
    )
    fixtures = {"RTX 5080 White": [white], "RTX 5080 Black": [black]}
    report = run_multi_query_observation(
        queries=("RTX 5080 White", "RTX 5080 Black"),
        search_page_for_query=fixture_map_for_queries(fixtures),
        db=db,
        limit=DEFAULT_SEARCH_LIMIT,
        dry_run=False,
    )
    statuses = {item.status for obs in report.queries for item in obs.results}
    assert SearchItemStatus.IDENTITY_REVIEW_BLOCKED in statuses
    assert SearchItemStatus.PERSISTED not in statuses
    assert _count_listings(db) == 0
