"""Phase 14 — identity metadata snapshot and batch preflight persist safety."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from pricebrain_app.pipeline.runner import run_pipeline
from pricebrain_app.repository import constants as c
from pricebrain_app.repository.gpu_master_seed import seed_gpu_master
from pricebrain_app.repository.identity_snapshot import (
    build_identity_snapshot,
    variant_tokens_from_stored_product,
)
from pricebrain_app.repository.persist_service import (
    IdentityReviewBlockedError,
    PersistBoundarySession,
    PersistDecision,
    finalize_boundary_state,
    persist_validated_product,
)
from pricebrain_app.repository._testing.persist_helpers import save_validated_product
from pricebrain_app.repository.stored_product_collision import review_against_stored_product
from pricebrain_app.search_batch import (
    DEFAULT_SEARCH_LIMIT,
    SearchItemStatus,
    run_search_batch,
)
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
        "crawled_at": CRAWLED_AT,
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


def _count_paths(db: FakeFirestoreClient, prefix: str) -> int:
    return sum(1 for path in db.paths() if path.startswith(prefix))


def _count_listings(db: FakeFirestoreClient) -> int:
    marker = f"/{c.PRICE_HISTORY}/"
    return sum(
        1
        for path in db.paths()
        if path.startswith(f"{c.LISTINGS}/") and marker not in path
    )


def _count_price_history(db: FakeFirestoreClient) -> int:
    marker = f"/{c.PRICE_HISTORY}/"
    return sum(1 for path in db.paths() if marker in path)


def _persist_raw(db: FakeFirestoreClient, raw: dict) -> dict:
    validated = run_pipeline(dict(raw))
    return persist_validated_product(
        db,
        validated,
        external_product_id=str(raw["product_id"]),
        product_name=str(raw["product_name"]),
    )


def _seed_existing(db: FakeFirestoreClient, raw: dict) -> str:
    validated = run_pipeline(dict(raw))
    result = save_validated_product(db, dict(validated))
    return str(result["product_id"])


def _run_batch(db: FakeFirestoreClient, *items: dict):
    return run_search_batch(
        query="phase14",
        search_page=_source(list(items)),
        db=db,
        limit=DEFAULT_SEARCH_LIMIT,
        dry_run=False,
        sleep_func=_no_sleep,
    )


# --- Identity metadata ---


def test_phase14_identity_snapshot_saved_on_persist(db: FakeFirestoreClient) -> None:
    raw = _item("1400000001", "ZOTAC GAMING 지포스 RTX 5080 SOLID OC D7 16GB")
    result = _persist_raw(db, raw)
    doc = db.collection(c.PRODUCTS).document(result["product_id"]).get().to_dict()
    assert doc is not None
    snapshot = doc.get("identity_snapshot")
    assert isinstance(snapshot, dict)
    assert snapshot["board_partner_id"] == doc["board_partner_id"]
    assert snapshot["gpu_model_id"] == doc["gpu_model_id"]
    assert snapshot["vram_gb"] == doc["vram_gb"]
    assert snapshot["normalized_product_name"] == doc["normalized_product_name"]


def test_phase14_variant_token_snapshot_white(db: FakeFirestoreClient) -> None:
    raw = _item(
        "1400000002",
        "ZOTAC GAMING 지포스 RTX 5080 SOLID OC White D7 16GB",
    )
    validated = run_pipeline(dict(raw))
    snapshot = build_identity_snapshot(validated)
    assert "WHITE" in snapshot["variant_tokens"]

    result = _persist_raw(db, raw)
    stored = db.collection(c.PRODUCTS).document(result["product_id"]).get().to_dict()
    assert "WHITE" in stored["identity_snapshot"]["variant_tokens"]


def test_phase14_mpn_snapshot_saved(db: FakeFirestoreClient) -> None:
    raw = _item(
        "1400000003",
        "GIGABYTE 지포스 RTX 5070 GAMING OC D7 12GB",
        manufacturer_part_number="GV-N5070A",
    )
    result = _persist_raw(db, raw)
    stored = db.collection(c.PRODUCTS).document(result["product_id"]).get().to_dict()
    assert stored["identity_snapshot"]["manufacturer_part_number"] == "GV-N5070A"


def test_phase14_backward_compat_no_snapshot(db: FakeFirestoreClient) -> None:
    """Products without identity_snapshot still participate in stored review."""
    raw = _item("1400000010", "ZOTAC GAMING 지포스 RTX 5080 SOLID OC D7 16GB")
    product_id = _seed_existing(db, raw)
    ref = db.collection(c.PRODUCTS).document(product_id)
    legacy = {k: v for k, v in ref.get().to_dict().items() if k != "identity_snapshot"}
    ref.set(legacy)

    stored = ref.get().to_dict()
    assert "identity_snapshot" not in stored
    # Fallback reads variant signals from normalized_product_name when snapshot is absent.
    assert "SOLID OC" in variant_tokens_from_stored_product(stored)

    white = _item(
        "1400000011",
        "ZOTAC GAMING 지포스 RTX 5080 SOLID OC White D7 16GB",
    )
    validated = run_pipeline(dict(white))
    report = review_against_stored_product(
        db,
        validated,
        external_product_id="1400000011",
        product_name=str(white["product_name"]),
    )
    assert report is not None
    assert report.review_required is True
    assert "WHITE" in report.detected_variant_differences


# --- Batch preflight ordering ---


def test_phase14_black_white_batch_zero_writes(db: FakeFirestoreClient) -> None:
    black = _item(
        "7980057125",
        "ZOTAC GAMING 지포스 RTX 5080 SOLID OC D7 16GB",
    )
    white = _item(
        "8111912562",
        "ZOTAC GAMING 지포스 RTX 5080 SOLID OC White D7 16GB",
    )
    results, summary = _run_batch(db, black, white)
    statuses = {item.external_product_id: item.status for item in results}
    assert statuses["7980057125"] is SearchItemStatus.IDENTITY_REVIEW_BLOCKED
    assert statuses["8111912562"] is SearchItemStatus.IDENTITY_REVIEW_BLOCKED
    assert summary.identity_review_blocked == 2
    assert summary.persisted == 0
    assert _count_paths(db, f"{c.PRODUCTS}/") == 0
    assert _count_listings(db) == 0
    assert _count_price_history(db) == 0


def test_phase14_black_white_order_white_first(db: FakeFirestoreClient) -> None:
    white = _item(
        "8111912562",
        "ZOTAC GAMING 지포스 RTX 5080 SOLID OC White D7 16GB",
    )
    black = _item(
        "7980057125",
        "ZOTAC GAMING 지포스 RTX 5080 SOLID OC D7 16GB",
    )
    results, summary = _run_batch(db, white, black)
    assert summary.persisted == 0
    assert summary.identity_review_blocked == 2
    assert _count_paths(db, f"{c.PRODUCTS}/") == 0


def test_phase14_mixed_batch_isolation(db: FakeFirestoreClient) -> None:
    normal1 = _item("9100000001", "GIGABYTE 지포스 RTX 5070 GAMING OC D7 12GB")
    review_white = _item(
        "8111912562",
        "ZOTAC GAMING 지포스 RTX 5080 SOLID OC White D7 16GB",
    )
    review_black = _item(
        "7980057125",
        "ZOTAC GAMING 지포스 RTX 5080 SOLID OC D7 16GB",
    )
    unknown = _item("9100000002", "MSI 지포스 RTX 4070 벤투스 3X D6X 12GB")
    irrelevant = _item(
        "9100000003",
        "라이젠7 7800X3D RTX5070_12GB RAM_32GB SSD_1TB 조립PC",
    )
    normal2 = _item("9100000004", "MSI 지포스 RTX 5070 Ti 게이밍 트리오 OC D7 16GB")

    results, summary = _run_batch(
        db,
        normal1,
        review_white,
        review_black,
        unknown,
        irrelevant,
        normal2,
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


def test_phase14_c3_at_end_no_partial_persist(db: FakeFirestoreClient) -> None:
    normal = _item("9200000001", "GIGABYTE 지포스 RTX 5070 GAMING OC D7 12GB")
    black = _item(
        "7980057125",
        "ZOTAC GAMING 지포스 RTX 5080 SOLID OC D7 16GB",
    )
    white = _item(
        "8111912562",
        "ZOTAC GAMING 지포스 RTX 5080 SOLID OC White D7 16GB",
    )
    results, summary = _run_batch(db, normal, black, white)
    by_ext = {item.external_product_id: item.status for item in results}
    assert by_ext["9200000001"] is SearchItemStatus.PERSISTED
    assert by_ext["7980057125"] is SearchItemStatus.IDENTITY_REVIEW_BLOCKED
    assert by_ext["8111912562"] is SearchItemStatus.IDENTITY_REVIEW_BLOCKED
    assert summary.persisted == 1
    assert _count_paths(db, f"{c.PRODUCTS}/") == 1


def test_phase14_c3_at_start_no_partial_persist(db: FakeFirestoreClient) -> None:
    black = _item(
        "7980057125",
        "ZOTAC GAMING 지포스 RTX 5080 SOLID OC D7 16GB",
    )
    white = _item(
        "8111912562",
        "ZOTAC GAMING 지포스 RTX 5080 SOLID OC White D7 16GB",
    )
    normal = _item("9200000002", "GIGABYTE 지포스 RTX 5070 GAMING OC D7 12GB")
    results, summary = _run_batch(db, black, white, normal)
    by_ext = {item.external_product_id: item.status for item in results}
    assert by_ext["7980057125"] is SearchItemStatus.IDENTITY_REVIEW_BLOCKED
    assert by_ext["8111912562"] is SearchItemStatus.IDENTITY_REVIEW_BLOCKED
    assert by_ext["9200000002"] is SearchItemStatus.PERSISTED
    assert summary.persisted == 1
    assert _count_paths(db, f"{c.PRODUCTS}/") == 1


def test_phase14_multiple_collision_groups(db: FakeFirestoreClient) -> None:
    """Two independent C3 groups — neither group writes."""
    zotac_black = _item(
        "7980057125",
        "ZOTAC GAMING 지포스 RTX 5080 SOLID OC D7 16GB",
    )
    zotac_white = _item(
        "8111912562",
        "ZOTAC GAMING 지포스 RTX 5080 SOLID OC White D7 16GB",
    )
    normal = _item("9200000003", "GIGABYTE 지포스 RTX 5070 GAMING OC D7 12GB")
    results, summary = _run_batch(db, zotac_black, zotac_white, normal)
    assert summary.identity_review_blocked == 2
    assert summary.persisted == 1
    assert _count_paths(db, f"{c.PRODUCTS}/") == 1


def test_phase14_allowed_candidates_only_write(db: FakeFirestoreClient) -> None:
    session = PersistBoundarySession(db)
    allowed = _item("9300000001", "GIGABYTE 지포스 RTX 5070 GAMING OC D7 12GB")
    blocked_white = _item(
        "8111912562",
        "ZOTAC GAMING 지포스 RTX 5080 SOLID OC White D7 16GB",
    )
    blocked_black = _item(
        "7980057125",
        "ZOTAC GAMING 지포스 RTX 5080 SOLID OC D7 16GB",
    )
    for raw in (allowed, blocked_white, blocked_black):
        validated = run_pipeline(dict(raw))
        persist_validated_product(
            db,
            validated,
            external_product_id=str(raw["product_id"]),
            product_name=str(raw["product_name"]),
            boundary_session=session,
        )
    outcomes = session.finalize()
    decisions = {o.external_product_id: o.decision for o in outcomes}
    assert decisions["9300000001"] is PersistDecision.PERSISTED
    assert decisions["8111912562"] is PersistDecision.IDENTITY_REVIEW_BLOCKED
    assert decisions["7980057125"] is PersistDecision.IDENTITY_REVIEW_BLOCKED
    assert _count_paths(db, f"{c.PRODUCTS}/") == 1


# --- Cross-session ---


def test_phase14_cross_session_black_then_white_blocked(db: FakeFirestoreClient) -> None:
    _seed_existing(
        db,
        _item("1400000020", "ZOTAC GAMING 지포스 RTX 5080 SOLID OC D7 16GB"),
    )
    product_id = "ZOTAC-RTX5080-SOLIDOC-16GB"
    stored = db.collection(c.PRODUCTS).document(product_id).get().to_dict()
    assert isinstance(stored.get("identity_snapshot"), dict)

    products_before = _count_paths(db, f"{c.PRODUCTS}/")
    listings_before = _count_listings(db)
    with pytest.raises(IdentityReviewBlockedError):
        _persist_raw(
            db,
            _item(
                "1400000021",
                "ZOTAC GAMING 지포스 RTX 5080 SOLID OC White D7 16GB",
            ),
        )
    assert _count_paths(db, f"{c.PRODUCTS}/") == products_before
    assert _count_listings(db) == listings_before


def test_phase14_cross_session_same_black_reingest_allowed(db: FakeFirestoreClient) -> None:
    raw = _item("1400000030", "ZOTAC GAMING 지포스 RTX 5080 SOLID OC D7 16GB")
    _seed_existing(db, raw)
    listings_before = _count_listings(db)
    result = _persist_raw(
        db,
        _item("1400000031", "ZOTAC GAMING 지포스 RTX 5080 SOLID OC D7 16GB", seller="다른셀러"),
    )
    assert result["product_id"] == "ZOTAC-RTX5080-SOLIDOC-16GB"
    assert _count_listings(db) == listings_before + 1


def test_phase14_reingest_same_sku_different_seller(db: FakeFirestoreClient) -> None:
    raw = _item("1400000040", "GIGABYTE 지포스 RTX 5080 WINDFORCE D7 16GB")
    _seed_existing(db, raw)
    listings_before = _count_listings(db)
    result = _persist_raw(
        db,
        _item("1400000041", "GIGABYTE 지포스 RTX 5080 WINDFORCE D7 16GB", seller="B셀러"),
    )
    assert result["listing_id"]
    assert _count_listings(db) == listings_before + 1


def test_phase14_mpn_same_identity(db: FakeFirestoreClient) -> None:
    mpn = "GV-N5070A"
    first = _item(
        "1400000050",
        "GIGABYTE 지포스 RTX 5070 GAMING OC D7 12GB",
        manufacturer_part_number=mpn,
    )
    second = _item(
        "1400000051",
        "GIGABYTE 지포스 RTX 5070 GAMING OC D7 12GB",
        manufacturer_part_number=mpn,
        seller="B셀러",
    )
    pid1 = _persist_raw(db, first)["product_id"]
    pid2 = _persist_raw(db, second)["product_id"]
    assert pid1 == pid2


def test_phase14_mpn_mismatch_blocked(
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
    _seed_existing(
        db,
        _item(
            "1400000060",
            "GIGABYTE 지포스 RTX 5070 GAMING OC D7 12GB",
            manufacturer_part_number="GV-N5070A",
        ),
    )
    with pytest.raises(IdentityReviewBlockedError):
        _persist_raw(
            db,
            _item(
                "1400000061",
                "GIGABYTE 지포스 RTX 5070 GAMING OC D7 12GB",
                manufacturer_part_number="GV-N5070B",
            ),
        )


def test_phase14_board_partner_separate(db: FakeFirestoreClient) -> None:
    gigabyte = _item("1400000070", "GIGABYTE 지포스 RTX 5080 WINDFORCE D7 16GB")
    manli = _item("1400000071", "MANLI 지포스 RTX 5080 WINDFORCE D7 16GB")
    gid = _persist_raw(db, gigabyte)["product_id"]
    mid = _persist_raw(db, manli)["product_id"]
    assert gid != mid


def test_phase14_vram_mismatch_blocked(
    db: FakeFirestoreClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pricebrain_app.pipeline import product_matcher

    real_build = product_matcher.build_canonical_product_id
    shared: dict[str, str | None] = {"value": None}

    def _capture_canonical(data: dict) -> str | None:
        cid = real_build(data)
        if shared["value"] is None:
            shared["value"] = cid
        return shared["value"]

    monkeypatch.setattr(
        product_matcher,
        "build_canonical_product_id",
        _capture_canonical,
    )
    first = _item("1400000080", "GIGABYTE 지포스 RTX 5070 GAMING OC D7 12GB")
    _seed_existing(db, first)
    product_id = shared["value"]
    assert product_id is not None
    db.collection(c.PRODUCTS).document(product_id).set(
        {**db.collection(c.PRODUCTS).document(product_id).get().to_dict(), "vram_gb": 16},
        merge=True,
    )
    second = _item("1400000081", "GIGABYTE 지포스 RTX 5070 GAMING OC D7 12GB")
    validated = run_pipeline(dict(second))
    validated["vram_gb"] = 12
    with pytest.raises(IdentityReviewBlockedError) as excinfo:
        persist_validated_product(
            db,
            validated,
            external_product_id="1400000081",
            product_name=str(second["product_name"]),
        )
    assert "vram_mismatch" in (excinfo.value.review_reason or "")


# --- Mutations M22–M25 ---


def test_phase14_m22_preflight_removal_partial_persist(
    db: FakeFirestoreClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sequential inline write without two-phase preflight allows partial persist when batch gate is bypassed."""
    from pricebrain_app.repository import persist_service as ps
    from pricebrain_app.repository.service import _write_validated_product
    from pricebrain_app.repository.stored_product_collision import (
        review_against_stored_product as real_stored_review,
    )

    monkeypatch.setattr(
        ps,
        "blocked_canonical_ids_from_state",
        lambda _state: set(),
    )

    def _inline_finalize(state, *, db, dry_run):
        outcomes = []
        for item in state.deferred:
            canonical_id = str(item.validated.get("canonical_product_id") or "")
            stored_report = real_stored_review(
                db,
                item.validated,
                external_product_id=item.external_product_id,
                product_name=item.product_name,
            )
            if stored_report is not None and stored_report.review_required:
                outcomes.append(
                    ps.PersistOutcome(
                        external_product_id=item.external_product_id,
                        product_name=item.product_name,
                        canonical_product_id=canonical_id or None,
                        decision=ps.PersistDecision.IDENTITY_REVIEW_BLOCKED,
                        review_required=True,
                    )
                )
                continue
            if dry_run:
                outcomes.append(
                    ps.PersistOutcome(
                        external_product_id=item.external_product_id,
                        product_name=item.product_name,
                        canonical_product_id=canonical_id or None,
                        decision=ps.PersistDecision.PERSIST_CANDIDATE,
                    )
                )
                continue
            try:
                save_result = _write_validated_product(db, item.validated)
            except Exception:
                outcomes.append(
                    ps.PersistOutcome(
                        external_product_id=item.external_product_id,
                        product_name=item.product_name,
                        canonical_product_id=canonical_id or None,
                        decision=ps.PersistDecision.IDENTITY_REVIEW_BLOCKED,
                        review_required=True,
                    )
                )
                continue
            outcomes.append(
                ps.PersistOutcome(
                    external_product_id=item.external_product_id,
                    product_name=item.product_name,
                    canonical_product_id=canonical_id or None,
                    decision=ps.PersistDecision.PERSISTED,
                    save_result=save_result,
                )
            )
        return outcomes

    monkeypatch.setattr(ps, "finalize_boundary_state", _inline_finalize)

    black = _item(
        "7980057125",
        "ZOTAC GAMING 지포스 RTX 5080 SOLID OC D7 16GB",
    )
    white = _item(
        "8111912562",
        "ZOTAC GAMING 지포스 RTX 5080 SOLID OC White D7 16GB",
    )
    session = PersistBoundarySession(db)
    for raw in (black, white):
        validated = run_pipeline(dict(raw))
        persist_validated_product(
            db,
            validated,
            external_product_id=str(raw["product_id"]),
            product_name=str(raw["product_name"]),
            boundary_session=session,
        )
    outcomes = session.finalize()
    persisted = [o for o in outcomes if o.decision is PersistDecision.PERSISTED]
    blocked = [o for o in outcomes if o.decision is PersistDecision.IDENTITY_REVIEW_BLOCKED]
    assert len(persisted) == 1
    assert len(blocked) == 1
    assert _count_paths(db, f"{c.PRODUCTS}/") == 1


def test_phase14_m23_stored_metadata_comparison_removal(
    db: FakeFirestoreClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pricebrain_app.pipeline.collision_review import (
        CollisionClass,
        CollisionGroupReport,
    )

    monkeypatch.setattr(
        "pricebrain_app.repository.stored_product_collision.differing_variant_tokens",
        lambda _l, _r: (),
    )
    monkeypatch.setattr(
        "pricebrain_app.repository.stored_product_collision.classify_collision_group",
        lambda **_kwargs: CollisionGroupReport(
            canonical_product_id="ZOTAC-RTX5080-SOLIDOC-16GB",
            member_count=2,
            external_product_ids=("stored", "candidate"),
            titles=("t1", "t2"),
            detected_variant_differences=(),
            collision_class=CollisionClass.C2_NORMAL_LISTING,
            review_required=False,
        ),
    )
    _seed_existing(
        db,
        _item("1400000090", "ZOTAC GAMING 지포스 RTX 5080 SOLID OC D7 16GB"),
    )
    result = _persist_raw(
        db,
        _item("1400000091", "ZOTAC GAMING 지포스 RTX 5080 SOLID OC White D7 16GB"),
    )
    assert result["listing_id"]
    assert _count_listings(db) == 2


def test_phase14_m24_identity_snapshot_save_guard(db: FakeFirestoreClient) -> None:
    """Regression guard — persisted products must carry identity_snapshot."""
    raw = _item("1400000095", "GIGABYTE 지포스 RTX 5070 GAMING OC D7 12GB")
    result = _persist_raw(db, raw)
    stored = db.collection(c.PRODUCTS).document(result["product_id"]).get().to_dict()
    assert "identity_snapshot" in stored
    assert stored["identity_snapshot"]["variant_tokens"] is not None


def test_phase14_m25_early_persist_before_preflight(
    db: FakeFirestoreClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import pricebrain_app.search_batch as search_batch_module
    from pricebrain_app.repository import persist_service as ps
    from pricebrain_app.repository.service import _write_validated_product

    original_finalize = ps.finalize_boundary_state

    def _persist_before_preflight(state, *, db, dry_run):
        if not dry_run:
            for item in state.deferred:
                try:
                    _write_validated_product(db, item.validated)
                except Exception:
                    continue
        return original_finalize(state, db=db, dry_run=dry_run)

    monkeypatch.setattr(ps, "finalize_boundary_state", _persist_before_preflight)
    monkeypatch.setattr(
        search_batch_module,
        "finalize_boundary_state",
        _persist_before_preflight,
    )

    black = _item(
        "7980057125",
        "ZOTAC GAMING 지포스 RTX 5080 SOLID OC D7 16GB",
    )
    white = _item(
        "8111912562",
        "ZOTAC GAMING 지포스 RTX 5080 SOLID OC White D7 16GB",
    )
    results, summary = _run_batch(db, black, white)
    assert summary.identity_review_blocked == 2
    assert _count_paths(db, f"{c.PRODUCTS}/") >= 1
