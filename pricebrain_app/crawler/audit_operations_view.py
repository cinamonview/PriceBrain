"""Read-only audit event history queries."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pricebrain_app.crawler.audit_event_store import AuditEventStore, get_audit_event_store, load_audit_snapshots
from pricebrain_app.crawler.audit_operations_format import format_audit_event_summary
from pricebrain_app.crawler.audit_health import classify_audit_health
from pricebrain_app.crawler.audit_operations_models import (
    ALERT_EVENT_TYPES,
    NOTIFICATION_EVENT_TYPES,
    RUNNER_EVENT_TYPES,
    AuditEvent,
    AuditEventFilter,
    AuditEventSnapshot,
    AuditEventSummary,
    AuditEventType,
    AuditOperationsSnapshot,
)
from pricebrain_app.crawler.logging_utils import get_crawler_logger
from pricebrain_app.crawler.price_alert_models import PriceAlert
from pricebrain_app.crawler.price_alert_repository import PriceAlertRepository
from pricebrain_app.crawler.targets import parse_datetime, utc_now

logger = get_crawler_logger("crawler.audit_operations")

FAILURE_EVENT_TYPES = frozenset(
    {
        AuditEventType.ALERT_INVALID,
        AuditEventType.NOTIFICATION_FAILED,
        AuditEventType.RUNNER_CYCLE_FAILED,
    }
)


class AuditOperationsView:
    """Read-only audit event history operations."""

    def __init__(
        self,
        alert_repository: PriceAlertRepository,
        *,
        event_store: AuditEventStore | None = None,
    ) -> None:
        self._alerts = alert_repository
        self._store = event_store or get_audit_event_store()

    def list_events(
        self,
        *,
        filters: AuditEventFilter | None = None,
        ascending: bool = False,
    ) -> list[AuditEventSnapshot]:
        flt = filters or AuditEventFilter()
        snapshots, _ = self._load_snapshots()
        filtered = [item for item in snapshots if self._matches(item, flt)]
        ordered = self._sort(filtered, ascending=ascending)
        if flt.recent is not None:
            ordered = ordered[: max(int(flt.recent), 0)]
        _log_viewed("audit.operations.viewed", total=len(ordered))
        return ordered

    def summarize_events(self, *, filters: AuditEventFilter | None = None) -> AuditEventSummary:
        snapshots = self.list_events(filters=filters)
        valid = [item for item in snapshots if item.event is not None]
        read_errors = sum(1 for item in snapshots if item.read_error is not None)
        by_type = _count_by(valid, lambda item: item.event.event_type.value if item.event else "UNKNOWN")
        by_status = _count_by(
            valid,
            lambda item: item.event.status or "unknown" if item.event else "unknown",
        )
        by_channel = _count_by(
            valid,
            lambda item: item.event.channel or "unknown" if item.event else "unknown",
        )
        return AuditEventSummary(
            total=len(valid),
            recent=len(valid),
            by_type=by_type,
            by_status=by_status,
            by_channel=by_channel,
            alert_events=sum(
                1 for item in valid if item.event and item.event.event_type in ALERT_EVENT_TYPES
            ),
            notification_events=sum(
                1
                for item in valid
                if item.event and item.event.event_type in NOTIFICATION_EVENT_TYPES
            ),
            runner_events=sum(
                1 for item in valid if item.event and item.event.event_type in RUNNER_EVENT_TYPES
            ),
            read_errors=read_errors,
        )

    def build_snapshot(
        self,
        *,
        filters: AuditEventFilter | None = None,
        now: datetime | None = None,
    ) -> AuditOperationsSnapshot:
        run_at = now or utc_now()
        flt = filters or AuditEventFilter(recent=50)
        summary = self.summarize_events(filters=flt)
        health, reasons = classify_audit_health(summary)
        events = tuple(self.list_events(filters=flt))
        return AuditOperationsSnapshot(
            generated_at=run_at,
            summary=summary,
            health=health,
            health_reasons=reasons,
            events=events,
        )

    def list_alert_audit(self, alert_id: str) -> list[AuditEventSnapshot]:
        alert = self._alerts.get(alert_id.strip())
        snapshots = self.list_events(
            filters=AuditEventFilter(alert_id=alert_id.strip()),
            ascending=True,
        )
        if alert is not None and not any(
            item.event and item.event.event_type is AuditEventType.ALERT_CREATED for item in snapshots
        ):
            created = self._created_snapshot(alert)
            snapshots = [created, *snapshots]
        return snapshots

    def list_target_audit(self, target_id: str) -> list[AuditEventSnapshot]:
        return self.list_events(
            filters=AuditEventFilter(target_id=target_id.strip()),
            ascending=True,
        )

    def list_runner_audit(
        self,
        *,
        recent: int | None = None,
        failures_only: bool = False,
    ) -> list[AuditEventSnapshot]:
        return self.list_events(
            filters=AuditEventFilter(
                runner_only=True,
                failures_only=failures_only,
                recent=recent,
            ),
        )

    def _load_snapshots(self) -> tuple[list[AuditEventSnapshot], int]:
        parsed, read_errors = load_audit_snapshots(self._store)
        snapshots: list[AuditEventSnapshot] = []
        for event, error in parsed:
            if error is not None:
                snapshots.append(
                    AuditEventSnapshot(event=None, summary="invalid event", read_error=error)
                )
                continue
            assert event is not None
            snapshots.append(
                AuditEventSnapshot(
                    event=event,
                    summary=format_audit_event_summary(event),
                )
            )
        return snapshots, read_errors

    def _matches(self, snapshot: AuditEventSnapshot, flt: AuditEventFilter) -> bool:
        if snapshot.read_error is not None:
            return not flt.failures_only and not flt.runner_only
        event = snapshot.event
        if event is None:
            return False
        if flt.event_type is not None:
            requested = flt.event_type.strip().upper().replace("-", "_")
            if event.event_type.value != requested:
                return False
        if flt.alert_id is not None and event.alert_id != flt.alert_id.strip():
            return False
        if flt.target_id is not None and event.target_id != flt.target_id.strip():
            return False
        if flt.mall_id is not None and (event.mall_id or "").lower() != flt.mall_id.strip().lower():
            return False
        if flt.status is not None and (event.status or "").upper() != flt.status.strip().upper():
            return False
        if flt.channel is not None and (event.channel or "").upper() != flt.channel.strip().upper():
            return False
        if flt.since is not None and event.occurred_at < flt.since:
            return False
        if flt.until is not None and event.occurred_at > flt.until:
            return False
        if flt.failures_only and event.event_type not in FAILURE_EVENT_TYPES:
            return False
        if flt.runner_only and event.event_type not in RUNNER_EVENT_TYPES:
            return False
        return True

    def _sort(self, snapshots: list[AuditEventSnapshot], *, ascending: bool) -> list[AuditEventSnapshot]:
        if ascending:
            return sorted(
                snapshots,
                key=lambda item: (
                    item.event.occurred_at if item.event else utc_now(),
                    item.event.event_id if item.event else "",
                ),
            )
        return sorted(
            snapshots,
            key=lambda item: (
                -(item.event.occurred_at.timestamp() if item.event else 0),
                item.event.event_id if item.event else "",
            ),
        )

    def _created_snapshot(self, alert: PriceAlert) -> AuditEventSnapshot:
        event = AuditEvent(
            event_id=f"created-{alert.alert_id}",
            event_type=AuditEventType.ALERT_CREATED,
            occurred_at=alert.created_at or utc_now(),
            alert_id=alert.alert_id,
            target_id=alert.target_id,
            mall_id=alert.mall_id,
            status="CREATED",
            message=f"alert_type={alert.alert_type.value} threshold={alert.threshold}",
            metadata={"enabled": alert.enabled},
        )
        return AuditEventSnapshot(event=event, summary=format_audit_event_summary(event))


def _count_by(items: list[AuditEventSnapshot], key_fn) -> tuple[tuple[str, int], ...]:
    counts: dict[str, int] = {}
    for item in items:
        key = str(key_fn(item))
        counts[key] = counts.get(key, 0) + 1
    return tuple(sorted(counts.items(), key=lambda pair: (-pair[1], pair[0])))


def parse_cli_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    parsed = parse_datetime(value.strip())
    if parsed is None:
        raise ValueError(f"Invalid datetime: {value}")
    return parsed


def _log_viewed(event: str, *, total: int) -> None:
    logger.info(event, extra={"event": event, "total": total})
