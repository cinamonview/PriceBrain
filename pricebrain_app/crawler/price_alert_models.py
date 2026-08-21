"""Price alert models — alert rules and evaluation results."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from pricebrain_app.crawler.targets import parse_datetime, utc_now

PRICE_ALERTS_COLLECTION = "price_alerts"
DEFAULT_ALERT_COOLDOWN_SECONDS = 0


class PriceAlertType(str, Enum):
    PRICE_BELOW = "PRICE_BELOW"
    PRICE_DROP_PERCENT = "PRICE_DROP_PERCENT"
    PRICE_DROP_AMOUNT = "PRICE_DROP_AMOUNT"
    PRICE_UP = "PRICE_UP"
    PRICE_CHANGED = "PRICE_CHANGED"


class AlertEvaluationOutcome(str, Enum):
    TRIGGERED = "TRIGGERED"
    NOT_TRIGGERED = "NOT_TRIGGERED"
    SKIPPED = "SKIPPED"
    INVALID = "INVALID"


CLI_ALERT_TYPE_CHOICES = {
    "price-below": PriceAlertType.PRICE_BELOW,
    "price-drop-percent": PriceAlertType.PRICE_DROP_PERCENT,
    "price-drop-amount": PriceAlertType.PRICE_DROP_AMOUNT,
    "price-up": PriceAlertType.PRICE_UP,
    "price-changed": PriceAlertType.PRICE_CHANGED,
}


@dataclass
class PriceAlert:
    alert_id: str
    target_id: str
    mall_id: str
    alert_type: PriceAlertType
    threshold: float
    enabled: bool = True
    brand: str | None = None
    product_name: str | None = None
    cooldown_seconds: int = DEFAULT_ALERT_COOLDOWN_SECONDS
    last_triggered_at: datetime | None = None
    last_observed_price: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def to_firestore_dict(self) -> dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "target_id": self.target_id,
            "mall_id": self.mall_id,
            "alert_type": self.alert_type.value,
            "threshold": self.threshold,
            "enabled": self.enabled,
            "brand": self.brand,
            "product_name": self.product_name,
            "cooldown_seconds": int(self.cooldown_seconds),
            "last_triggered_at": self.last_triggered_at,
            "last_observed_price": self.last_observed_price,
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_firestore_dict(cls, data: dict[str, Any], *, doc_id: str) -> PriceAlert:
        alert_type = PriceAlertType(str(data.get("alert_type") or PriceAlertType.PRICE_BELOW.value))
        metadata = data.get("metadata")
        return cls(
            alert_id=str(data.get("alert_id") or doc_id),
            target_id=str(data.get("target_id") or ""),
            mall_id=str(data.get("mall_id") or ""),
            alert_type=alert_type,
            threshold=float(data.get("threshold", 0)),
            enabled=bool(data.get("enabled", True)),
            brand=_optional_str(data.get("brand")),
            product_name=_optional_str(data.get("product_name")),
            cooldown_seconds=int(data.get("cooldown_seconds", DEFAULT_ALERT_COOLDOWN_SECONDS)),
            last_triggered_at=parse_datetime(data.get("last_triggered_at")),
            last_observed_price=_optional_int(data.get("last_observed_price")),
            metadata=dict(metadata) if isinstance(metadata, dict) else {},
            created_at=parse_datetime(data.get("created_at")),
            updated_at=parse_datetime(data.get("updated_at")),
        )


@dataclass(frozen=True)
class AlertEvaluationResult:
    alert_id: str
    target_id: str
    alert_type: PriceAlertType
    outcome: AlertEvaluationOutcome
    current_price: int | None
    previous_price: int | None
    threshold: float
    message: str
    observed_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "target_id": self.target_id,
            "alert_type": self.alert_type.value,
            "outcome": self.outcome.value,
            "current_price": self.current_price,
            "previous_price": self.previous_price,
            "threshold": self.threshold,
            "message": self.message,
            "observed_at": _iso(self.observed_at),
        }


def parse_cli_alert_type(value: str) -> PriceAlertType:
    key = value.strip().lower().replace("_", "-")
    if key not in CLI_ALERT_TYPE_CHOICES:
        supported = ", ".join(sorted(CLI_ALERT_TYPE_CHOICES))
        raise ValueError(f"Unsupported alert type: {value}. Supported: {supported}")
    return CLI_ALERT_TYPE_CHOICES[key]


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=utc_now().tzinfo)
    return value.isoformat()
