"""Shared CLI helpers for remediation operations."""

from __future__ import annotations

from pricebrain_app.crawler.investigation_operations_cli import build_investigation_operations_view
from pricebrain_app.crawler.remediation_operations_view import RemediationOperationsView


def build_remediation_operations_view() -> RemediationOperationsView:
    return RemediationOperationsView(build_investigation_operations_view())
