import { useMemo, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { parseExecutionResponse } from "../api/executionValidation";
import { ApiError } from "../api/operationsApi";
import type { ExecutionHistoryEntry } from "../api/types";
import { ExecutionFiltersBar } from "../components/ExecutionFiltersBar";
import { ExecutionHistoryCard } from "../components/ExecutionHistoryCard";
import { ExecutionHistoryDetailPanel } from "../components/ExecutionHistoryDetailPanel";
import { HealthBadge, QueryState } from "../components/HealthBadge";
import { ExecutionLoadingSkeleton } from "../components/LoadingSkeleton";
import { getRefreshIntervalMs, useOperationsQuery } from "../hooks/useOperationsQuery";
import {
  DEFAULT_EXECUTION_FILTERS,
  applyExecutionFilters,
  flattenExecutionEntries,
} from "../utils/executionFilters";
import { UI, formatExecutionStatusLabel, formatHealthLabel } from "../utils/uiLabels";

function executionErrorMessage(status: string, fallback: string | null): string | null {
  if (status === "unauthorized") {
    return "인증이 필요합니다.";
  }
  if (status === "forbidden") {
    return "실행 이력 정보를 볼 권한이 없습니다.";
  }
  if (status === "error") {
    return "실행 이력 정보를 불러오지 못했습니다.";
  }
  return fallback;
}

export function ExecutionPage() {
  const { user, operationsApi } = useAuth();
  const enabled = Boolean(user);
  const [filters, setFilters] = useState(DEFAULT_EXECUTION_FILTERS);
  const [selectedEntry, setSelectedEntry] = useState<ExecutionHistoryEntry | null>(null);

  const fetchExecution = useMemo(
    () => async () => {
      const raw = await operationsApi.getExecution();
      const parsed = parseExecutionResponse(raw);
      if (!parsed) {
        throw new ApiError(500, "실행 이력 정보를 불러오지 못했습니다.");
      }
      return parsed;
    },
    [operationsApi],
  );

  const { data, status, errorMessage, refresh } = useOperationsQuery({
    enabled,
    fetcher: fetchExecution,
    refreshMs: getRefreshIntervalMs(),
  });

  const filteredEntries = useMemo(
    () => (data ? applyExecutionFilters(data.entries, filters) : []),
    [data, filters],
  );

  const allEntries = useMemo(
    () => (data ? flattenExecutionEntries(data.entries) : []),
    [data],
  );

  if ((status === "loading" || status === "idle") && !data) {
    return <ExecutionLoadingSkeleton />;
  }

  if (status !== "success" || !data) {
    return (
      <QueryState
        status={status}
        message={executionErrorMessage(status, errorMessage)}
        onRetry={() => void refresh()}
      />
    );
  }

  return (
    <div className="page-stack execution-page">
      <div className="page-header">
        <div>
          <h2>PriceBrain {UI.executionHistory}</h2>
          <p className="muted">
            {UI.generatedAt} {data.generated_at}
          </p>
        </div>
        <button type="button" onClick={() => void refresh()}>
          {UI.refresh}
        </button>
      </div>

      <div className="summary-grid">
        <HealthBadge label={formatHealthLabel("실행")} status={data.health} />
        <div className="summary-count-card execution-status-planned">
          <span>{formatExecutionStatusLabel("PLANNED")}</span>
          <strong>{data.summary.planned}</strong>
        </div>
        <div className="summary-count-card execution-status-dry_run">
          <span>{formatExecutionStatusLabel("DRY_RUN")}</span>
          <strong>{data.summary.dry_run}</strong>
        </div>
        <div className="summary-count-card execution-status-executed">
          <span>{formatExecutionStatusLabel("EXECUTED")}</span>
          <strong>{data.summary.executed}</strong>
        </div>
        <div className="summary-count-card execution-status-blocked">
          <span>{formatExecutionStatusLabel("BLOCKED")}</span>
          <strong>{data.summary.blocked}</strong>
        </div>
        <div className="summary-count-card execution-status-failed">
          <span>{formatExecutionStatusLabel("FAILED")}</span>
          <strong>{data.summary.failed}</strong>
        </div>
      </div>

      <div className="section-card">
        <header>
          <h3>{UI.summary}</h3>
        </header>
        <ul className="metric-list">
          <li>
            <span>전체 실행</span>
            <span>{data.summary.total}</span>
          </li>
          <li>
            <span>최근 실패</span>
            <span>{data.summary.recent_failures}</span>
          </li>
          <li>
            <span>승인 실패</span>
            <span>{data.summary.approval_failures}</span>
          </li>
          <li>
            <span>변경 수행</span>
            <span>{data.summary.mutation_count}</span>
          </li>
          <li>
            <span>읽기 오류</span>
            <span>{data.summary.read_errors}</span>
          </li>
        </ul>
        {data.health_reasons.length > 0 ? (
          <p className="muted">실행 상태 사유: {data.health_reasons.join(", ")}</p>
        ) : null}
      </div>

      <ExecutionFiltersBar filters={filters} onChange={setFilters} />

      <div className="investigation-layout">
        <div className="findings-list">
          {filteredEntries.length === 0 ? (
            <div className="query-state">
              {allEntries.length === 0
                ? "현재 기록된 실행 이력이 없습니다."
                : "선택한 필터 조건에 맞는 실행 항목이 없습니다."}
            </div>
          ) : (
            filteredEntries.map((entry) => (
              <ExecutionHistoryCard
                key={entry.execution_id}
                entry={entry}
                selected={selectedEntry?.execution_id === entry.execution_id}
                onSelect={setSelectedEntry}
              />
            ))
          )}
        </div>
        <ExecutionHistoryDetailPanel
          entry={selectedEntry}
          onClose={() => setSelectedEntry(null)}
        />
      </div>
    </div>
  );
}
