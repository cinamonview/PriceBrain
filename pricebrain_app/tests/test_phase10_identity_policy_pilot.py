"""Phase 10 — identity policy implementation pilot tests."""

from __future__ import annotations

import json
import pathlib
from collections import defaultdict
from datetime import datetime, timezone

import pytest

from pricebrain_app.crawler.parser.elevenst import parse_elevenst_product_detail_html
from pricebrain_app.crawler.parser.elevenst_mpn import extract_elevenst_detail_mpn
from pricebrain_app.crawler.parser.elevenst_search import parse_elevenst_search_json
from pricebrain_app.pipeline.cleaner import clean
from pricebrain_app.pipeline.collision_review import (
    CollisionClass,
    classify_collision_group,
    review_canonical_collisions,
)
from pricebrain_app.pipeline.gpu_parser import parse_gpu
from pricebrain_app.pipeline.identity_variants import extract_variant_token
from pricebrain_app.pipeline.normalizer import normalize
from pricebrain_app.pipeline.product_classifier import ProductType, classify_product_type
from pricebrain_app.pipeline.product_matcher import build_canonical_product_id, match_product
from pricebrain_app.pipeline.runner import run_pipeline
from pricebrain_app.repository.gpu_master_seed import seed_gpu_master
from pricebrain_app.search_batch import DEFAULT_SEARCH_LIMIT, SearchItemResult, SearchItemStatus
from pricebrain_app.search_observation import (
    PHASE7_BOUNDED_QUERIES,
    fixture_map_for_queries,
    observe_collision_review,
    observe_identity,
    run_multi_query_observation,
)
from pricebrain_app.tests.fake_firestore import FakeFirestoreClient

FIXTURES = pathlib.Path(__file__).parent / "fixtures" / "elevenst"
PHASE4_SAMPLE = pathlib.Path("_phase4_sample")
CRAWLED_AT = datetime(2026, 8, 26, 12, 0, 0, tzinfo=timezone.utc)
DETAIL_URL = "https://www.11st.co.kr/products/8083397777"


@pytest.fixture
def db() -> FakeFirestoreClient:
    client = FakeFirestoreClient()
    seed_gpu_master(client)
    return client


def _read_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _load_phase4(filename: str) -> list[dict]:
    path = PHASE4_SAMPLE / filename
    if not path.exists():
        pytest.skip(f"missing phase4 sample: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    return parse_elevenst_search_json(payload, crawled_at=CRAWLED_AT)


def test_phase10_mpn_extracts_from_detail_fixture() -> None:
    from bs4 import BeautifulSoup

    html = _read_fixture("product_detail_gpu.html")
    soup = BeautifulSoup(html, "html.parser")
    assert extract_elevenst_detail_mpn(soup) == "GV-N5070A"

    raw = parse_elevenst_product_detail_html(html, product_url=DETAIL_URL)
    assert raw is not None
    assert raw.get("manufacturer_part_number") == "GV-N5070A"


def test_phase10_mpn_missing_on_empty_html() -> None:
    from bs4 import BeautifulSoup

    assert extract_elevenst_detail_mpn(BeautifulSoup("<html></html>", "html.parser")) is None


def test_phase10_mpn_negative_does_not_extract_title_or_seller() -> None:
    from bs4 import BeautifulSoup

    html = """
    <html><body>
      <title>GIGABYTE RTX 5070 GAMING OC D7 12GB 피씨디렉트</title>
      <div class="store_name">공식지정점_클릭</div>
      <table><tr><th>상품번호</th><td>8083397777</td></tr></table>
    </body></html>
    """
    assert extract_elevenst_detail_mpn(BeautifulSoup(html, "html.parser")) is None


def test_phase10_mpn_priority_over_title_variant() -> None:
    validated = run_pipeline(
        {
            "mall": "ELEVENST",
            "product_id": "8083397777",
            "product_name": "GIGABYTE 지포스 RTX 5070 GAMING OC D7 12GB",
            "price": 1_159_000,
            "seller": "공식지정점_클릭",
            "product_url": DETAIL_URL,
            "crawled_at": CRAWLED_AT,
            "manufacturer_part_number": "GV-N5070A",
        }
    )
    assert validated["canonical_product_id"] == "GVN5070A"


def test_phase10_zotac_solid_oc_and_solid_core_are_distinct() -> None:
    solid_oc = build_canonical_product_id(
        {
            "brand": "ZOTAC",
            "gpu_model": "RTX 5080",
            "vram_gb": 16,
            "normalized_product_name": "ZOTAC GAMING RTX 5080 SOLID OC D7 16GB",
        }
    )
    solid_core = build_canonical_product_id(
        {
            "brand": "ZOTAC",
            "gpu_model": "RTX 5080",
            "vram_gb": 16,
            "normalized_product_name": "ZOTAC GAMING RTX 5080 SOLID CORE OC D7 16GB",
        }
    )
    assert solid_oc == "ZOTAC-RTX5080-SOLIDOC-16GB"
    assert solid_core == "ZOTAC-RTX5080-SOLIDCORE-16GB"
    assert solid_oc != solid_core


def test_phase10_gigabyte_aorus_and_ice_tokens_are_manufacturer_specific() -> None:
    assert extract_variant_token(brand="GIGABYTE", normalized_name="GIGABYTE AORUS RTX 5080 MASTER") == "MASTER"
    assert (
        extract_variant_token(
            brand="GIGABYTE",
            normalized_name="GIGABYTE RX 9070 XT GAMING OC ICE 16GB",
        )
        == "GAMINGOCICE"
    )
    assert extract_variant_token(brand="ASUS", normalized_name="ASUS AORUS RTX 5080") is None


def test_phase10_collision_guard_flags_zotac_white_review() -> None:
    members = [
        SearchItemResult(
            status=SearchItemStatus.PERSIST_CANDIDATE,
            mall_id="elevenst",
            query="RTX 5080",
            page=1,
            rank=0,
            external_product_id="8111912562",
            product_name="ZOTAC GAMING RTX 5080 SOLID OC White D7 16GB",
            board_partner_id="ZOTAC",
            gpu_model_id="rtx_5080",
            canonical_product_id="ZOTAC-RTX5080-SOLIDOC-16GB",
        ),
        SearchItemResult(
            status=SearchItemStatus.PERSIST_CANDIDATE,
            mall_id="elevenst",
            query="지포스 RTX",
            page=1,
            rank=1,
            external_product_id="7980057125",
            product_name="ZOTAC GAMING RTX 5080 SOLID OC D7 16GB",
            board_partner_id="ZOTAC",
            gpu_model_id="rtx_5080",
            canonical_product_id="ZOTAC-RTX5080-SOLIDOC-16GB",
        ),
    ]
    report = classify_collision_group(
        canonical_product_id="ZOTAC-RTX5080-SOLIDOC-16GB",
        members=members,
    )
    assert report is not None
    assert report.collision_class is CollisionClass.C3_VARIANT_COLLISION
    assert report.review_required is True
    assert "WHITE" in report.detected_variant_differences


def test_phase10_collision_guard_windforce_same_line_is_c2() -> None:
    title = "GIGABYTE RTX 5080 WINDFORCE OC SFF D7 16GB"
    members = [
        SearchItemResult(
            status=SearchItemStatus.PERSIST_CANDIDATE,
            mall_id="elevenst",
            query="RTX 5080",
            page=1,
            rank=0,
            external_product_id="8086083839",
            product_name=f"{title} 피씨디렉트",
            board_partner_id="GIGABYTE",
            gpu_model_id="rtx_5080",
            canonical_product_id="GIGABYTE-RTX5080-WINDFORCE-16GB",
        ),
        SearchItemResult(
            status=SearchItemStatus.PERSIST_CANDIDATE,
            mall_id="elevenst",
            query="RTX 5080",
            page=1,
            rank=1,
            external_product_id="8155550375",
            product_name=f"{title} 제이씨현",
            board_partner_id="GIGABYTE",
            gpu_model_id="rtx_5080",
            canonical_product_id="GIGABYTE-RTX5080-WINDFORCE-16GB",
        ),
    ]
    report = classify_collision_group(
        canonical_product_id="GIGABYTE-RTX5080-WINDFORCE-16GB",
        members=members,
    )
    assert report is not None
    assert report.collision_class is CollisionClass.C2_NORMAL_LISTING
    assert report.review_required is False


def test_phase10_m8_mpn_extraction_removal_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    from bs4 import BeautifulSoup

    monkeypatch.setattr(
        "pricebrain_app.crawler.parser.elevenst.extract_elevenst_detail_mpn",
        lambda _soup: None,
    )
    html = _read_fixture("product_detail_gpu.html")
    raw = parse_elevenst_product_detail_html(html, product_url=DETAIL_URL)
    assert raw is not None
    assert raw.get("manufacturer_part_number") is None


def test_phase10_m9_manufacturer_specific_restriction_removal_detected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "pricebrain_app.pipeline.product_matcher.extract_variant_token",
        lambda *, brand, normalized_name: "SOLIDOC" if "SOLID OC" in normalized_name.upper() else None,
    )
    asus = build_canonical_product_id(
        {
            "brand": "ASUS",
            "gpu_model": "RTX 5080",
            "vram_gb": 16,
            "normalized_product_name": "ASUS RTX 5080 SOLID OC D7 16GB",
        }
    )
    assert asus == "ASUS-RTX5080-SOLIDOC-16GB"


def test_phase10_m10_collision_guard_removal_allows_silent_c3(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    members = [
        SearchItemResult(
            status=SearchItemStatus.PERSIST_CANDIDATE,
            mall_id="elevenst",
            query="RTX 5080",
            page=1,
            rank=0,
            external_product_id="8111912562",
            product_name="ZOTAC GAMING RTX 5080 SOLID OC White D7 16GB",
            board_partner_id="ZOTAC",
            gpu_model_id="rtx_5080",
            canonical_product_id="ZOTAC-RTX5080-SOLIDOC-16GB",
        ),
        SearchItemResult(
            status=SearchItemStatus.PERSIST_CANDIDATE,
            mall_id="elevenst",
            query="지포스 RTX",
            page=1,
            rank=1,
            external_product_id="7980057125",
            product_name="ZOTAC GAMING RTX 5080 SOLID OC D7 16GB",
            board_partner_id="ZOTAC",
            gpu_model_id="rtx_5080",
            canonical_product_id="ZOTAC-RTX5080-SOLIDOC-16GB",
        ),
    ]

    def _broken_review(_members, *, mpn_by_external=None):
        return tuple()

    monkeypatch.setattr(
        "pricebrain_app.search_observation.review_canonical_collisions",
        _broken_review,
    )
    review = observe_collision_review(members)
    assert review.review_required_count == 0

    baseline = review_canonical_collisions(members)
    assert any(group.review_required for group in baseline)


@pytest.mark.skipif(not PHASE4_SAMPLE.exists(), reason="phase4 sample not present")
def test_phase10_bounded_sample_collision_before_after(db: FakeFirestoreClient) -> None:
    fixture_files = {
        "RTX 4070": "p4_RTX_4070_p1.json",
        "RTX 5070": "p4_RTX_5070_p1.json",
        "RTX 5080": "p4_RTX_5080_p1.json",
        "RX 9070": "p4_RX_9070_p1.json",
        "그래픽카드": "p4_그래픽카드_p1.json",
        "지포스 RTX": "p4_지포스_RTX_p1.json",
    }
    fixtures = {
        query: _load_phase4(filename)[:DEFAULT_SEARCH_LIMIT]
        for query, filename in fixture_files.items()
    }
    report = run_multi_query_observation(
        queries=PHASE7_BOUNDED_QUERIES,
        search_page_for_query=fixture_map_for_queries(fixtures),
        db=db,
        limit=DEFAULT_SEARCH_LIMIT,
        pages=1,
        dry_run=True,
    )
    items = [item for obs in report.queries for item in obs.results]
    identity = observe_identity(items)

    assert identity.unique_external_ids > 0
    assert identity.canonical_id_collisions > 0
    assert report.collision_review.c4_count == 0
    assert report.collision_review.review_required_count >= 1

    by_canonical: dict[str, list] = defaultdict(list)
    for item in items:
        if item.canonical_product_id and item.external_product_id:
            by_canonical[item.canonical_product_id].append(item)
    assert len(by_canonical) >= identity.unique_canonical_product_ids


def test_phase10_full_sample_gpu_collision_metrics() -> None:
    if not PHASE4_SAMPLE.exists():
        pytest.skip("phase4 sample not present")

    seen: set[str] = set()
    gpu_rows = []
    for path in PHASE4_SAMPLE.glob("*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        for raw in parse_elevenst_search_json(payload, crawled_at=CRAWLED_AT):
            ext = str(raw["product_id"])
            if ext in seen:
                continue
            seen.add(ext)
            cleaned = clean(dict(raw))
            if classify_product_type(raw_name=str(cleaned.get("product_name") or "")) is not ProductType.GPU_PRODUCT:
                continue
            matched = match_product(parse_gpu(normalize(cleaned)))
            if matched.get("canonical_product_id"):
                gpu_rows.append(matched)

    by = defaultdict(list)
    for row in gpu_rows:
        by[row["canonical_product_id"]].append(row)
    collision_groups = {key: value for key, value in by.items() if len(value) > 1}
    assert len(gpu_rows) >= 300
    assert len(collision_groups) > 0
    assert len(by) >= identity_baseline_unique_canonical()


def identity_baseline_unique_canonical() -> int:
    """Phase 9 baseline unique canonical count on the same sample (141)."""
    return 141
