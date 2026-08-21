"""Shared CLI helpers for price alert commands."""

from __future__ import annotations

from pricebrain_app.crawler.price_alert_repository import PriceAlertRepository
from pricebrain_app.crawler.price_alert_service import PriceAlertService
from pricebrain_app.crawler.price_ops_cli import build_price_operations_view
from pricebrain_app.crawler.target_repository import CrawlTargetRepository
from pricebrain_app.firebase.admin import get_firestore_client


def build_price_alert_repository() -> PriceAlertRepository:
    return PriceAlertRepository(get_firestore_client())


def build_price_alert_service() -> PriceAlertService:
    db = get_firestore_client()
    return PriceAlertService(
        PriceAlertRepository(db),
        build_price_operations_view(),
    )


def build_target_repository() -> CrawlTargetRepository:
    return CrawlTargetRepository(get_firestore_client())
