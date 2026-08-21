"""Shared CLI helpers for alert operations commands."""

from __future__ import annotations

from pricebrain_app.crawler.alert_operations_view import AlertOperationsView
from pricebrain_app.crawler.alert_ops_health_store import get_alert_ops_health_store
from pricebrain_app.crawler.price_alert_cli import build_price_alert_repository
from pricebrain_app.crawler.price_ops_cli import build_price_operations_view
from pricebrain_app.crawler.target_repository import CrawlTargetRepository
from pricebrain_app.firebase.admin import get_firestore_client


def build_alert_operations_view() -> AlertOperationsView:
    db = get_firestore_client()
    return AlertOperationsView(
        build_price_alert_repository(),
        CrawlTargetRepository(db),
        build_price_operations_view(),
        health_store=get_alert_ops_health_store(),
    )
