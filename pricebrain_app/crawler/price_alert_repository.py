"""Price alert Firestore repository — price_alerts collection only."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pricebrain_app.crawler.price_alert_models import (
    PRICE_ALERTS_COLLECTION,
    PriceAlert,
    PriceAlertType,
)
from pricebrain_app.crawler.targets import utc_now


class PriceAlertRepository:
    """Persist price alert rules — no evaluation logic."""

    def __init__(self, db: Any) -> None:
        self._db = db

    def create(
        self,
        *,
        target_id: str,
        mall_id: str,
        alert_type: PriceAlertType,
        threshold: float,
        enabled: bool = True,
        brand: str | None = None,
        product_name: str | None = None,
        cooldown_seconds: int = 0,
        metadata: dict[str, Any] | None = None,
        now: datetime | None = None,
    ) -> PriceAlert:
        run_at = now or utc_now()
        alert_id = uuid.uuid4().hex
        alert = PriceAlert(
            alert_id=alert_id,
            target_id=target_id.strip(),
            mall_id=mall_id.strip().lower(),
            alert_type=alert_type,
            threshold=float(threshold),
            enabled=enabled,
            brand=brand,
            product_name=product_name,
            cooldown_seconds=int(cooldown_seconds),
            metadata=dict(metadata or {}),
            created_at=run_at,
            updated_at=run_at,
        )
        self._db.collection(PRICE_ALERTS_COLLECTION).document(alert_id).set(
            alert.to_firestore_dict()
        )
        saved = self.get(alert_id)
        if saved is None:
            raise RuntimeError(f"Failed to create price alert: {alert_id}")
        return saved

    def get(self, alert_id: str) -> PriceAlert | None:
        doc = self._db.collection(PRICE_ALERTS_COLLECTION).document(alert_id.strip()).get()
        if not doc.exists:
            return None
        data = doc.to_dict() or {}
        return PriceAlert.from_firestore_dict(data, doc_id=doc.id)

    def list_all(
        self,
        *,
        target_id: str | None = None,
        enabled: bool | None = None,
    ) -> list[PriceAlert]:
        alerts: list[PriceAlert] = []
        for snapshot in self._db.collection(PRICE_ALERTS_COLLECTION).stream():
            data = snapshot.to_dict() or {}
            alert = PriceAlert.from_firestore_dict(data, doc_id=snapshot.id)
            if target_id is not None and alert.target_id != target_id.strip():
                continue
            if enabled is not None and alert.enabled is not enabled:
                continue
            alerts.append(alert)
        alerts.sort(key=lambda item: (item.target_id, item.alert_type.value, item.alert_id))
        return alerts

    def list_enabled(self) -> list[PriceAlert]:
        return self.list_all(enabled=True)

    def update(self, alert_id: str, **fields: Any) -> PriceAlert:
        current = self.get(alert_id)
        if current is None:
            raise KeyError(f"Price alert not found: {alert_id}")

        payload: dict[str, Any] = {"updated_at": utc_now()}
        if "threshold" in fields and fields["threshold"] is not None:
            payload["threshold"] = float(fields["threshold"])
        if "enabled" in fields and fields["enabled"] is not None:
            payload["enabled"] = bool(fields["enabled"])
        if "cooldown_seconds" in fields and fields["cooldown_seconds"] is not None:
            payload["cooldown_seconds"] = int(fields["cooldown_seconds"])
        if "brand" in fields:
            payload["brand"] = fields["brand"]
        if "product_name" in fields:
            payload["product_name"] = fields["product_name"]
        if "metadata" in fields and fields["metadata"] is not None:
            payload["metadata"] = dict(fields["metadata"])
        if "last_triggered_at" in fields:
            payload["last_triggered_at"] = fields["last_triggered_at"]
        if "last_observed_price" in fields:
            payload["last_observed_price"] = fields["last_observed_price"]

        self._db.collection(PRICE_ALERTS_COLLECTION).document(alert_id).set(payload, merge=True)
        saved = self.get(alert_id)
        if saved is None:
            raise RuntimeError(f"Failed to update price alert: {alert_id}")
        return saved

    def delete(self, alert_id: str) -> bool:
        doc = self._db.collection(PRICE_ALERTS_COLLECTION).document(alert_id.strip()).get()
        if not doc.exists:
            return False
        self._db.collection(PRICE_ALERTS_COLLECTION).document(alert_id.strip()).set(
            {"enabled": False, "updated_at": utc_now()},
            merge=True,
        )
        return True

    def set_enabled(self, alert_id: str, *, enabled: bool) -> PriceAlert:
        return self.update(alert_id, enabled=enabled)

    def mark_triggered(
        self,
        alert_id: str,
        *,
        observed_price: int,
        triggered_at: datetime | None = None,
    ) -> PriceAlert:
        run_at = triggered_at or utc_now()
        return self.update(
            alert_id,
            last_triggered_at=run_at,
            last_observed_price=int(observed_price),
        )
