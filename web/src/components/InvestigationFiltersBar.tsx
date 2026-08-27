import type { InvestigationFilterState, SeverityFilter } from "../utils/investigationFilters";
import { INVESTIGATION_AREAS } from "../utils/investigationFilters";
import { UI, formatAreaLabel, formatSeverityLabel } from "../utils/uiLabels";

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
        <h3>{UI.filters}</h3>
      </header>
      <div className="filters-grid">
        <label>
          {UI.severity}
          <select
            value={filters.severity}
            onChange={(event) => update("severity", event.target.value as SeverityFilter)}
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
            {INVESTIGATION_AREAS.map((area) => (
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
            placeholder="코드, 제목, 메시지..."
            aria-label="조사 검색"
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
      </div>
    </section>
  );
}
