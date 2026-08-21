"""Shared CLI helpers for investigation operations."""

from __future__ import annotations

from pricebrain_app.crawler.dashboard_operations_cli import build_dashboard_operations_view
from pricebrain_app.crawler.investigation_operations_view import InvestigationOperationsView


def build_investigation_operations_view() -> InvestigationOperationsView:
    return InvestigationOperationsView(build_dashboard_operations_view())
