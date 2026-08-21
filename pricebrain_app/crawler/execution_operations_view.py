"""Read-only remediation execution history queries."""

from __future__ import annotations

from datetime import datetime

from pricebrain_app.crawler.execution_health import classify_execution_health
from pricebrain_app.crawler.execution_history_store import (
    APPROVAL_FAILURE_CODES,
    ExecutionHistoryStore,
    get_execution_history_store,
    parse_execution_history_entry,
)
from pricebrain_app.crawler.execution_operations_models import (
    STATUS_PRIORITY_ORDER,
    ExecutionHistoryFilter,
    ExecutionHistorySnapshot,
    ExecutionHistoryStatus,
    ExecutionHistorySummary,
    ExecutionOperationsSnapshot,
)
from pricebrain_app.crawler.logging_utils import get_crawler_logger
from pricebrain_app.crawler.targets import utc_now

logger = get_crawler_logger("crawler.execution_operations")


class ExecutionOperationsView:
    """Read-only remediation execution history operations."""

    def __init__(self, *, history_store: ExecutionHistoryStore | None = None) -> None:
        self._store = history_store or get_execution_history_store()

    def list_recent(
        self,
        *,
        filters: ExecutionHistoryFilter | None = None,
    ) -> list[ExecutionHistorySnapshot]:
        snapshots, _ = self._load_snapshots()
        filtered = self._apply_filters(snapshots, filters)
        ordered = self._sort(filtered)
        if filters and filters.recent is not None:
            ordered = ordered[: max(int(filters.recent), 0)]
        logger.info(
            "execution.operations.viewed",
            extra={"event": "execution.operations.viewed", "total": len(ordered)},
        )
        return ordered

    def failures(self, *, recent: int | None = None) -> list[ExecutionHistorySnapshot]:
        return self.list_recent(
            filters=ExecutionHistoryFilter(failures_only=True, recent=recent),
        )

    def blocked(self, *, recent: int | None = None) -> list[ExecutionHistorySnapshot]:
        return self.list_recent(
            filters=ExecutionHistoryFilter(blocked_only=True, recent=recent),
        )

    def executed(self, *, recent: int | None = None) -> list[ExecutionHistorySnapshot]:
        snapshots = self.list_recent(filters=ExecutionHistoryFilter(recent=recent))
        return [item for item in snapshots if item.entry and item.entry.status is ExecutionHistoryStatus.EXECUTED]

    def dry_runs(self, *, recent: int | None = None) -> list[ExecutionHistorySnapshot]:
        snapshots = self.list_recent(filters=ExecutionHistoryFilter(recent=recent))
        return [item for item in snapshots if item.entry and item.entry.status is ExecutionHistoryStatus.DRY_RUN]

    def planned(self, *, recent: int | None = None) -> list[ExecutionHistorySnapshot]:
        snapshots = self.list_recent(filters=ExecutionHistoryFilter(recent=recent))
        return [item for item in snapshots if item.entry and item.entry.status is ExecutionHistoryStatus.PLANNED]

    def for_action(self, action_id: str, *, recent: int | None = None) -> list[ExecutionHistorySnapshot]:
        return self.list_recent(
            filters=ExecutionHistoryFilter(action_id=action_id.strip(), recent=recent),
        )

    def for_target(self, target_id: str, *, recent: int | None = None) -> list[ExecutionHistorySnapshot]:
        return self.list_recent(
            filters=ExecutionHistoryFilter(target_id=target_id.strip(), recent=recent),
        )

    def for_alert(self, alert_id: str, *, recent: int | None = None) -> list[ExecutionHistorySnapshot]:
        return self.list_recent(
            filters=ExecutionHistoryFilter(alert_id=alert_id.strip(), recent=recent),
        )

    def summarize(self, *, filters: ExecutionHistoryFilter | None = None) -> ExecutionHistorySummary:
        snapshots = self.list_recent(filters=filters)
        valid = [item.entry for item in snapshots if item.entry is not None]
        read_errors = sum(1 for item in snapshots if item.read_error is not None) + self._store.record_errors
        by_action_type: dict[str, int] = {}
        by_area: dict[str, int] = {}
        planned = dry_run = approved = executed = blocked = failed = skipped = 0
        mutation_count = 0
        approval_failures = 0
        recent_failures = 0
        for entry in valid:
            by_action_type[entry.action_type.value] = by_action_type.get(entry.action_type.value, 0) + 1
            by_area[entry.area] = by_area.get(entry.area, 0) + 1
            if entry.status is ExecutionHistoryStatus.PLANNED:
                planned += 1
            elif entry.status is ExecutionHistoryStatus.DRY_RUN:
                dry_run += 1
            elif entry.status is ExecutionHistoryStatus.APPROVED:
                approved += 1
            elif entry.status is ExecutionHistoryStatus.EXECUTED:
                executed += 1
            elif entry.status is ExecutionHistoryStatus.BLOCKED:
                blocked += 1
            elif entry.status is ExecutionHistoryStatus.FAILED:
                failed += 1
            elif entry.status is ExecutionHistoryStatus.SKIPPED:
                skipped += 1
            if entry.mutation_performed:
                mutation_count += 1
            if entry.error_code in APPROVAL_FAILURE_CODES:
                approval_failures += 1
            if entry.status is ExecutionHistoryStatus.FAILED:
                recent_failures += 1
        return ExecutionHistorySummary(
            total=len(valid),
            planned=planned,
            dry_run=dry_run,
            approved=approved,
            executed=executed,
            blocked=blocked,
            failed=failed,
            skipped=skipped,
            mutation_count=mutation_count,
            approval_failures=approval_failures,
            recent_failures=recent_failures,
            by_action_type=tuple(sorted(by_action_type.items(), key=lambda pair: (-pair[1], pair[0]))),
            by_area=tuple(sorted(by_area.items(), key=lambda pair: (-pair[1], pair[0]))),
            read_errors=read_errors,
        )

    def build_snapshot(
        self,
        *,
        filters: ExecutionHistoryFilter | None = None,
        now: datetime | None = None,
    ) -> ExecutionOperationsSnapshot:
        run_at = now or utc_now()
        summary = self.summarize(filters=filters)
        health, reasons = classify_execution_health(summary)
        entries = tuple(self.list_recent(filters=filters))
        return ExecutionOperationsSnapshot(
            generated_at=run_at,
            summary=summary,
            health=health,
            health_reasons=reasons,
            entries=entries,
        )

    def _load_snapshots(self) -> tuple[list[ExecutionHistorySnapshot], int]:
        snapshots: list[ExecutionHistorySnapshot] = []
        read_errors = 0
        for raw in self._store.list_raw():
            try:
                entry = parse_execution_history_entry(raw)
                snapshots.append(ExecutionHistorySnapshot(entry=entry))
            except Exception as exc:
                read_errors += 1
                snapshots.append(ExecutionHistorySnapshot(read_error=str(exc)))
        return snapshots, read_errors

    def _apply_filters(
        self,
        snapshots: list[ExecutionHistorySnapshot],
        filters: ExecutionHistoryFilter | None,
    ) -> list[ExecutionHistorySnapshot]:
        if filters is None:
            return snapshots
        filtered: list[ExecutionHistorySnapshot] = []
        for item in snapshots:
            if item.entry is None:
                if not filters.failures_only and not filters.blocked_only:
                    filtered.append(item)
                continue
            if filters.action_id and item.entry.action_id != filters.action_id.strip():
                continue
            if filters.target_id and item.entry.target_id != filters.target_id.strip():
                continue
            if filters.alert_id and item.entry.alert_id != filters.alert_id.strip():
                continue
            if filters.failures_only and item.entry.status is not ExecutionHistoryStatus.FAILED:
                continue
            if filters.blocked_only and item.entry.status is not ExecutionHistoryStatus.BLOCKED:
                continue
            filtered.append(item)
        return filtered

    def _sort(self, snapshots: list[ExecutionHistorySnapshot]) -> list[ExecutionHistorySnapshot]:
        def sort_key(item: ExecutionHistorySnapshot) -> tuple:
            if item.entry is None:
                return (0, 0, "")
            occurred = item.entry.occurred_at or item.entry.started_at
            ts = occurred.timestamp() if occurred else 0
            status_rank = STATUS_PRIORITY_ORDER.get(item.entry.status, 0)
            return (-ts, -status_rank, item.entry.execution_id)

        return sorted(snapshots, key=sort_key)
