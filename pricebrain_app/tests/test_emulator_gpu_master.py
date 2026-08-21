"""Firestore Emulator — GPU Master seed (Gate C-3)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from pricebrain_app.firebase.admin import get_firestore_client
from pricebrain_app.pipeline.runner import run_pipeline
from pricebrain_app.repository import constants as c
from pricebrain_app.repository.gpu_master_seed import seed_gpu_master
from pricebrain_app.repository.service import save_validated_product
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
