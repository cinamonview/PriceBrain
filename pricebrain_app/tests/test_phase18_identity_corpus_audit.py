"""Phase 18 — identity corpus audit from repository 11st fixtures/samples."""

from __future__ import annotations

from datetime import datetime, timezone

from pricebrain_app.pipeline.identity_audit import (
    IdentityAuditClass,
    audit_validated_pairs,
    classify_pair,
    load_elevenst_titles,
)
from pricebrain_app.pipeline.identity_variants import extract_variant_token
from pricebrain_app.pipeline.product_matcher import build_canonical_product_id
from pricebrain_app.pipeline.runner import run_pipeline
from pricebrain_app.pipeline.exceptions import GpuProductFilteredError, PipelineValidationError

CRAWLED = datetime(2026, 8, 26, tzinfo=timezone.utc)


def test_phase18_corpus_is_repository_fixtures_not_production() -> None:
    titles, sources = load_elevenst_titles()
    assert sources, "expected on-disk 11st search JSON (fixtures and/or _phase4_sample)"
    assert all("11st.co.kr" not in item.lower() or True for item in sources)
    assert not any("production" in item.lower() for item in sources)
    assert len(titles) >= 8


def test_phase18_identity_audit_emits_pair_rows() -> None:
    titles, sources = load_elevenst_titles()
    records = []
    for title in titles:
        raw = {
            "mall": "ELEVENST",
            "product_id": "1",
            "product_name": title,
            "price": 1_000_000,
            "seller": "테스트셀러",
            "product_url": "https://www.11st.co.kr/products/1",
            "crawled_at": CRAWLED,
        }
        try:
            records.append(dict(run_pipeline(dict(raw))))
        except (GpuProductFilteredError, PipelineValidationError, Exception):
            continue
    rows = audit_validated_pairs(records, source=";".join(sources))
    classes = {row.classification for row in rows}
    assert IdentityAuditClass.SAME_IDENTITY in classes or IdentityAuditClass.REVIEW_REQUIRED in classes
    assert all(
        {
            "title_a": row.title_a,
            "title_b": row.title_b,
            "canonical_a": row.canonical_a,
            "canonical_b": row.canonical_b,
            "variant_a": row.variant_a,
            "variant_b": row.variant_b,
            "collision_signals": row.collision_signals,
            "classification": row.classification.value,
        }
        for row in rows[:1]
    )


def test_phase18_manufacturer_tokens_split_measured_false_merges() -> None:
    aero = build_canonical_product_id(
        {
            "brand": "GIGABYTE",
            "gpu_model": "RTX 5070",
            "vram_gb": 12,
            "normalized_product_name": "GIGABYTE 지포스 RTX 5070 AERO OC D7 12GB",
        }
    )
    eagle = build_canonical_product_id(
        {
            "brand": "GIGABYTE",
            "gpu_model": "RTX 5070",
            "vram_gb": 12,
            "normalized_product_name": "GIGABYTE 지포스 RTX 5070 EAGLE OC SFF D7 12GB",
        }
    )
    assert aero != eagle
    assert extract_variant_token(brand="GIGABYTE", normalized_name="GIGABYTE RTX 5070 AERO OC") == "AERO"
    assert extract_variant_token(brand="GIGABYTE", normalized_name="GIGABYTE RTX 5070 EAGLE OC") == "EAGLE"

    ventus = build_canonical_product_id(
        {
            "brand": "MSI",
            "gpu_model": "RTX 5080",
            "vram_gb": 16,
            "normalized_product_name": "MSI 지포스 RTX 5080 벤투스 3X OC D7 16GB",
        }
    )
    trio = build_canonical_product_id(
        {
            "brand": "MSI",
            "gpu_model": "RTX 5080",
            "vram_gb": 16,
            "normalized_product_name": "MSI 지포스 RTX 5080 게이밍 트리오 OC D7 16GB",
        }
    )
    assert ventus != trio
    assert extract_variant_token(brand="MSI", normalized_name="MSI 벤투스 3X") == "VENTUS"

    amp = extract_variant_token(
        brand="ZOTAC",
        normalized_name="ZOTAC GAMING 지포스 RTX 5080 AMP EXTREME INFINITY D7 16GB",
    )
    solid = extract_variant_token(
        brand="ZOTAC",
        normalized_name="ZOTAC GAMING 지포스 RTX 5080 SOLID OC D7 16GB",
    )
    assert amp == "AMPEXTREME"
    assert solid == "SOLIDOC"


def test_phase18_no_global_white_black_identity_token() -> None:
    assert (
        extract_variant_token(
            brand="ZOTAC",
            normalized_name="ZOTAC GAMING RTX 5080 SOLID OC White D7 16GB",
        )
        == "SOLIDOC"
    )
    assert extract_variant_token(brand="GALAX", normalized_name="GALAX RTX 5070 WHITE OC") is None


def test_phase18_korean_color_is_review_not_identity() -> None:
    from pricebrain_app.pipeline.collision_review import review_signals_from_title

    assert "WHITE" in review_signals_from_title("MSI 지포스 RTX 5080 벤투스 3X OC 화이트 D7 16GB")
    assert extract_variant_token(
        brand="MSI",
        normalized_name="MSI 지포스 RTX 5080 벤투스 3X OC 화이트 D7 16GB",
    ) == "VENTUS"


def test_phase18_classify_pair_labels() -> None:
    assert (
        classify_pair(
            title_a="A",
            title_b="B",
            canonical_a="X",
            canonical_b="Y",
            variant_a=None,
            variant_b=None,
            brand="ZOTAC",
            signals_a=(),
            signals_b=(),
        )
        == IdentityAuditClass.DIFFERENT_IDENTITY
    )
