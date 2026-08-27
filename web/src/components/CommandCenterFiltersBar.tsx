import type { CommandCenterFilterState } from "../utils/commandCenterFilters";
import { INVESTIGATION_AREAS } from "../utils/investigationFilters";
import { UI, formatAreaLabel, formatSeverityLabel } from "../utils/uiLabels";

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
        <h3>{UI.viewControls}</h3>
      </header>
      <div className="filters-grid">
        <label>
          {UI.area}
          <select
            value={filters.area}
            onChange={(event) => update("area", event.target.value)}
            aria-label="영역 필터"
          >
            <option value="ALL">{UI.all}</option>
            {INVESTIGATION_AREAS.map((area) => (
              <option key={area} value={area}>
                {formatAreaLabel(area)}
              </option>
            ))}
          </select>
        </label>
        <label>
          {UI.severity}
          <select
            value={filters.severity}
            onChange={(event) => update("severity", event.target.value)}
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
          {UI.search}
          <input
            type="search"
            value={filters.search}
            onChange={(event) => update("search", event.target.value)}
            placeholder="발견 코드, 메시지, 대상..."
            aria-label="운영 센터 검색"
          />
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
