import type {
  AuditEventTypeFilter,
  AuditFilterState,
  AuditSeverityFilter,
  AuditSortOption,
} from "../utils/auditFilters";
import { AUDIT_AREAS } from "../utils/auditFilters";
import {
  UI,
  formatAreaLabel,
  formatAuditEventTypeLabel,
  formatSeverityLabel,
  formatSortLabel,
} from "../utils/uiLabels";

interface AuditFiltersBarProps {
  filters: AuditFilterState;
  onChange: (next: AuditFilterState) => void;
}

const EVENT_TYPE_OPTIONS: AuditEventTypeFilter[] = [
  "ALL",
  "ALERT_TRIGGERED",
  "ALERT_INVALID",
  "NOTIFICATION_FAILED",
  "NOTIFICATION_SENT",
  "RUNNER_CYCLE_FAILED",
  "RUNNER_CYCLE_COMPLETED",
  "REMEDIATION_EXECUTED",
  "REMEDIATION_FAILED",
  "REMEDIATION_APPROVAL_BLOCKED",
  "UNKNOWN",
];

const SEVERITY_OPTIONS: AuditSeverityFilter[] = [
  "ALL",
  "CRITICAL",
  "ERROR",
  "WARNING",
  "INFO",
  "UNKNOWN",
];

const SORT_OPTIONS: AuditSortOption[] = ["NEWEST", "OLDEST", "TYPE", "SEVERITY"];

function formatEventTypeFilterLabel(option: AuditEventTypeFilter): string {
  if (option === "ALL") {
    return UI.all;
  }
  if (option === "UNKNOWN") {
    return formatSeverityLabel("UNKNOWN");
  }
  return formatAuditEventTypeLabel(option);
}

export function AuditFiltersBar({ filters, onChange }: AuditFiltersBarProps) {
  function update<K extends keyof AuditFilterState>(key: K, value: AuditFilterState[K]) {
    onChange({ ...filters, [key]: value });
  }

  return (
    <section className="section-card investigation-filters">
      <header>
        <h3>{UI.filters}</h3>
      </header>
      <div className="filters-grid">
        <label>
          이벤트 유형
          <select
            value={filters.eventType}
            onChange={(event) => update("eventType", event.target.value as AuditEventTypeFilter)}
            aria-label="이벤트 유형 필터"
          >
            {EVENT_TYPE_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {formatEventTypeFilterLabel(option)}
              </option>
            ))}
          </select>
        </label>
        <label>
          {UI.severity}
          <select
            value={filters.severity}
            onChange={(event) => update("severity", event.target.value as AuditSeverityFilter)}
            aria-label="심각도 필터"
          >
            {SEVERITY_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {formatSeverityLabel(option)}
              </option>
            ))}
          </select>
        </label>
        <label>
          {UI.area}
          <select
            value={filters.area}
            onChange={(event) => update("area", event.target.value)}
            aria-label="영역 필터"
          >
            <option value="ALL">{UI.all}</option>
            {AUDIT_AREAS.map((area) => (
              <option key={area} value={area}>
                {formatAreaLabel(area)}
              </option>
            ))}
          </select>
        </label>
        <label>
          {UI.target}
          <input
            type="search"
            value={filters.targetId}
            onChange={(event) => update("targetId", event.target.value)}
            placeholder="대상 ID"
            aria-label="대상 필터"
          />
        </label>
        <label>
          {UI.alert}
          <input
            type="search"
            value={filters.alertId}
            onChange={(event) => update("alertId", event.target.value)}
            placeholder="알림 ID"
            aria-label="알림 필터"
          />
        </label>
        <label>
          {UI.search}
          <input
            type="search"
            value={filters.search}
            onChange={(event) => update("search", event.target.value)}
            placeholder="이벤트 ID, 메시지, 요약..."
            aria-label="감사 로그 검색"
          />
        </label>
        <label>
          정렬
          <select
            value={filters.sort}
            onChange={(event) => update("sort", event.target.value as AuditSortOption)}
            aria-label="정렬 순서"
          >
            {SORT_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {formatSortLabel(option)}
              </option>
            ))}
          </select>
        </label>
        <label className="checkbox-field">
          <input
            type="checkbox"
            checked={filters.failuresOnly}
            onChange={(event) => update("failuresOnly", event.target.checked)}
          />
          {UI.failuresOnly}
        </label>
        <label className="checkbox-field">
          <input
            type="checkbox"
            checked={filters.recentOnly}
            onChange={(event) => update("recentOnly", event.target.checked)}
          />
          {UI.recent}
        </label>
      </div>
    </section>
  );
}
