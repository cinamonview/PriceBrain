"""Read-only dashboard investigation queries."""

from __future__ import annotations

from datetime import datetime

from pricebrain_app.crawler.dashboard_operations_models import DashboardFilter, PriceBrainDashboardSnapshot
from pricebrain_app.crawler.dashboard_operations_view import DashboardOperationsView
from pricebrain_app.crawler.investigation_operations_models import (
    DashboardInvestigationSnapshot,
    InvestigationFilter,
    InvestigationFinding,
    InvestigationSeverity,
    InvestigationSummary,
    SEVERITY_ORDER,
    sort_findings,
    summarize_findings,
)
from pricebrain_app.crawler.investigation_rules import analyze_dashboard_snapshot
from pricebrain_app.crawler.logging_utils import get_crawler_logger
from pricebrain_app.crawler.targets import utc_now

logger = get_crawler_logger("crawler.investigation_operations")
FAILURE_SEVERITIES = frozenset(
    {InvestigationSeverity.WARNING, InvestigationSeverity.ERROR, InvestigationSeverity.CRITICAL}
)


class InvestigationOperationsView:
    """Investigate dashboard health using existing read-only operations views."""

    def __init__(self, dashboard_view: DashboardOperationsView) -> None:
        self._dashboard = dashboard_view
        self._last_snapshot: DashboardInvestigationSnapshot | None = None

    def investigate_dashboard(
        self,
        *,
        dashboard_filters: DashboardFilter | None = None,
        now: datetime | None = None,
        dashboard: PriceBrainDashboardSnapshot | None = None,
    ) -> DashboardInvestigationSnapshot:
        run_at = now or utc_now()
        if dashboard is None:
            dashboard = self._dashboard.build_dashboard_snapshot(filters=dashboard_filters, now=run_at)
        findings = sort_findings(analyze_dashboard_snapshot(dashboard, generated_at=run_at))
        summary = summarize_findings(findings)
        snapshot = DashboardInvestigationSnapshot(
            generated_at=run_at,
            health=dashboard.summary.health,
            summary=summary,
            findings=tuple(findings),
            dashboard_summary=dashboard.summary,
            crawler=dashboard.crawler,
            price=dashboard.price,
            alerts=dashboard.alerts,
            notifications=dashboard.notifications,
            runner=dashboard.runner,
            audit=dashboard.audit,
        )
        self._last_snapshot = snapshot
        logger.info(
            "investigation.operations.viewed",
            extra={
                "event": "investigation.operations.viewed",
                "health": snapshot.health.value,
                "total_findings": summary.total_findings,
            },
        )
        return snapshot

    def findings(
        self,
        *,
        filters: InvestigationFilter | None = None,
        snapshot: DashboardInvestigationSnapshot | None = None,
    ) -> list[InvestigationFinding]:
        current = snapshot or self._require_snapshot()
        return _filter_findings(list(current.findings), filters)

    def findings_for_area(
        self,
        area: str,
        *,
        filters: InvestigationFilter | None = None,
        snapshot: DashboardInvestigationSnapshot | None = None,
    ) -> list[InvestigationFinding]:
        flt = filters or InvestigationFilter()
        merged = InvestigationFilter(
            area=area,
            target_id=flt.target_id,
            alert_id=flt.alert_id,
            failures_only=flt.failures_only,
            min_severity=flt.min_severity,
        )
        return self.findings(filters=merged, snapshot=snapshot)

    def findings_for_target(
        self,
        target_id: str,
        *,
        filters: InvestigationFilter | None = None,
        snapshot: DashboardInvestigationSnapshot | None = None,
    ) -> list[InvestigationFinding]:
        flt = filters or InvestigationFilter()
        merged = InvestigationFilter(
            area=flt.area,
            target_id=target_id.strip(),
            alert_id=flt.alert_id,
            failures_only=flt.failures_only,
            min_severity=flt.min_severity,
        )
        return self.findings(filters=merged, snapshot=snapshot)

    def findings_for_alert(
        self,
        alert_id: str,
        *,
        filters: InvestigationFilter | None = None,
        snapshot: DashboardInvestigationSnapshot | None = None,
    ) -> list[InvestigationFinding]:
        flt = filters or InvestigationFilter()
        merged = InvestigationFilter(
            area=flt.area,
            target_id=flt.target_id,
            alert_id=alert_id.strip(),
            failures_only=flt.failures_only,
            min_severity=flt.min_severity,
        )
        return self.findings(filters=merged, snapshot=snapshot)

    def summary(
        self,
        *,
        filters: InvestigationFilter | None = None,
        snapshot: DashboardInvestigationSnapshot | None = None,
    ) -> InvestigationSummary:
        return summarize_findings(self.findings(filters=filters, snapshot=snapshot))

    def _require_snapshot(self) -> DashboardInvestigationSnapshot:
        if self._last_snapshot is None:
            return self.investigate_dashboard()
        return self._last_snapshot


def _filter_findings(
    findings: list[InvestigationFinding],
    filters: InvestigationFilter | None,
) -> list[InvestigationFinding]:
    flt = filters or InvestigationFilter()
    filtered: list[InvestigationFinding] = []
    for item in findings:
        if flt.area is not None and item.area != flt.area.strip().lower():
            continue
        if flt.target_id is not None and item.target_id != flt.target_id.strip():
            continue
        if flt.alert_id is not None and item.alert_id != flt.alert_id.strip():
            continue
        if flt.failures_only and item.severity is InvestigationSeverity.INFO:
            continue
        if flt.min_severity is not None and SEVERITY_ORDER[item.severity] < SEVERITY_ORDER[flt.min_severity]:
            continue
        filtered.append(item)
    return sort_findings(filtered)
