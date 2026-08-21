"""Shared CLI helpers for remediation executor."""

from __future__ import annotations

from pricebrain_app.crawler.alert_operations_cli import build_alert_operations_view
from pricebrain_app.crawler.audit_operations_cli import build_audit_operations_view
from pricebrain_app.crawler.ops_cli import build_operations_view
from pricebrain_app.crawler.price_ops_cli import build_price_operations_view
from pricebrain_app.crawler.remediation_action_handlers import RemediationHandlerContext
from pricebrain_app.crawler.remediation_executor import RemediationActionExecutor
from pricebrain_app.crawler.remediation_executor_view import RemediationExecutorView
from pricebrain_app.crawler.remediation_operations_cli import build_remediation_operations_view


def build_remediation_executor_view() -> RemediationExecutorView:
    crawler_view = build_operations_view()
    price_view = build_price_operations_view()
    alert_view = build_alert_operations_view()
    audit_view = build_audit_operations_view()
    context = RemediationHandlerContext(
        crawler_view=crawler_view,
        price_view=price_view,
        alert_view=alert_view,
        audit_view=audit_view,
    )
    executor = RemediationActionExecutor(context)
    remediation_view = build_remediation_operations_view()
    return RemediationExecutorView(remediation_view, executor)
