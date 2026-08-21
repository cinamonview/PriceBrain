"""Read-only remediation action handlers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from pricebrain_app.crawler.alert_operations_view import AlertOperationsView
from pricebrain_app.crawler.audit_operations_view import AuditOperationsView
from pricebrain_app.crawler.operations_view import CrawlerOperationsView
from pricebrain_app.crawler.price_operations_view import PriceOperationsView
from pricebrain_app.crawler.remediation_operations_models import RemediationAction, RemediationActionType


@dataclass(frozen=True)
class HandlerResult:
    message: str
    mutation_performed: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RemediationHandlerContext:
    crawler_view: CrawlerOperationsView
    price_view: PriceOperationsView
    alert_view: AlertOperationsView
    audit_view: AuditOperationsView


class RemediationActionHandler(ABC):
    action_type: RemediationActionType

    @abstractmethod
    def handle(self, action: RemediationAction, context: RemediationHandlerContext) -> HandlerResult:
        raise NotImplementedError


class CrawlerTargetReviewHandler(RemediationActionHandler):
    action_type = RemediationActionType.REVIEW_CRAWLER_TARGET

    def handle(self, action: RemediationAction, context: RemediationHandlerContext) -> HandlerResult:
        if action.target_id:
            target = context.crawler_view.get_target(action.target_id)
            if target is None:
                return HandlerResult(message=f"Target not found: {action.target_id}")
            return HandlerResult(
                message=(
                    f"Target {target.target_id} status={target.last_status or '-'} "
                    f"error={target.last_error_code or '-'}"
                ),
                metadata={"last_status": target.last_status, "last_error_code": target.last_error_code},
            )
        failures = context.crawler_view.list_recent_failures(limit=5)
        return HandlerResult(
            message=f"Review {len(failures)} recent crawler failure target(s)",
            metadata={"recent_failures": len(failures)},
        )


class SsgAccessReviewHandler(RemediationActionHandler):
    action_type = RemediationActionType.REVIEW_SSG_ACCESS

    def handle(self, action: RemediationAction, context: RemediationHandlerContext) -> HandlerResult:
        if action.target_id:
            target = context.crawler_view.get_target(action.target_id)
            if target is None:
                return HandlerResult(message=f"Target not found: {action.target_id}")
            return HandlerResult(
                message=(
                    f"SSG access review for {target.target_id}: "
                    f"{target.last_error_code or 'no error code'}"
                ),
                metadata={"last_error_code": target.last_error_code},
            )
        return HandlerResult(message="SSG_ACCESS_DENIED 상태 확인 필요")


class PriceHistoryReviewHandler(RemediationActionHandler):
    action_type = RemediationActionType.REVIEW_PRICE_HISTORY

    def handle(self, action: RemediationAction, context: RemediationHandlerContext) -> HandlerResult:
        if action.target_id:
            summary = context.price_view.get_price_summary(action.target_id)
            if summary is None:
                return HandlerResult(message=f"No price summary for {action.target_id}")
            return HandlerResult(
                message=(
                    f"Price history for {action.target_id}: "
                    f"classification={summary.classification.value} "
                    f"history_count={summary.history_count}"
                ),
                metadata={"classification": summary.classification.value, "history_count": summary.history_count},
            )
        gpu = context.price_view.summarize_gpu_prices()
        return HandlerResult(
            message=f"GPU price status: no_history={gpu.no_history} with_price={gpu.with_price}",
            metadata={"no_history": gpu.no_history, "with_price": gpu.with_price},
        )


class PriceAlertReviewHandler(RemediationActionHandler):
    action_type = RemediationActionType.REVIEW_ALERT

    def handle(self, action: RemediationAction, context: RemediationHandlerContext) -> HandlerResult:
        if action.alert_id:
            snapshot = context.alert_view.get_alert_snapshot(action.alert_id)
            if snapshot is None:
                return HandlerResult(message=f"Alert not found: {action.alert_id}")
            return HandlerResult(
                message=(
                    f"Alert {snapshot.alert_id} enabled={snapshot.enabled} "
                    f"classification={snapshot.classification or '-'}"
                ),
                metadata={"enabled": snapshot.enabled, "classification": snapshot.classification},
            )
        summary = context.alert_view.summarize_alerts()
        return HandlerResult(
            message=f"Alert summary total={summary.total} enabled={summary.enabled}",
            metadata={"total": summary.total, "enabled": summary.enabled},
        )


class NotificationReviewHandler(RemediationActionHandler):
    action_type = RemediationActionType.REVIEW_NOTIFICATION

    def handle(self, action: RemediationAction, context: RemediationHandlerContext) -> HandlerResult:
        summary = context.alert_view.summarize_notifications(recent_limit=5)
        return HandlerResult(
            message=(
                f"Notification ops sent={summary.notification_sent} "
                f"failed={summary.notification_failed}"
            ),
            metadata={
                "notification_sent": summary.notification_sent,
                "notification_failed": summary.notification_failed,
            },
        )


class RunnerReviewHandler(RemediationActionHandler):
    action_type = RemediationActionType.REVIEW_RUNNER

    def handle(self, action: RemediationAction, context: RemediationHandlerContext) -> HandlerResult:
        health = context.alert_view.get_runner_health(recent_limit=3)
        return HandlerResult(
            message=(
                f"Runner health cycles={health.recent_cycles} "
                f"last_status_errors={len(health.errors)}"
            ),
            metadata={"recent_cycles": health.recent_cycles, "errors": list(health.errors)},
        )


class AuditReviewHandler(RemediationActionHandler):
    action_type = RemediationActionType.REVIEW_AUDIT

    def handle(self, action: RemediationAction, context: RemediationHandlerContext) -> HandlerResult:
        summary = context.audit_view.summarize_events()
        return HandlerResult(
            message=f"Audit summary total={summary.total} read_errors={summary.read_errors}",
            metadata={"total": summary.total, "read_errors": summary.read_errors},
        )


class ConfigurationReviewHandler(RemediationActionHandler):
    action_type = RemediationActionType.VERIFY_CONFIGURATION

    def handle(self, action: RemediationAction, context: RemediationHandlerContext) -> HandlerResult:
        return HandlerResult(
            message="Configuration review required — no automatic changes performed",
            metadata={"finding_code": action.metadata.get("finding_code")},
        )


class NoActionHandler(RemediationActionHandler):
    action_type = RemediationActionType.NO_ACTION

    def handle(self, action: RemediationAction, context: RemediationHandlerContext) -> HandlerResult:
        return HandlerResult(message="No action required", metadata={"skipped": True})


def build_remediation_handlers() -> dict[RemediationActionType, RemediationActionHandler]:
    handlers: list[RemediationActionHandler] = [
        CrawlerTargetReviewHandler(),
        SsgAccessReviewHandler(),
        PriceHistoryReviewHandler(),
        PriceAlertReviewHandler(),
        NotificationReviewHandler(),
        RunnerReviewHandler(),
        AuditReviewHandler(),
        ConfigurationReviewHandler(),
        NoActionHandler(),
    ]
    return {handler.action_type: handler for handler in handlers}
