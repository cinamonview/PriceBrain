"""Pure investigation rule engine — no external I/O."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pricebrain_app.crawler.dashboard_operations_models import PriceBrainDashboardSnapshot
from pricebrain_app.crawler.investigation_operations_models import (
    InvestigationFinding,
    InvestigationSeverity,
)


def analyze_dashboard_snapshot(
    snapshot: PriceBrainDashboardSnapshot,
    *,
    generated_at: datetime | None = None,
) -> list[InvestigationFinding]:
    run_at = generated_at or snapshot.generated_at
    findings: list[InvestigationFinding] = []
    findings.extend(_analyze_crawler(snapshot, run_at))
    findings.extend(_analyze_price(snapshot, run_at))
    findings.extend(_analyze_alerts(snapshot, run_at))
    findings.extend(_analyze_notifications(snapshot, run_at))
    findings.extend(_analyze_runner(snapshot, run_at))
    findings.extend(_analyze_audit(snapshot, run_at))
    findings.extend(_analyze_positive_runner(snapshot, run_at))
    return findings


def _new_finding(
    *,
    area: str,
    code: str,
    severity: InvestigationSeverity,
    title: str,
    message: str,
    occurred_at: datetime | None = None,
    target_id: str | None = None,
    alert_id: str | None = None,
    event_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> InvestigationFinding:
    return InvestigationFinding(
        finding_id=uuid.uuid4().hex,
        severity=severity,
        area=area,
        code=code,
        title=title,
        message=message,
        target_id=target_id,
        alert_id=alert_id,
        event_id=event_id,
        occurred_at=occurred_at,
        metadata=dict(metadata or {}),
    )


def _analyze_crawler(snapshot: PriceBrainDashboardSnapshot, run_at: datetime) -> list[InvestigationFinding]:
    crawler = snapshot.crawler
    findings: list[InvestigationFinding] = []
    if crawler.read_error is not None:
        findings.append(
            _new_finding(
                area="crawler",
                code="CRAWLER_HTTP_ERROR",
                severity=InvestigationSeverity.ERROR,
                title="Crawler section read error",
                message=crawler.read_error,
                occurred_at=run_at,
            )
        )
        return findings

    if crawler.ssg_access_denied > 0:
        findings.append(
            _new_finding(
                area="crawler",
                code="CRAWLER_ACCESS_DENIED",
                severity=InvestigationSeverity.WARNING,
                title="SSG access denied",
                message=(
                    f"SSG target {crawler.ssg_access_denied}건에서 SSG_ACCESS_DENIED 발생"
                ),
                occurred_at=run_at,
                metadata={"count": crawler.ssg_access_denied},
            )
        )

    http_errors = crawler.failed_targets - crawler.ssg_access_denied
    if http_errors > 0:
        findings.append(
            _new_finding(
                area="crawler",
                code="CRAWLER_HTTP_ERROR",
                severity=InvestigationSeverity.ERROR,
                title="Crawler HTTP errors",
                message=f"{http_errors} target(s) report non-access-denied HTTP failures",
                occurred_at=run_at,
                metadata={"count": http_errors},
            )
        )

    if (
        crawler.enabled_targets > 0
        and crawler.recent_successes == 0
        and crawler.failed_targets > 0
    ):
        findings.append(
            _new_finding(
                area="crawler",
                code="CRAWLER_NO_SUCCESS",
                severity=InvestigationSeverity.WARNING,
                title="No recent crawl successes",
                message=(
                    f"{crawler.enabled_targets} enabled target(s) but no recent crawl success"
                ),
                occurred_at=run_at,
            )
        )

    for item in crawler.recent_failure_targets:
        if item.get("last_error_code") in {"SSG_ACCESS_DENIED", "ACCESS_DENIED"}:
            findings.append(
                _new_finding(
                    area="crawler",
                    code="CRAWLER_ACCESS_DENIED",
                    severity=InvestigationSeverity.WARNING,
                    title="Target access denied",
                    message=str(item.get("last_error_message") or "SSG_ACCESS_DENIED"),
                    target_id=str(item.get("target_id") or "") or None,
                    occurred_at=run_at,
                )
            )
    return findings


def _analyze_price(snapshot: PriceBrainDashboardSnapshot, run_at: datetime) -> list[InvestigationFinding]:
    price = snapshot.price
    if price.read_error is not None:
        return [
            _new_finding(
                area="price",
                code="PRICE_READ_ERROR",
                severity=InvestigationSeverity.ERROR,
                title="Price section read error",
                message=price.read_error,
                occurred_at=run_at,
            )
        ]
    if price.no_history > 0:
        return [
            _new_finding(
                area="price",
                code="PRICE_NO_HISTORY",
                severity=InvestigationSeverity.WARNING,
                title="Missing GPU price history",
                message=f"{price.no_history} GPU target(s) have no recent price history",
                occurred_at=run_at,
                metadata={"count": price.no_history},
            )
        ]
    return []


def _analyze_alerts(snapshot: PriceBrainDashboardSnapshot, run_at: datetime) -> list[InvestigationFinding]:
    alerts = snapshot.alerts
    runner = snapshot.runner
    findings: list[InvestigationFinding] = []
    if alerts.read_error is not None:
        findings.append(
            _new_finding(
                area="alert",
                code="ALERT_READ_ERROR",
                severity=InvestigationSeverity.ERROR,
                title="Alert section read error",
                message=alerts.read_error,
                occurred_at=run_at,
            )
        )
        return findings

    if alerts.invalid > 0 or alerts.recent_invalid > 0:
        findings.append(
            _new_finding(
                area="alert",
                code="ALERT_READ_ERROR",
                severity=InvestigationSeverity.ERROR,
                title="Invalid alert evaluations",
                message=(
                    f"{alerts.invalid} invalid alert(s), "
                    f"{alerts.recent_invalid} recent invalid evaluation(s)"
                ),
                occurred_at=run_at,
            )
        )

    if alerts.enabled > 0 and runner.evaluated == 0 and runner.recent_cycles == 0:
        findings.append(
            _new_finding(
                area="alert",
                code="ALERT_NO_RECENT_EVALUATION",
                severity=InvestigationSeverity.WARNING,
                title="No recent alert evaluation",
                message=f"{alerts.enabled} enabled alert(s) without recent runner evaluation",
                occurred_at=run_at,
            )
        )
    return findings


def _analyze_notifications(snapshot: PriceBrainDashboardSnapshot, run_at: datetime) -> list[InvestigationFinding]:
    notifications = snapshot.notifications
    findings: list[InvestigationFinding] = []
    if notifications.read_error is not None:
        findings.append(
            _new_finding(
                area="notification",
                code="NOTIFICATION_FAILURE",
                severity=InvestigationSeverity.ERROR,
                title="Notification section read error",
                message=notifications.read_error,
                occurred_at=run_at,
            )
        )
        return findings

    failure_count = max(notifications.failed, len(notifications.recent_failures))
    if failure_count >= 2:
        findings.append(
            _new_finding(
                area="notification",
                code="NOTIFICATION_FAILURE_REPEATED",
                severity=InvestigationSeverity.CRITICAL,
                title="Repeated notification failures",
                message=f"{failure_count} recent notification failure(s) detected",
                occurred_at=run_at,
                metadata={"count": failure_count},
            )
        )
    elif notifications.failed > 0 or notifications.recent_failures:
        alert_id = None
        target_id = None
        if notifications.recent_failures:
            first = notifications.recent_failures[0]
            alert_id = first.get("alert_id")
            target_id = first.get("target_id")
        findings.append(
            _new_finding(
                area="notification",
                code="NOTIFICATION_FAILURE",
                severity=InvestigationSeverity.ERROR,
                title="Notification failure",
                message=f"{notifications.failed} notification failure(s) detected",
                alert_id=str(alert_id) if alert_id else None,
                target_id=str(target_id) if target_id else None,
                occurred_at=run_at,
            )
        )
    return findings


def _analyze_runner(snapshot: PriceBrainDashboardSnapshot, run_at: datetime) -> list[InvestigationFinding]:
    runner = snapshot.runner
    if runner.read_error is not None:
        return [
            _new_finding(
                area="runner",
                code="RUNNER_CYCLE_FAILED",
                severity=InvestigationSeverity.ERROR,
                title="Runner section read error",
                message=runner.read_error,
                occurred_at=run_at,
            )
        ]

    if runner.recent_failed_cycles >= 2:
        return [
            _new_finding(
                area="runner",
                code="RUNNER_CYCLE_FAILURE_REPEATED",
                severity=InvestigationSeverity.CRITICAL,
                title="Repeated runner cycle failures",
                message=f"{runner.recent_failed_cycles} recent failed runner cycle(s)",
                occurred_at=runner.last_failed_cycle_at or run_at,
            )
        ]

    if runner.last_cycle_status == "FAILED" or runner.recent_failed_cycles == 1:
        return [
            _new_finding(
                area="runner",
                code="RUNNER_CYCLE_FAILED",
                severity=InvestigationSeverity.WARNING,
                title="Runner cycle failed",
                message="Latest runner cycle reported failure",
                occurred_at=runner.last_failed_cycle_at or runner.last_run_at or run_at,
            )
        ]
    return []


def _analyze_audit(snapshot: PriceBrainDashboardSnapshot, run_at: datetime) -> list[InvestigationFinding]:
    audit = snapshot.audit
    if audit.read_error is None:
        return []
    return [
        _new_finding(
            area="audit",
            code="AUDIT_READ_ERROR",
            severity=InvestigationSeverity.ERROR,
            title="Audit read error",
            message=audit.read_error,
            occurred_at=run_at,
        )
    ]


def _analyze_positive_runner(snapshot: PriceBrainDashboardSnapshot, run_at: datetime) -> list[InvestigationFinding]:
    runner = snapshot.runner
    if runner.read_error is not None or runner.last_cycle_status != "SUCCESS":
        return []
    return [
        _new_finding(
            area="runner",
            code="RUNNER_HEALTHY",
            severity=InvestigationSeverity.INFO,
            title="Runner healthy",
            message="Runner cycle 정상",
            occurred_at=runner.last_run_at or run_at,
        )
    ]
