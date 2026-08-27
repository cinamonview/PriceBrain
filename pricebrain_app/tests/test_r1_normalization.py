"""R1 design gate — alias, bracket, and product-type classification."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from pricebrain_app.pipeline.board_partners import canonical_board_partner
from pricebrain_app.pipeline.cleaner import clean
from pricebrain_app.pipeline.constants import (
    GPU_BOARD_PARTNER_ALIASES,
    GPU_BOARD_PARTNERS,
)
from pricebrain_app.pipeline.exceptions import GpuProductFilteredError, PipelineValidationError
from pricebrain_app.pipeline.gpu_parser import parse_gpu
from pricebrain_app.pipeline.normalizer import normalize
from pricebrain_app.pipeline.product_classifier import (
    ProductType,
    classify_product,
    classify_product_type,
)
from pricebrain_app.pipeline.product_matcher import match_product
from pricebrain_app.pipeline.runner import run_pipeline
from pricebrain_app.pipeline.validator import validate
from pricebrain_app.repository import constants as c
from pricebrain_app.repository.exceptions import UnknownGpuModelError
from pricebrain_app.repository.gpu_master_seed import BOARD_PARTNERS, seed_gpu_master
from pricebrain_app.repository.operational_service import quarantine_unknown_gpu_model
from pricebrain_app.repository._testing.persist_helpers import save_validated_product
from pricebrain_app.tests.fake_firestore import FakeFirestoreClient

CRAWLED_AT = datetime(2026, 8, 26, 12, 0, 0, tzinfo=timezone.utc)


def _raw(product_name: str, *, product_id: str = "8083397777") -> dict:
    return {
        "mall": "ELEVENST",
        "product_id": product_id,
        "product_name": product_name,
        "price": 1_259_000,
        "seller": "테스트셀러",
        "product_url": f"https://www.11st.co.kr/products/{product_id}",
        "crawled_at": CRAWLED_AT,
    }


def _parsed(product_name: str) -> dict:
    return parse_gpu(normalize(clean(_raw(product_name))))


# --- alias policy -----------------------------------------------------------


def test_alias_targets_are_canonical_master_partners() -> None:
    seeded = {str(partner["slug"]) for partner in BOARD_PARTNERS}
    missing_canonical = sorted(set(GPU_BOARD_PARTNERS) - seeded)
    missing_alias = sorted(set(GPU_BOARD_PARTNER_ALIASES.values()) - set(GPU_BOARD_PARTNERS))
    assert missing_canonical == []
    assert missing_alias == []


@pytest.mark.parametrize(
    ("alias", "canonical"),
    [
        ("기가바이트", "GIGABYTE"),
        ("사파이어", "SAPPHIRE"),
        ("조텍", "ZOTAC"),
        ("게인워드", "GAINWARD"),
        ("에이수스", "ASUS"),
        ("갤럭시", "GALAX"),
        ("팔릿", "PALIT"),
        ("컬러풀", "COLORFUL"),
        ("이노쓰리디", "INNO3D"),
        ("애즈락", "ASROCK"),
        ("엠에스아이", "MSI"),
        ("ROG", "ASUS"),
        ("GIGABYTE", "GIGABYTE"),
        ("ZOTAC", "ZOTAC"),
    ],
)
def test_korean_and_english_aliases_resolve_to_canonical(alias: str, canonical: str) -> None:
    assert canonical_board_partner(alias) == canonical


def test_galax_does_not_match_galaxy_book_token() -> None:
    assert canonical_board_partner("Samsung Galaxy Book") is None


def test_unlisted_korean_partner_is_not_invented() -> None:
    assert canonical_board_partner("이엠텍") is None
    assert canonical_board_partner("EMTEK") is None
    assert canonical_board_partner("MANLI") == "MANLI"
    assert canonical_board_partner("만리") == "MANLI"


def test_korean_partner_title_extracts_canonical_brand() -> None:
    data = _parsed("기가바이트 지포스 RTX 5070 AERO OC D7 12GB 제이씨현")
    assert data["brand"] == "GIGABYTE"
    assert data["board_partner_id"] == "GIGABYTE"
    assert data["gpu_model_id"] == "rtx_5070"


# --- brackets ---------------------------------------------------------------


def test_known_partner_bracket_is_preserved_as_canonical_token() -> None:
    data = normalize(clean(_raw("[INNO3D] 지포스 RTX 5070 OC D7 12GB X3 그래픽카드")))
    assert data["normalized_product_name"].startswith("INNO3D")
    parsed = parse_gpu(data)
    assert parsed["board_partner_id"] == "INNO3D"


def test_korean_partner_bracket_is_unwrapped() -> None:
    data = normalize(clean(_raw("[기가바이트] 지포스 RTX 5070 GAMING OC D7 12GB")))
    assert data["normalized_product_name"].startswith("GIGABYTE")
    assert parse_gpu(data)["board_partner_id"] == "GIGABYTE"


def test_marketing_bracket_is_still_stripped() -> None:
    data = normalize(clean(_raw("[특가] ZOTAC GAMING 지포스 RTX 5080 SOLID CORE OC D7 16GB!!!")))
    assert "특가" not in data["normalized_product_name"]
    assert data["normalized_product_name"].startswith("ZOTAC")
    assert parse_gpu(data)["board_partner_id"] == "ZOTAC"


def test_shipping_bracket_is_still_stripped() -> None:
    for prefix in ("[무료배송]", "[해외배송]"):
        data = normalize(clean(_raw(f"{prefix} MSI 지포스 RTX 5070 벤투스 2X OC D7 12GB")))
        assert "무료" not in data["normalized_product_name"]
        assert "해외" not in data["normalized_product_name"]
        assert data["normalized_product_name"].startswith("MSI")


def test_marketing_then_partner_brackets_preserve_partner() -> None:
    data = normalize(clean(_raw("[특가][INNO3D] 지포스 RTX 5070 OC D7 12GB")))
    assert "특가" not in data["normalized_product_name"]
    assert parse_gpu(data)["board_partner_id"] == "INNO3D"


# --- product type -----------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("GIGABYTE 지포스 RTX 5070 GAMING OC D7 12GB", ProductType.GPU_PRODUCT),
        ("MSI RTX 4070 Ventus 2X 쿨링팬 교체용 95mm", ProductType.GPU_ACCESSORY),
        ("그래픽카드 알루미늄 방열판 과열방지 부품", ProductType.GPU_ACCESSORY),
        ("ASUS ROG STRIX RTX 4070 SUPER Bykski GPU 워터블록", ProductType.GPU_ACCESSORY),
        ("RTX4070TI 12+4핀전원 커넥터 8핀 3개변환 슬리브케이블", ProductType.GPU_ACCESSORY),
        ("라이젠7 7800X3D RTX5070_12GB RAM_32GB 조립PC 게이밍 컴퓨터", ProductType.PREBUILT_PC),
        ("레노버 Legion 5 15AHP11 R7 (Ryzen 7 / RTX5070) 게이밍 노트북", ProductType.LAPTOP),
        ("일반 키보드", ProductType.UNKNOWN),
        ("일반 USB 케이블 1m", ProductType.GPU_ACCESSORY),
    ],
)
def test_product_type_keyword_rules(name: str, expected: ProductType) -> None:
    assert classify_product_type(raw_name=name) is expected


def test_dual_fan_gpu_sku_is_not_an_accessory() -> None:
    name = "PALIT 지포스 RTX 5070 INFINITY 3 D7 12GB Dual Fan"
    assert classify_product_type(raw_name=name) is ProductType.GPU_PRODUCT


def test_filtered_types_never_reach_gpu_master_resolution() -> None:
    for name in (
        "MSI RTX 4070 Ventus 2X 쿨링팬 교체용 95mm",
        "라이젠7 7800X3D RTX5070 12GB 조립PC",
        "삼성 갤럭시북6 울트라 RTX5070 게이밍노트북",
    ):
        with pytest.raises(GpuProductFilteredError) as excinfo:
            run_pipeline(_raw(name))
        assert excinfo.value.field in {"GPU_ACCESSORY", "PREBUILT_PC", "LAPTOP"}


def test_accessory_is_not_persisted_via_vram_relaxation() -> None:
    """VRAM remains required for GPU_PRODUCT; accessories never get that far."""
    with pytest.raises(GpuProductFilteredError, match="GPU_ACCESSORY"):
        run_pipeline(_raw("GIGABYTE 지포스 RTX4070 WINDFORCE OC 그래픽 카드 교체 팬"))


def test_actual_gpu_without_vram_still_fails_validation() -> None:
    data = match_product(
        parse_gpu(
            classify_product(
                normalize(clean(_raw("GIGABYTE 지포스 RTX 5070 GAMING OC")))
            )
        )
    )
    with pytest.raises(PipelineValidationError, match="incomplete"):
        validate(data)


def test_known_gpu_product_still_persists() -> None:
    validated = run_pipeline(_raw("GIGABYTE 지포스 RTX 5070 GAMING OC D7 12GB"))
    assert validated["gpu_model_id"] == "rtx_5070"
    assert validated["board_partner_id"] == "GIGABYTE"


def test_korean_partner_plus_unknown_model_quarantines() -> None:
    db = FakeFirestoreClient()
    seed_gpu_master(db)
    raw = _raw("기가바이트 지포스 RTX 4070 GAMING OC D6X 12GB", product_id="4070000001")
    validated = dict(run_pipeline(raw))
    with pytest.raises(UnknownGpuModelError) as excinfo:
        save_validated_product(db, validated)
    assert excinfo.value.gpu_model_id == "rtx_4070"
    quarantine_unknown_gpu_model(db, excinfo.value, validated_data=validated)

    pending = db.get_document(f"{c.PENDING_GPU_MODELS}/rtx_4070")
    assert pending is not None
    assert pending["status"] == "PENDING_REVIEW"
    assert db.get_document(f"{c.GPU_MODELS}/rtx_4070") is None
    assert db.get_document(f"{c.LISTINGS}/ELEVENST_4070000001") is None


def test_emtek_alias_is_not_written_into_board_partner_master() -> None:
    db = FakeFirestoreClient()
    seed_gpu_master(db)
    before = {path for path in db.paths() if path.startswith(f"{c.BOARD_PARTNERS}/")}
    with pytest.raises(PipelineValidationError):
        run_pipeline(_raw("이엠텍 지포스 RTX 5070 MIRACLE WHITE D7 12GB"))
    after = {path for path in db.paths() if path.startswith(f"{c.BOARD_PARTNERS}/")}
    assert before == after
    assert f"{c.BOARD_PARTNERS}/EMTEK" not in after
