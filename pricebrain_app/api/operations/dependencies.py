"""FastAPI dependencies for read-only operations views."""

from __future__ import annotations

from pricebrain_app.crawler.audit_operations_cli import build_audit_operations_view
from pricebrain_app.crawler.audit_operations_view import AuditOperationsView
from pricebrain_app.crawler.command_center_operations_cli import (
    build_command_center_operations_view,
    build_execution_operations_view,
)
from pricebrain_app.crawler.command_center_operations_view import CommandCenterOperationsView
from pricebrain_app.crawler.dashboard_operations_cli import build_dashboard_operations_view
from pricebrain_app.crawler.dashboard_operations_view import DashboardOperationsView
from pricebrain_app.crawler.execution_operations_view import ExecutionOperationsView
from pricebrain_app.crawler.investigation_operations_cli import build_investigation_operations_view
from pricebrain_app.crawler.investigation_operations_view import InvestigationOperationsView
from pricebrain_app.crawler.remediation_operations_cli import build_remediation_operations_view
from pricebrain_app.crawler.remediation_operations_view import RemediationOperationsView


def get_dashboard_operations_view() -> DashboardOperationsView:
    return build_dashboard_operations_view()


def get_investigation_operations_view() -> InvestigationOperationsView:
    return build_investigation_operations_view()


def get_remediation_operations_view() -> RemediationOperationsView:
    return build_remediation_operations_view()


def get_execution_operations_view() -> ExecutionOperationsView:
    return build_execution_operations_view()


def get_audit_operations_view() -> AuditOperationsView:
    return build_audit_operations_view()


def get_command_center_operations_view() -> CommandCenterOperationsView:
    return build_command_center_operations_view()
