"""Firestore Emulator — GPU Master seed (Gate C-3)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from pricebrain_app.firebase.admin import get_firestore_client
from pricebrain_app.pipeline.runner import run_pipeline
from pricebrain_app.repository import constants as c
from pricebrain_app.repository.gpu_master_seed import seed_gpu_master
from pricebrain_app.repository._testing.persist_helpers import save_validated_product
from pricebrain_app.tests.emulator_utils import emulator_env, requires_emulator


@requires_emulator
def test_c3_08_emulator_gpu_master_seed() -> None:
    with emulator_env():
        db = get_firestore_client()
        seed_gpu_master(db)
        assert db.collection(c.GPU_VENDORS).document("NVIDIA").get().exists
        assert db.collection(c.GPU_FAMILIES).document("GEFORCE_RTX").get().exists
        assert db.collection(c.GPU_MODELS).document("rtx_5080").get().exists
        assert db.collection(c.BOARD_PARTNERS).document("ZOTAC").get().exists
        assert db.collection(c.BOARD_PARTNERS).document("GIGABYTE").get().exists
        assert db.collection(c.GPU_MODELS).document("rtx_5070").get().exists


@requires_emulator
def test_c3_09_emulator_pipeline_master_resolve() -> None:
    with emulator_env():
        db = get_firestore_client()
        validated = run_pipeline(
            {
                "mall": "SSG",
                "product_id": f"em{uuid.uuid4().hex[:10]}",
                "product_name": "HIT ZOTAC GAMING 지포스 RTX 5080 SOLID CORE OC D7 16GB",
                "price": 100000,
                "seller": "히트정보",
                "product_url": "https://www.ssg.com/item/itemView.ssg?itemId=123",
                "crawled_at": datetime(2026, 8, 19, 10, 0, 0, tzinfo=timezone.utc),
            }
        )
        assert validated["gpu_model_id"] == "rtx_5080"
        assert validated["board_partner_id"] == "ZOTAC"


@requires_emulator
def test_c3_10_emulator_save_validated_product_master_links() -> None:
    with emulator_env():
        db = get_firestore_client()
        product_id = f"em{uuid.uuid4().hex[:10]}"
        validated = dict(
            run_pipeline(
                {
                    "mall": "SSG",
                    "product_id": product_id,
                    "product_name": "HIT ZOTAC GAMING 지포스 RTX 5080 SOLID CORE OC D7 16GB",
                    "price": 100000,
                    "seller": "히트정보",
                    "product_url": f"https://www.ssg.com/item/itemView.ssg?itemId={product_id}",
                    "crawled_at": datetime(2026, 8, 19, 10, 0, 0, tzinfo=timezone.utc),
                }
            )
        )
        result = save_validated_product(db, validated)
        product_doc = db.collection(c.PRODUCTS).document(str(result["product_id"])).get()
        product_data = product_doc.to_dict()
        assert product_data is not None
        assert product_data["gpu_model_id"] == "rtx_5080"
        assert product_data["board_partner_id"] == "ZOTAC"
        model_doc = db.collection(c.GPU_MODELS).document("rtx_5080").get()
        assert model_doc.exists
        assert model_doc.to_dict()["vendor_id"] == "NVIDIA"


@requires_emulator
def test_tier1_emulator_elevenst_gigabyte_rtx5070_ingest() -> None:
    from pathlib import Path

    from pricebrain_app.crawler.adapters.elevenst import ElevenstProductParser

    fixture = (
        Path(__file__).parent / "fixtures" / "elevenst" / "product_detail_gpu.html"
    )
    url = "https://www.11st.co.kr/products/8083397777"
    with emulator_env():
        db = get_firestore_client()
        payload = ElevenstProductParser().parse(
            fixture.read_text(encoding="utf-8"), url=url
        )
        validated = dict(run_pipeline(payload.to_dict()))
        assert validated["board_partner_id"] == "GIGABYTE"
        assert validated["gpu_model_id"] == "rtx_5070"
        result = save_validated_product(db, validated)
        product_doc = db.collection(c.PRODUCTS).document(str(result["product_id"])).get()
        product_data = product_doc.to_dict()
        assert product_data is not None
        assert product_data["board_partner_id"] == "GIGABYTE"
        assert product_data["gpu_model_id"] == "rtx_5070"
        assert result["listing_id"] == "ELEVENST_8083397777"


@requires_emulator
def test_phase2_emulator_ops_resolves_elevenst_listing() -> None:
    """Firestore → Repository → Operations View on the Emulator (V2 Phase 2)."""
    from pathlib import Path

    from pricebrain_app.crawler.adapters.elevenst import ElevenstProductParser
    from pricebrain_app.crawler.price_operations_view import PriceOperationsView
    from pricebrain_app.crawler.price_ops_models import HISTORY_EXISTS
    from pricebrain_app.crawler.target_repository import CrawlTargetRepository

    url = "https://www.11st.co.kr/products/8083397777"
    fixture = (
        Path(__file__).parent / "fixtures" / "elevenst" / "product_detail_gpu.html"
    )
    with emulator_env():
        db = get_firestore_client()
        payload = ElevenstProductParser().parse(
            fixture.read_text(encoding="utf-8"), url=url
        )
        result = save_validated_product(db, dict(run_pipeline(payload.to_dict())))
        assert result["listing_id"] == "ELEVENST_8083397777"

        target_repo = CrawlTargetRepository(db)
        target, _action = target_repo.merge_catalog(
            mall_id="elevenst",
            product_url=url,
            product_name="GIGABYTE RTX 5070 GAMING OC",
            category="gpu",
        )
        summary = PriceOperationsView(target_repo, db).get_price_summary(
            target.target_id
        )

        assert summary is not None
        assert summary.mall_id == "elevenst"
        assert summary.listing_id == "ELEVENST_8083397777"
        assert summary.listing_exists is True
        assert summary.current_price == 1_159_000
        assert summary.history_count >= 1
        assert summary.listing_state == HISTORY_EXISTS
        assert summary.product_id == "GIGABYTE-RTX5070-GAMINGOC-12GB"
