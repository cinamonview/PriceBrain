import type { PriorityFilter, RemediationFilterState } from "../utils/remediationFilters";
import { REMEDIATION_AREAS } from "../utils/remediationFilters";
import { UI, formatAreaLabel, formatPriorityLabel } from "../utils/uiLabels";

interface RemediationFiltersBarProps {
  filters: RemediationFilterState;
  onChange: (next: RemediationFilterState) => void;
}

const PRIORITY_OPTIONS: PriorityFilter[] = ["ALL", "CRITICAL", "HIGH", "MEDIUM", "LOW"];

function formatPriorityFilterLabel(option: PriorityFilter): string {
  return option === "ALL" ? UI.all : formatPriorityLabel(option);
}

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
        <h3>{UI.filters}</h3>
      </header>
      <div className="filters-grid">
        <label>
          우선순위
          <select
            value={filters.priority}
            onChange={(event) => update("priority", event.target.value as PriorityFilter)}
            aria-label="우선순위 필터"
          >
            {PRIORITY_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {formatPriorityFilterLabel(option)}
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
            {REMEDIATION_AREAS.map((area) => (
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
            placeholder="제목, 근거, 조치 유형..."
            aria-label="조치 계획 검색"
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
