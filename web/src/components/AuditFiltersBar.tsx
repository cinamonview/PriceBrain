import type {
  AuditEventTypeFilter,
  AuditFilterState,
  AuditSeverityFilter,
  AuditSortOption,
} from "../utils/auditFilters";
import { AUDIT_AREAS } from "../utils/auditFilters";

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

export function AuditFiltersBar({ filters, onChange }: AuditFiltersBarProps) {
  function update<K extends keyof AuditFilterState>(key: K, value: AuditFilterState[K]) {
    onChange({ ...filters, [key]: value });
  }

  return (
    <section className="section-card investigation-filters">
      <header>
        <h3>Filters</h3>
      </header>
      <div className="filters-grid">
        <label>
          Event Type
          <select
            value={filters.eventType}
            onChange={(event) => update("eventType", event.target.value as AuditEventTypeFilter)}
            aria-label="Event type filter"
          >
            {EVENT_TYPE_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>
        <label>
          Severity
          <select
            value={filters.severity}
            onChange={(event) => update("severity", event.target.value as AuditSeverityFilter)}
            aria-label="Severity filter"
          >
            {SEVERITY_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>
        <label>
          Area
          <select
            value={filters.area}
            onChange={(event) => update("area", event.target.value)}
            aria-label="Area filter"
          >
            <option value="ALL">All</option>
            {AUDIT_AREAS.map((area) => (
              <option key={area} value={area}>
                {area.charAt(0).toUpperCase() + area.slice(1)}
              </option>
            ))}
          </select>
        </label>
        <label>
          Target
          <input
            type="search"
            value={filters.targetId}
            onChange={(event) => update("targetId", event.target.value)}
            placeholder="target id"
            aria-label="Target filter"
          />
        </label>
        <label>
          Alert
          <input
            type="search"
            value={filters.alertId}
            onChange={(event) => update("alertId", event.target.value)}
            placeholder="alert id"
            aria-label="Alert filter"
          />
        </label>
        <label>
          Search
          <input
            type="search"
            value={filters.search}
            onChange={(event) => update("search", event.target.value)}
            placeholder="event id, message, summary..."
            aria-label="Audit search"
          />
        </label>
        <label>
          Sort
          <select
            value={filters.sort}
            onChange={(event) => update("sort", event.target.value as AuditSortOption)}
            aria-label="Sort order"
          >
            {SORT_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {option}
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
          failures only
        </label>
        <label className="checkbox-field">
          <input
            type="checkbox"
            checked={filters.recentOnly}
            onChange={(event) => update("recentOnly", event.target.checked)}
          />
          recent
        </label>
      </div>
    </section>
  );
}
