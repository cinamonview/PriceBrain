import type { InvestigationFilterState, SeverityFilter } from "../utils/investigationFilters";
import { INVESTIGATION_AREAS } from "../utils/investigationFilters";

interface InvestigationFiltersBarProps {
  filters: InvestigationFilterState;
  onChange: (next: InvestigationFilterState) => void;
}

const SEVERITY_OPTIONS: SeverityFilter[] = ["ALL", "CRITICAL", "ERROR", "WARNING", "INFO"];

export function InvestigationFiltersBar({ filters, onChange }: InvestigationFiltersBarProps) {
  function update<K extends keyof InvestigationFilterState>(key: K, value: InvestigationFilterState[K]) {
    onChange({ ...filters, [key]: value });
  }

  return (
    <section className="section-card investigation-filters">
      <header>
        <h3>Filters</h3>
      </header>
      <div className="filters-grid">
        <label>
          Severity
          <select
            value={filters.severity}
            onChange={(event) => update("severity", event.target.value as SeverityFilter)}
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
            {INVESTIGATION_AREAS.map((area) => (
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
            placeholder="code, title, message..."
            aria-label="Finding search"
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
