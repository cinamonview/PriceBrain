import { useMemo, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { parseAuditResponse } from "../api/auditValidation";
import { ApiError } from "../api/operationsApi";
import type { AuditEventSnapshot } from "../api/types";
import { AuditEventCard } from "../components/AuditEventCard";
import { AuditEventDetailPanel } from "../components/AuditEventDetailPanel";
import { AuditFiltersBar } from "../components/AuditFiltersBar";
import { HealthBadge, QueryState } from "../components/HealthBadge";
import { AuditLoadingSkeleton } from "../components/LoadingSkeleton";
import { getRefreshIntervalMs, useOperationsQuery } from "../hooks/useOperationsQuery";
import {
  DEFAULT_AUDIT_FILTERS,
  applyAuditFilters,
  computeAreaCounts,
  countFailureEvents,
  flattenAuditEvents,
} from "../utils/auditFilters";
import {
  UI,
  formatAreaLabel,
  formatAuditEventTypeLabel,
  formatHealthLabel,
} from "../utils/uiLabels";

function auditErrorMessage(status: string, fallback: string | null): string | null {
  if (status === "unauthorized") {
    return "인증이 필요합니다.";
  }
  if (status === "forbidden") {
    return "감사 로그 정보를 볼 권한이 없습니다.";
  }
  if (status === "error") {
    return "감사 로그 정보를 불러오지 못했습니다.";
  }
  return fallback;
}

export function AuditPage() {
  const { user, operationsApi } = useAuth();
  const enabled = Boolean(user);
  const [filters, setFilters] = useState(DEFAULT_AUDIT_FILTERS);
  const [selectedSnapshot, setSelectedSnapshot] = useState<AuditEventSnapshot | null>(null);

  const fetchAudit = useMemo(
    () => async () => {
      const raw = await operationsApi.getAudit();
      const parsed = parseAuditResponse(raw);
      if (!parsed) {
        throw new ApiError(500, "감사 로그 정보를 불러오지 못했습니다.");
      }
      return parsed;
    },
    [operationsApi],
  );

  const { data, status, errorMessage, refresh } = useOperationsQuery({
    enabled,
    fetcher: fetchAudit,
    refreshMs: getRefreshIntervalMs(),
  });

  const filteredSnapshots = useMemo(
    () => (data ? applyAuditFilters(data.events, filters) : []),
    [data, filters],
  );

  const allEvents = useMemo(
    () => (data ? flattenAuditEvents(data.events) : []),
    [data],
  );

  const areaCounts = useMemo(
    () => (data?.summary.by_area ? data.summary.by_area : computeAreaCounts(allEvents)),
    [data, allEvents],
  );

  const failureCount = useMemo(
    () => data?.summary.failure_events ?? countFailureEvents(allEvents),
    [data, allEvents],
  );

  if ((status === "loading" || status === "idle") && !data) {
    return <AuditLoadingSkeleton />;
  }

  if (status !== "success" || !data) {
    return (
      <QueryState
        status={status}
        message={auditErrorMessage(status, errorMessage)}
        onRetry={() => void refresh()}
      />
    );
  }

  return (
    <div className="page-stack audit-page">
      <div className="page-header">
        <div>
          <h2>PriceBrain {UI.audit}</h2>
          <p className="muted">
            {UI.generatedAt} {data.generated_at}
          </p>
        </div>
        <button type="button" onClick={() => void refresh()}>
          {UI.refresh}
        </button>
      </div>

      <div className="summary-grid">
        <HealthBadge label={formatHealthLabel(UI.audit)} status={data.health} />
        <div className="summary-count-card">
          <span>전체 이벤트</span>
          <strong>{data.summary.total}</strong>
        </div>
        <div className="summary-count-card">
          <span>최근 이벤트</span>
          <strong>{data.summary.recent}</strong>
        </div>
        <div className="summary-count-card execution-status-failed">
          <span>실패 이벤트</span>
          <strong>{failureCount}</strong>
        </div>
        <div className="summary-count-card">
          <span>읽기 오류</span>
          <strong>{data.summary.read_errors}</strong>
        </div>
      </div>

      <div className="section-card">
        <header>
          <h3>{UI.summary}</h3>
        </header>
        <ul className="metric-list">
          <li>
            <span>알림 이벤트</span>
            <span>{data.summary.alert_events}</span>
          </li>
          <li>
            <span>알림 전송 이벤트</span>
            <span>{data.summary.notification_events}</span>
          </li>
          <li>
            <span>실행기 이벤트</span>
            <span>{data.summary.runner_events}</span>
          </li>
        </ul>
        {Object.keys(data.summary.by_type).length > 0 ? (
          <div className="metric-subsection">
            <h4>이벤트 유형별</h4>
            <ul className="metric-list">
              {Object.entries(data.summary.by_type).map(([eventType, count]) => (
                <li key={eventType}>
                  <span>{formatAuditEventTypeLabel(eventType)}</span>
                  <span>{count}</span>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
        {Object.keys(areaCounts).length > 0 ? (
          <div className="metric-subsection">
            <h4>영역별</h4>
            <ul className="metric-list">
              {Object.entries(areaCounts).map(([area, count]) => (
                <li key={area}>
                  <span>{formatAreaLabel(area)}</span>
                  <span>{count}</span>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
        {data.health_reasons.length > 0 ? (
          <p className="muted">감사 로그 상태 사유: {data.health_reasons.join(", ")}</p>
        ) : null}
      </div>

      <AuditFiltersBar filters={filters} onChange={setFilters} />

      <div className="investigation-layout">
        <div className="findings-list">
          {filteredSnapshots.length === 0 ? (
            <div className="query-state">
              {data.events.length === 0
                ? "현재 기록된 감사 이벤트가 없습니다."
                : "선택한 필터 조건에 맞는 감사 이벤트가 없습니다."}
            </div>
          ) : (
            filteredSnapshots.map((snapshot) => (
              <AuditEventCard
                key={snapshot.event?.event_id ?? snapshot.read_error ?? snapshot.summary}
                snapshot={snapshot}
                selected={
                  selectedSnapshot?.event?.event_id === snapshot.event?.event_id &&
                  selectedSnapshot?.read_error === snapshot.read_error
                }
                onSelect={setSelectedSnapshot}
              />
            ))
          )}
        </div>
        <AuditEventDetailPanel snapshot={selectedSnapshot} onClose={() => setSelectedSnapshot(null)} />
      </div>
    </div>
  );
}
