"""GPU Master seed and reference resolve tests — Gate C-3."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from pricebrain_app.pipeline.runner import run_pipeline
from pricebrain_app.repository import constants as c
from pricebrain_app.repository.exceptions import RepositoryValidationError
from pricebrain_app.repository.gpu_master_seed import (
    BOARD_PARTNERS,
    GPU_FAMILIES,
    GPU_MODELS,
    GPU_VENDORS,
    seed_gpu_master,
)
from pricebrain_app.repository.gpu_repository import GpuRepository
from pricebrain_app.repository.reference_repository import ReferenceRepository
from pricebrain_app.repository.service import save_validated_product
from pricebrain_app.tests.fake_firestore import FakeFirestoreClient


def _master_path_count(db: FakeFirestoreClient) -> int:
    prefixes = (
        c.GPU_VENDORS,
        c.GPU_FAMILIES,
        c.GPU_MODELS,
        c.BOARD_PARTNERS,
    )
    return sum(
        1
        for path in db.paths()
        if any(path.startswith(f"{prefix}/") for prefix in prefixes)
    )


def test_c3_01_gpu_vendor_seed(fake_db: FakeFirestoreClient) -> None:
    vendor = fake_db.get_document(f"{c.GPU_VENDORS}/NVIDIA")
    assert vendor is not None
    assert vendor["code"] == "NVIDIA"
    assert vendor["name"] == "NVIDIA"
    assert vendor["active"] is True


def test_c3_02_gpu_family_seed(fake_db: FakeFirestoreClient) -> None:
    family = fake_db.get_document(f"{c.GPU_FAMILIES}/GEFORCE_RTX")
    assert family is not None
    assert family["vendor_id"] == "NVIDIA"
    assert family["active"] is True


def test_c3_03_gpu_model_seed(fake_db: FakeFirestoreClient) -> None:
    model = fake_db.get_document(f"{c.GPU_MODELS}/rtx_5080")
    assert model is not None
    assert model["gpu_series"] == "RTX"
    assert model["gpu_model"] == "RTX 5080"
    assert model["vendor_id"] == "NVIDIA"
    assert model["family_id"] == "GEFORCE_RTX"
    assert model["vram_gb"] == 16


def test_c3_04_board_partner_seed(fake_db: FakeFirestoreClient) -> None:
    partner = fake_db.get_document(f"{c.BOARD_PARTNERS}/ZOTAC")
    assert partner is not None
    assert partner["slug"] == "ZOTAC"
    assert partner["display_name"] == "ZOTAC"


def test_c3_05_seed_idempotent() -> None:
    db = FakeFirestoreClient()
    seed_gpu_master(db)
    first_count = _master_path_count(db)
    assert first_count == len(GPU_VENDORS) + len(GPU_FAMILIES) + len(GPU_MODELS) + len(
        BOARD_PARTNERS
    )
    seed_gpu_master(db)
    assert _master_path_count(db) == first_count


def test_c3_06_reference_repository_resolves_master(
    fake_db: FakeFirestoreClient, validated_product: dict
) -> None:
    repo = ReferenceRepository(fake_db)
    repo.resolve_all(validated_product)
    assert GpuRepository(fake_db).get_model("rtx_5080") is not None
    assert GpuRepository(fake_db).get_partner("ZOTAC") is not None


def test_c3_07_missing_gpu_model_raises(validated_product: dict) -> None:
    db = FakeFirestoreClient()
    seed_gpu_master(db)
    validated = dict(validated_product)
    validated["gpu_model_id"] = "missing_model"
    repo = ReferenceRepository(db)
    with pytest.raises(RepositoryValidationError, match="gpu_model_id"):
        repo.resolve_all(validated)


def test_c3_07_missing_board_partner_raises(validated_product: dict) -> None:
    db = FakeFirestoreClient()
    seed_gpu_master(db)
    validated = dict(validated_product)
    validated["board_partner_id"] = "UNKNOWN_PARTNER"
    repo = ReferenceRepository(db)
    with pytest.raises(RepositoryValidationError, match="board_partner_id"):
        repo.resolve_all(validated)


@pytest.fixture
def validated_product() -> dict:
    raw = {
        "mall": "SSG",
        "product_id": "1000832367906",
        "product_name": "HIT ZOTAC GAMING 지포스 RTX 5080 SOLID CORE OC D7 16GB",
        "price": 2429000,
        "seller": "히트정보",
        "product_url": "https://www.ssg.com/item/itemView.ssg?itemId=1000832367906",
        "crawled_at": datetime(2026, 8, 19, 10, 0, 0, tzinfo=timezone.utc),
    }
    return dict(run_pipeline(raw))


def test_c3_08_save_bootstraps_missing_gpu_master(validated_product: dict) -> None:
    db = FakeFirestoreClient()
    assert GpuRepository(db).get_partner("ZOTAC") is None

    result = save_validated_product(db, validated_product)

    assert GpuRepository(db).get_partner("ZOTAC") is not None
    product = db.get_document(f"{c.PRODUCTS}/{result['product_id']}")
    assert product is not None
    assert product["board_partner_id"] == "ZOTAC"


def test_c3_09_user_ingest_payload_bootstraps_zotac_master() -> None:
    raw = {
        "product_id": "test-rtx5080-001",
        "product_name": "ZOTAC GAMING GeForce RTX 5080 16GB",
        "mall_id": "ssg",
        "product_url": "https://example.com/products/test-rtx5080",
        "price": 1599000,
        "seller": "PriceBrain Test",
    }
    validated = run_pipeline(raw)
    assert validated["board_partner_id"] == "ZOTAC"

    db = FakeFirestoreClient()
    result = save_validated_product(db, dict(validated))
    assert result["listing_id"] == "SSG_test-rtx5080-001"
    assert db.get_document(f"{c.BOARD_PARTNERS}/ZOTAC") is not None


def test_c3_10_save_validated_product_uses_master_references(
    fake_db: FakeFirestoreClient, validated_product: dict
) -> None:
    result = save_validated_product(fake_db, validated_product)
    product = fake_db.get_document(f"{c.PRODUCTS}/{result['product_id']}")
    assert product is not None
    assert product["gpu_model_id"] == "rtx_5080"
    assert product["board_partner_id"] == "ZOTAC"
    model = fake_db.get_document(f"{c.GPU_MODELS}/rtx_5080")
    assert model is not None
    assert model["family_id"] == "GEFORCE_RTX"
