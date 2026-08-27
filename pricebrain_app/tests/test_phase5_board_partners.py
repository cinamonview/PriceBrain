"""Phase 5 — MANLI/POWERCOLOR master extension and brandEngNm enrichment."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from pricebrain_app.crawler.parser.elevenst_search import parse_elevenst_search_json
from pricebrain_app.pipeline.board_partners import (
    board_partner_from_brand_eng_nm,
    canonical_board_partner,
)
from pricebrain_app.pipeline.cleaner import clean
from pricebrain_app.pipeline.constants import GPU_BOARD_PARTNERS
from pricebrain_app.pipeline.exceptions import GpuProductFilteredError, PipelineValidationError
from pricebrain_app.pipeline.gpu_parser import parse_gpu
from pricebrain_app.pipeline.normalizer import normalize
from pricebrain_app.pipeline.product_classifier import ProductType, classify_product_type
from pricebrain_app.pipeline.runner import run_pipeline
from pricebrain_app.repository import constants as c
from pricebrain_app.repository.gpu_master_seed import BOARD_PARTNERS, seed_gpu_master
from pricebrain_app.repository.reference_repository import ReferenceRepository
from pricebrain_app.repository._testing.persist_helpers import save_validated_product
from pricebrain_app.tests.fake_firestore import FakeFirestoreClient

CRAWLED_AT = datetime(2026, 8, 26, 12, 0, 0, tzinfo=timezone.utc)


def _raw(
    product_name: str,
    *,
    product_id: str = "8083397777",
    brand_eng_nm: str | None = None,
) -> dict:
    data = {
        "mall": "ELEVENST",
        "product_id": product_id,
        "product_name": product_name,
        "price": 1_259_000,
        "seller": "테스트셀러",
        "product_url": f"https://www.11st.co.kr/products/{product_id}",
        "crawled_at": CRAWLED_AT,
    }
    if brand_eng_nm is not None:
        data["brand_eng_nm"] = brand_eng_nm
    return data


def _parsed(product_name: str, **kwargs: object) -> dict:
    return parse_gpu(normalize(clean(_raw(product_name, **kwargs))))


# --- MANLI ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("token", "expected"),
    [
        ("MANLI", "MANLI"),
        ("MANLi", "MANLI"),
        ("만리", "MANLI"),
    ],
)
def test_manli_aliases_resolve_to_canonical(token: str, expected: str) -> None:
    assert canonical_board_partner(token) == expected


def test_manli_title_extracts_canonical_partner() -> None:
    data = _parsed("MANLI 지포스 RTX 5070 Polar Fox OC V2 D7 12GB")
    assert data["board_partner_id"] == "MANLI"
    assert data["gpu_model_id"] == "rtx_5070"


def test_manli_resolves_against_master(fake_db: FakeFirestoreClient) -> None:
    ReferenceRepository(fake_db).resolve_board_partner("MANLI")


def test_manli_gpu_product_persists(fake_db: FakeFirestoreClient) -> None:
    validated = run_pipeline(
        _raw("MANLI 지포스 RTX 5070 Nebula D7 12GB Dual Fan", product_id="8623286999")
    )
    assert validated["board_partner_id"] == "MANLI"
    result = save_validated_product(fake_db, dict(validated))
    product = fake_db.get_document(f"{c.PRODUCTS}/{result['product_id']}")
    assert product is not None
    assert product["board_partner_id"] == "MANLI"


# --- POWERCOLOR -------------------------------------------------------------


@pytest.mark.parametrize(
    ("token", "expected"),
    [
        ("PowerColor", "POWERCOLOR"),
        ("파워컬러", "POWERCOLOR"),
        ("파워칼라", "POWERCOLOR"),
        ("POWERCOLOR", "POWERCOLOR"),
    ],
)
def test_powercolor_aliases_resolve_to_canonical(token: str, expected: str) -> None:
    assert canonical_board_partner(token) == expected


def test_powercolor_title_extracts_canonical_partner() -> None:
    data = _parsed("파워컬러 헬하운드 AMD 라데온 RX 9070 XT 16GB GDDR6")
    assert data["board_partner_id"] == "POWERCOLOR"
    assert data["gpu_model_id"] == "rx_9070_xt"


def test_powercolor_resolves_against_master(fake_db: FakeFirestoreClient) -> None:
    ReferenceRepository(fake_db).resolve_board_partner("POWERCOLOR")


def test_powercolor_accessory_stays_filtered() -> None:
    name = "PowerColor RX 9070 XT Hellhound용 G 워터블록 Copper Waterblock"
    assert classify_product_type(raw_name=name) is ProductType.GPU_ACCESSORY
    with pytest.raises(GpuProductFilteredError, match="GPU_ACCESSORY"):
        run_pipeline(_raw(name))


# --- EMTEK (deferred) -------------------------------------------------------


def test_emtek_is_not_a_canonical_partner_alias() -> None:
    assert canonical_board_partner("이엠텍") is None
    assert canonical_board_partner("EMTEK") is None


def test_palit_emtek_suffix_keeps_palit() -> None:
    data = _parsed("PALIT 지포스 RTX 5070 INFINITY 3 D7 12GB 이엠텍")
    assert data["board_partner_id"] == "PALIT"


def test_emtek_own_sku_does_not_auto_persist(fake_db: FakeFirestoreClient) -> None:
    before = {path for path in fake_db.paths() if path.startswith(f"{c.BOARD_PARTNERS}/")}
    with pytest.raises(PipelineValidationError):
        run_pipeline(_raw("이엠텍 지포스 RTX 5070 MIRACLE WHITE D7 12GB"))
    after = {path for path in fake_db.paths() if path.startswith(f"{c.BOARD_PARTNERS}/")}
    assert before == after
    assert f"{c.BOARD_PARTNERS}/EMTEK" not in after


def test_emtek_brand_eng_nm_msi_is_not_trusted() -> None:
    data = _parsed(
        "이엠텍 지포스 RTX 5070 MIRACLE WHITE D7 12GB",
        brand_eng_nm="MSI",
    )
    assert "board_partner_id" not in data or data.get("board_partner_id") != "MSI"


# --- brandEngNm enrichment ----------------------------------------------------


def test_brand_eng_nm_recovers_known_partner_when_title_lacks_one() -> None:
    title = "기편안한 컨디션이트 GeForce RTX 4070 Ti Super Eagle OC 16GB WINDFORCE"
    data = _parsed(title, brand_eng_nm="기가바이트")
    assert data["board_partner_id"] == "GIGABYTE"


def test_brand_eng_nm_seller_brand_is_ignored() -> None:
    assert board_partner_from_brand_eng_nm("FORYOUCOM", title="RTX 5070 12GB") is None


def test_brand_eng_nm_nvidia_is_not_board_partner() -> None:
    assert board_partner_from_brand_eng_nm("NVIDIA", title="RTX 5080 16GB") is None
    assert board_partner_from_brand_eng_nm("엔비디아", title="RTX 5080 16GB") is None


def test_brand_eng_nm_unlisted_partner_is_not_invented() -> None:
    assert board_partner_from_brand_eng_nm("YESTON", title="RX 9070 XT 16GB") is None


def test_brand_eng_nm_does_not_override_title_partner() -> None:
    data = _parsed(
        "ZOTAC GAMING 지포스 RTX 5080 SOLID CORE OC D7 16GB",
        brand_eng_nm="기가바이트",
    )
    assert data["board_partner_id"] == "ZOTAC"


def test_elevenst_search_passes_brand_eng_nm() -> None:
    payload = {
        "data": [
            {
                "items": [
                    {
                        "id": 999,
                        "title": "RTX 5070 12G SHADOW 3X OC",
                        "finalPrc": 1000000,
                        "brandEngNm": "기가바이트",
                    }
                ]
            }
        ]
    }
    (item,) = parse_elevenst_search_json(payload)
    assert item.get("brand_eng_nm") == "기가바이트"


# --- master alignment -------------------------------------------------------


def test_manli_and_powercolor_are_seeded() -> None:
    slugs = {str(partner["slug"]) for partner in BOARD_PARTNERS}
    assert {"MANLI", "POWERCOLOR"} <= slugs
    assert {"MANLI", "POWERCOLOR"} <= set(GPU_BOARD_PARTNERS)


# --- classification regression ----------------------------------------------


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("MANLI 지포스 RTX 5070 Nebula D7 12GB Dual Fan", ProductType.GPU_PRODUCT),
        ("PowerColor RX 9070 XT Hellhound용 G 워터블록 Copper Waterblock", ProductType.GPU_ACCESSORY),
        ("라이젠7 7800X3D RTX5070_12GB RAM_32GB SSD_1TB 조립PC", ProductType.PREBUILT_PC),
        ("레노버 Legion 5 15AHP11 R7 RTX5070 게이밍 노트북", ProductType.LAPTOP),
        ("MANLI 지포스 RTX 5070 Nebula D7 12GB Dual Fan", ProductType.GPU_PRODUCT),
    ],
)
def test_product_classification_regression(name: str, expected: ProductType) -> None:
    assert classify_product_type(raw_name=name) is expected


def test_dual_fan_manli_sku_is_gpu_product() -> None:
    name = "MANLI 지포스 RTX 5070 Nebula D7 12GB Dual Fan"
    assert classify_product_type(raw_name=name) is ProductType.GPU_PRODUCT
