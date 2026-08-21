import type { CommandCenterFilterState } from "../utils/commandCenterFilters";
import { INVESTIGATION_AREAS } from "../utils/investigationFilters";

interface CommandCenterFiltersBarProps {
  filters: CommandCenterFilterState;
  onChange: (next: CommandCenterFilterState) => void;
}

const SEVERITY_OPTIONS = ["ALL", "CRITICAL", "ERROR", "WARNING", "INFO"];

export function CommandCenterFiltersBar({ filters, onChange }: CommandCenterFiltersBarProps) {
  function update<K extends keyof CommandCenterFilterState>(
    key: K,
    value: CommandCenterFilterState[K],
  ) {
    onChange({ ...filters, [key]: value });
  }

  return (
    <section className="section-card investigation-filters command-center-filters">
      <header>
        <h3>View Controls</h3>
      </header>
      <div className="filters-grid">
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
          Severity
          <select
            value={filters.severity}
            onChange={(event) => update("severity", event.target.value)}
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
          Search
          <input
            type="search"
            value={filters.search}
            onChange={(event) => update("search", event.target.value)}
            placeholder="finding code, message, target..."
            aria-label="Command center search"
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
