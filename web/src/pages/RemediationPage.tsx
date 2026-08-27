import { useMemo, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { parseRemediationPlanResponse } from "../api/remediationValidation";
import { ApiError } from "../api/operationsApi";
import type { RemediationAction } from "../api/types";
import { HealthBadge, QueryState } from "../components/HealthBadge";
import { RemediationLoadingSkeleton } from "../components/LoadingSkeleton";
import { RemediationActionCard } from "../components/RemediationActionCard";
import { RemediationActionDetailPanel } from "../components/RemediationActionDetailPanel";
import { RemediationFiltersBar } from "../components/RemediationFiltersBar";
import { getRefreshIntervalMs, useOperationsQuery } from "../hooks/useOperationsQuery";
import {
  DEFAULT_REMEDIATION_FILTERS,
  filterRemediationActions,
  priorityCount,
} from "../utils/remediationFilters";
import {
  UI,
  formatHealthLabel,
  formatPriorityLabel,
  formatYesNo,
} from "../utils/uiLabels";

function remediationErrorMessage(status: string, fallback: string | null): string | null {
  if (status === "unauthorized") {
    return "인증이 필요합니다.";
  }
  if (status === "forbidden") {
    return "조치 계획 정보를 볼 권한이 없습니다.";
  }
  if (status === "error") {
    return "조치 계획 정보를 불러오지 못했습니다.";
  }
  return fallback;
}

export function RemediationPage() {
  const { user, operationsApi } = useAuth();
  const enabled = Boolean(user);
  const [filters, setFilters] = useState(DEFAULT_REMEDIATION_FILTERS);
  const [selectedAction, setSelectedAction] = useState<RemediationAction | null>(null);

  const fetchRemediation = useMemo(
    () => async () => {
      const raw = await operationsApi.getRemediation();
      const parsed = parseRemediationPlanResponse(raw);
      if (!parsed) {
        throw new ApiError(500, "조치 계획 정보를 불러오지 못했습니다.");
      }
      return parsed;
    },
    [operationsApi],
  );

  const { data, status, errorMessage, refresh } = useOperationsQuery({
    enabled,
    fetcher: fetchRemediation,
    refreshMs: getRefreshIntervalMs(),
  });

  const filteredActions = useMemo(
    () => (data ? filterRemediationActions(data.actions, filters) : []),
    [data, filters],
  );

  const autoExecutableCount = data?.actions.filter((action) => action.auto_executable).length ?? 0;
  const approvalRequiredCount =
    data?.actions.filter((action) => action.human_approval_required).length ?? 0;

  if ((status === "loading" || status === "idle") && !data) {
    return <RemediationLoadingSkeleton />;
  }

  if (status !== "success" || !data) {
    return (
      <QueryState
        status={status}
        message={remediationErrorMessage(status, errorMessage)}
        onRetry={() => void refresh()}
      />
    );
  }

  return (
    <div className="page-stack remediation-page">
      <div className="page-header">
        <div>
          <h2>PriceBrain {UI.remediation}</h2>
          <p className="muted">
            {UI.generatedAt} {data.generated_at}
          </p>
        </div>
        <button type="button" onClick={() => void refresh()}>
          {UI.refresh}
        </button>
      </div>

      <div className="policy-banner remediation-policy">
        <strong>{UI.planOnly}</strong>
        <span>{UI.humanApprovalRequired}</span>
        <span>{UI.autoExecutionDisabled}</span>
      </div>

      <div className="summary-grid">
        <HealthBadge label={formatHealthLabel(UI.remediation)} status={data.health} />
        <div className="summary-count-card priority-high">
          <span>{formatPriorityLabel("HIGH")}</span>
          <strong>{priorityCount(data.summary.by_priority, "HIGH")}</strong>
        </div>
        <div className="summary-count-card priority-medium">
          <span>{formatPriorityLabel("MEDIUM")}</span>
          <strong>{priorityCount(data.summary.by_priority, "MEDIUM")}</strong>
        </div>
        <div className="summary-count-card priority-low">
          <span>{formatPriorityLabel("LOW")}</span>
          <strong>{priorityCount(data.summary.by_priority, "LOW")}</strong>
        </div>
      </div>

      <div className="section-card">
        <header>
          <h3>{UI.summary}</h3>
        </header>
        <ul className="metric-list">
          <li>
            <span>전체 조치</span>
            <span>{data.summary.total_actions}</span>
          </li>
          <li>
            <span>실행 가능 조치</span>
            <span>{data.summary.actionable_actions}</span>
          </li>
          <li>
            <span>{UI.humanApprovalRequired}</span>
            <span>{formatYesNo(approvalRequiredCount > 0)}</span>
          </li>
          <li>
            <span>자동 실행 가능</span>
            <span>
              {autoExecutableCount > 0 ? `${autoExecutableCount}${UI.flagged}` : formatYesNo(false)}
            </span>
          </li>
          <li>
            <span>읽기 오류</span>
            <span>{data.summary.read_errors}</span>
          </li>
        </ul>
      </div>

      <RemediationFiltersBar filters={filters} onChange={setFilters} />

      <div className="investigation-layout">
        <div className="findings-list">
          {filteredActions.length === 0 ? (
            <div className="query-state">
              {data.actions.length === 0
                ? "현재 제안된 조치가 없습니다."
                : "선택한 필터 조건에 맞는 조치가 없습니다."}
            </div>
          ) : (
            filteredActions.map((action) => (
              <RemediationActionCard
                key={action.action_id}
                action={action}
                selected={selectedAction?.action_id === action.action_id}
                onSelect={setSelectedAction}
              />
            ))
          )}
        </div>
        <RemediationActionDetailPanel
          action={selectedAction}
          onClose={() => setSelectedAction(null)}
        />
      </div>
    </div>
  );
}
