"""Reference document resolve — docs/09 §6.2, docs/05 §3."""

from __future__ import annotations

from typing import Any

from google.cloud.firestore_v1 import SERVER_TIMESTAMP

from pricebrain_app.repository import constants as c
from pricebrain_app.repository.base import BaseRepository
from pricebrain_app.repository.exceptions import (
    RepositoryValidationError,
    UnknownGpuModelError,
)
from pricebrain_app.repository.gpu_repository import GpuRepository


class ReferenceRepository(BaseRepository):
    """Resolve mall/seller/GPU references against Firestore master data."""

    def ensure_mall(self, mall_id: str) -> None:
        ref = self.db.collection(c.MALLS).document(mall_id)
        if ref.get().exists:
            return
        ref.set(
            {
                "code": mall_id,
                "name": mall_id,
                "display_name": mall_id,
                "active": True,
                "created_at": SERVER_TIMESTAMP,
            }
        )

    def ensure_seller(
        self,
        *,
        seller_id: str,
        mall_id: str,
        seller_name: str,
        normalized_seller_name: str | None = None,
    ) -> str:
        ref = self.db.collection(c.SELLERS).document(seller_id)
        if ref.get().exists:
            return seller_id
        ref.set(
            {
                "slug": seller_id,
                "seller_name": seller_name,
                "normalized_seller_name": normalized_seller_name or seller_name,
                "mall_id": mall_id,
                "active": True,
                "created_at": SERVER_TIMESTAMP,
            }
        )
        return seller_id

    def resolve_board_partner(self, board_partner_id: str) -> None:
        gpu_repo = GpuRepository(self.db)
        partner = gpu_repo.get_partner(board_partner_id)
        if partner is None:
            raise RepositoryValidationError(
                f"board_partner_id not found in GPU master: {board_partner_id}",
                field="board_partner_id",
            )

    def resolve_gpu_model(self, gpu_model_id: str) -> None:
        gpu_repo = GpuRepository(self.db)
        model = gpu_repo.get_model(gpu_model_id)
        if model is None:
            raise UnknownGpuModelError(
                f"gpu_model_id not found in GPU master: {gpu_model_id}",
                gpu_model_id=gpu_model_id,
            )
        vendor_id = str(model.get("vendor_id", ""))
        family_id = str(model.get("family_id", ""))
        if not gpu_repo.get_vendor(vendor_id):
            raise RepositoryValidationError(
                f"gpu vendor reference missing for model {gpu_model_id}: {vendor_id}",
                field="gpu_model_id",
            )
        if not gpu_repo.get_family(family_id):
            raise RepositoryValidationError(
                f"gpu family reference missing for model {gpu_model_id}: {family_id}",
                field="gpu_model_id",
            )

    def resolve_all(self, data: dict[str, Any]) -> None:
        mall_id = str(data["mall_id"])
        self.ensure_mall(mall_id)
        self.resolve_board_partner(str(data["board_partner_id"]))
        self.resolve_gpu_model(str(data["gpu_model_id"]))
        self.ensure_seller(
            seller_id=str(data["seller_id"]),
            mall_id=mall_id,
            seller_name=str(data.get("seller") or data["seller_id"]),
            normalized_seller_name=data.get("normalized_seller_name"),
        )
