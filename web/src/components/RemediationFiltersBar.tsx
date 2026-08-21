import type { PriorityFilter, RemediationFilterState } from "../utils/remediationFilters";
import { REMEDIATION_AREAS } from "../utils/remediationFilters";

interface RemediationFiltersBarProps {
  filters: RemediationFilterState;
  onChange: (next: RemediationFilterState) => void;
}

const PRIORITY_OPTIONS: PriorityFilter[] = ["ALL", "CRITICAL", "HIGH", "MEDIUM", "LOW"];

export function RemediationFiltersBar({ filters, onChange }: RemediationFiltersBarProps) {
  function update<K extends keyof RemediationFilterState>(
    key: K,
    value: RemediationFilterState[K],
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
          Priority
          <select
            value={filters.priority}
            onChange={(event) => update("priority", event.target.value as PriorityFilter)}
            aria-label="Priority filter"
          >
            {PRIORITY_OPTIONS.map((option) => (
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
            {REMEDIATION_AREAS.map((area) => (
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
            placeholder="title, reason, action type..."
            aria-label="Remediation search"
          />
        </label>
        <label className="checkbox-field">
          <input
            type="checkbox"
            checked={filters.failuresOnly}
            onChange={(event) => update("failuresOnly", event.target.checked)}
          />
          failures only
        </label>
      </div>
    </section>
  );
}
