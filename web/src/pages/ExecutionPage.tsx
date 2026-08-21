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

function executionErrorMessage(status: string, fallback: string | null): string | null {
  if (status === "unauthorized") {
    return "인증이 필요합니다.";
  }
  if (status === "forbidden") {
    return "Execution 정보를 볼 권한이 없습니다.";
  }
  if (status === "error") {
    return "Execution 정보를 불러오지 못했습니다.";
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
        throw new ApiError(500, "Execution 정보를 불러오지 못했습니다.");
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
          <h2>PriceBrain Execution History</h2>
          <p className="muted">Generated at {data.generated_at}</p>
        </div>
        <button type="button" onClick={() => void refresh()}>
          Refresh
        </button>
      </div>

      <div className="summary-grid">
        <HealthBadge label="Execution Health" status={data.health} />
        <div className="summary-count-card execution-status-planned">
          <span>PLANNED</span>
          <strong>{data.summary.planned}</strong>
        </div>
        <div className="summary-count-card execution-status-dry_run">
          <span>DRY_RUN</span>
          <strong>{data.summary.dry_run}</strong>
        </div>
        <div className="summary-count-card execution-status-executed">
          <span>EXECUTED</span>
          <strong>{data.summary.executed}</strong>
        </div>
        <div className="summary-count-card execution-status-blocked">
          <span>BLOCKED</span>
          <strong>{data.summary.blocked}</strong>
        </div>
        <div className="summary-count-card execution-status-failed">
          <span>FAILED</span>
          <strong>{data.summary.failed}</strong>
        </div>
      </div>

      <div className="section-card">
        <header>
          <h3>Summary</h3>
        </header>
        <ul className="metric-list">
          <li>
            <span>Total executions</span>
            <span>{data.summary.total}</span>
          </li>
          <li>
            <span>Recent failures</span>
            <span>{data.summary.recent_failures}</span>
          </li>
          <li>
            <span>Approval failures</span>
            <span>{data.summary.approval_failures}</span>
          </li>
          <li>
            <span>Mutations performed</span>
            <span>{data.summary.mutation_count}</span>
          </li>
          <li>
            <span>Read errors</span>
            <span>{data.summary.read_errors}</span>
          </li>
        </ul>
        {data.health_reasons.length > 0 ? (
          <p className="muted">Execution health reasons: {data.health_reasons.join(", ")}</p>
        ) : null}
      </div>

      <ExecutionFiltersBar filters={filters} onChange={setFilters} />

      <div className="investigation-layout">
        <div className="findings-list">
          {filteredEntries.length === 0 ? (
            <div className="query-state">
              {allEntries.length === 0
                ? "현재 기록된 execution history가 없습니다."
                : "선택한 filter 조건에 맞는 execution entry가 없습니다."}
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
