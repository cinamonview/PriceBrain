import type {
  ExecutionFilterState,
  ExecutionModeFilter,
  ExecutionSortOption,
  ExecutionStatusFilter,
} from "../utils/executionFilters";
import { EXECUTION_AREAS } from "../utils/executionFilters";

interface ExecutionFiltersBarProps {
  filters: ExecutionFilterState;
  onChange: (next: ExecutionFilterState) => void;
}

const STATUS_OPTIONS: ExecutionStatusFilter[] = [
  "ALL",
  "PLANNED",
  "DRY_RUN",
  "EXECUTED",
  "BLOCKED",
  "FAILED",
  "APPROVED",
  "SKIPPED",
  "UNKNOWN",
];

const MODE_OPTIONS: ExecutionModeFilter[] = ["ALL", "PLAN", "DRY_RUN", "EXECUTE"];

const SORT_OPTIONS: ExecutionSortOption[] = ["NEWEST", "OLDEST", "STATUS", "DURATION"];

export function ExecutionFiltersBar({ filters, onChange }: ExecutionFiltersBarProps) {
  function update<K extends keyof ExecutionFilterState>(
    key: K,
    value: ExecutionFilterState[K],
  ) {
    onChange({ ...filters, [key]: value });
  }

  return (
    <section className="section-card investigation-filters">
      <header>
        <h3>Filters</h3>
      </header>
      <div className="filters-grid">
        <label>
          Status
          <select
            value={filters.status}
            onChange={(event) => update("status", event.target.value as ExecutionStatusFilter)}
            aria-label="Status filter"
          >
            {STATUS_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>
        <label>
          Mode
          <select
            value={filters.mode}
            onChange={(event) => update("mode", event.target.value as ExecutionModeFilter)}
            aria-label="Mode filter"
          >
            {MODE_OPTIONS.map((option) => (
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
            {EXECUTION_AREAS.map((area) => (
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
            placeholder="execution id, action id, message..."
            aria-label="Execution search"
          />
        </label>
        <label>
          Sort
          <select
            value={filters.sort}
            onChange={(event) => update("sort", event.target.value as ExecutionSortOption)}
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
