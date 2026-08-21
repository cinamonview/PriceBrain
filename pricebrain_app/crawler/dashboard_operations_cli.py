"""Shared CLI helpers for dashboard operations."""

from __future__ import annotations

from pricebrain_app.crawler.alert_operations_cli import build_alert_operations_view
from pricebrain_app.crawler.audit_operations_cli import build_audit_operations_view
from pricebrain_app.crawler.dashboard_operations_view import DashboardOperationsView
from pricebrain_app.crawler.ops_cli import build_operations_view
from pricebrain_app.crawler.price_ops_cli import build_price_operations_view


def build_dashboard_operations_view() -> DashboardOperationsView:
    return DashboardOperationsView(
        build_operations_view(),
        build_price_operations_view(),
        build_alert_operations_view(),
        build_audit_operations_view(),
    )
