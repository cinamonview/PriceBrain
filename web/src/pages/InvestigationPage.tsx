import { useMemo, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { parseInvestigationResponse } from "../api/investigationValidation";
import { ApiError } from "../api/operationsApi";
import type { InvestigationFinding } from "../api/types";
import { FindingCard } from "../components/FindingCard";
import { FindingDetailPanel } from "../components/FindingDetailPanel";
import { HealthBadge, QueryState } from "../components/HealthBadge";
import { InvestigationFiltersBar } from "../components/InvestigationFiltersBar";
import { InvestigationLoadingSkeleton } from "../components/LoadingSkeleton";
import { getRefreshIntervalMs, useOperationsQuery } from "../hooks/useOperationsQuery";
import {
  DEFAULT_INVESTIGATION_FILTERS,
  filterInvestigationFindings,
} from "../utils/investigationFilters";

function investigationErrorMessage(status: string, fallback: string | null): string | null {
  if (status === "unauthorized") {
    return "인증이 필요합니다.";
  }
  if (status === "forbidden") {
    return "Investigation 정보를 볼 권한이 없습니다.";
  }
  if (status === "error") {
    return "Investigation 정보를 불러오지 못했습니다.";
  }
  return fallback;
}

export function InvestigationPage() {
  const { user, operationsApi } = useAuth();
  const enabled = Boolean(user);
  const [filters, setFilters] = useState(DEFAULT_INVESTIGATION_FILTERS);
  const [selectedFinding, setSelectedFinding] = useState<InvestigationFinding | null>(null);

  const fetchInvestigation = useMemo(
    () => async () => {
      const raw = await operationsApi.getInvestigation();
      const parsed = parseInvestigationResponse(raw);
      if (!parsed) {
        throw new ApiError(500, "Investigation 정보를 불러오지 못했습니다.");
      }
      return parsed;
    },
    [operationsApi],
  );

  const { data, status, errorMessage, refresh } = useOperationsQuery({
    enabled,
    fetcher: fetchInvestigation,
    refreshMs: getRefreshIntervalMs(),
  });

  const filteredFindings = useMemo(
    () => (data ? filterInvestigationFindings(data.findings, filters) : []),
    [data, filters],
  );

  if ((status === "loading" || status === "idle") && !data) {
    return <InvestigationLoadingSkeleton />;
  }

  if (status !== "success" || !data) {
    return (
      <QueryState
        status={status}
        message={investigationErrorMessage(status, errorMessage)}
        onRetry={() => void refresh()}
      />
    );
  }

  return (
    <div className="page-stack investigation-page">
      <div className="page-header">
        <div>
          <h2>PriceBrain Investigation</h2>
          <p className="muted">Generated at {data.generated_at}</p>
        </div>
        <button type="button" onClick={() => void refresh()}>
          Refresh
        </button>
      </div>

      <div className="summary-grid">
        <HealthBadge label="Investigation Health" status={data.health} />
        <div className="summary-count-card severity-critical">
          <span>CRITICAL</span>
          <strong>{data.summary.critical_count}</strong>
        </div>
        <div className="summary-count-card severity-error">
          <span>ERROR</span>
          <strong>{data.summary.error_count}</strong>
        </div>
        <div className="summary-count-card severity-warning">
          <span>WARNING</span>
          <strong>{data.summary.warning_count}</strong>
        </div>
        <div className="summary-count-card severity-info">
          <span>INFO</span>
          <strong>{data.summary.info_count}</strong>
        </div>
      </div>

      <div className="section-card">
        <header>
          <h3>Summary</h3>
        </header>
        <ul className="metric-list">
          <li>
            <span>Total findings</span>
            <span>{data.summary.total_findings}</span>
          </li>
          <li>
            <span>Read errors</span>
            <span>{data.summary.read_errors}</span>
          </li>
        </ul>
      </div>

      <InvestigationFiltersBar filters={filters} onChange={setFilters} />

      <div className="investigation-layout">
        <div className="findings-list">
          {filteredFindings.length === 0 ? (
            <div className="query-state">
              {data.findings.length === 0
                ? "현재 확인이 필요한 운영 이슈가 없습니다."
                : "선택한 filter 조건에 맞는 finding이 없습니다."}
            </div>
          ) : (
            filteredFindings.map((finding) => (
              <FindingCard
                key={finding.finding_id}
                finding={finding}
                selected={selectedFinding?.finding_id === finding.finding_id}
                onSelect={setSelectedFinding}
              />
            ))
          )}
        </div>
        <FindingDetailPanel finding={selectedFinding} onClose={() => setSelectedFinding(null)} />
      </div>
    </div>
  );
}
