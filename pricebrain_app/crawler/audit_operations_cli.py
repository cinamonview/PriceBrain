"""Shared CLI helpers for audit operations commands."""

from __future__ import annotations

from pricebrain_app.crawler.audit_operations_view import AuditOperationsView
from pricebrain_app.crawler.price_alert_cli import build_price_alert_repository


def build_audit_operations_view() -> AuditOperationsView:
    return AuditOperationsView(build_price_alert_repository())
