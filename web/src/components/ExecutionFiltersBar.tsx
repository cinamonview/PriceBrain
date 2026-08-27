import type {
  ExecutionFilterState,
  ExecutionModeFilter,
  ExecutionSortOption,
  ExecutionStatusFilter,
} from "../utils/executionFilters";
import { EXECUTION_AREAS } from "../utils/executionFilters";
import {
  UI,
  formatAreaLabel,
  formatExecutionStatusLabel,
  formatModeLabel,
  formatSortLabel,
} from "../utils/uiLabels";

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

function formatStatusFilterLabel(option: ExecutionStatusFilter): string {
  return option === "ALL" ? UI.all : formatExecutionStatusLabel(option);
}

function formatModeFilterLabel(option: ExecutionModeFilter): string {
  return option === "ALL" ? UI.all : formatModeLabel(option);
}

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
        <h3>{UI.filters}</h3>
      </header>
      <div className="filters-grid">
        <label>
          {UI.status}
          <select
            value={filters.status}
            onChange={(event) => update("status", event.target.value as ExecutionStatusFilter)}
            aria-label="상태 필터"
          >
            {STATUS_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {formatStatusFilterLabel(option)}
              </option>
            ))}
          </select>
        </label>
        <label>
          실행 모드
          <select
            value={filters.mode}
            onChange={(event) => update("mode", event.target.value as ExecutionModeFilter)}
            aria-label="실행 모드 필터"
          >
            {MODE_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {formatModeFilterLabel(option)}
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
            {EXECUTION_AREAS.map((area) => (
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
            placeholder="실행 ID, 조치 ID, 메시지..."
            aria-label="실행 이력 검색"
          />
        </label>
        <label>
          정렬
          <select
            value={filters.sort}
            onChange={(event) => update("sort", event.target.value as ExecutionSortOption)}
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
