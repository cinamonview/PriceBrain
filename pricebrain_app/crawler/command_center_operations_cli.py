"""Shared CLI helpers for command center operations."""

from __future__ import annotations

from pricebrain_app.crawler.command_center_operations_view import CommandCenterOperationsView
from pricebrain_app.crawler.dashboard_operations_cli import build_dashboard_operations_view
from pricebrain_app.crawler.execution_operations_view import ExecutionOperationsView
from pricebrain_app.crawler.investigation_operations_cli import build_investigation_operations_view
from pricebrain_app.crawler.remediation_operations_cli import build_remediation_operations_view


def build_execution_operations_view() -> ExecutionOperationsView:
    return ExecutionOperationsView()


def build_command_center_operations_view() -> CommandCenterOperationsView:
    return CommandCenterOperationsView(
        build_dashboard_operations_view(),
        build_investigation_operations_view(),
        build_remediation_operations_view(),
        build_execution_operations_view(),
    )
