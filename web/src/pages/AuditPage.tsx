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

function auditErrorMessage(status: string, fallback: string | null): string | null {
  if (status === "unauthorized") {
    return "인증이 필요합니다.";
  }
  if (status === "forbidden") {
    return "Audit 정보를 볼 권한이 없습니다.";
  }
  if (status === "error") {
    return "Audit 정보를 불러오지 못했습니다.";
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
        throw new ApiError(500, "Audit 정보를 불러오지 못했습니다.");
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
          <h2>PriceBrain Audit Events</h2>
          <p className="muted">Generated at {data.generated_at}</p>
        </div>
        <button type="button" onClick={() => void refresh()}>
          Refresh
        </button>
      </div>

      <div className="summary-grid">
        <HealthBadge label="Audit Health" status={data.health} />
        <div className="summary-count-card">
          <span>Total Events</span>
          <strong>{data.summary.total}</strong>
        </div>
        <div className="summary-count-card">
          <span>Recent Events</span>
          <strong>{data.summary.recent}</strong>
        </div>
        <div className="summary-count-card execution-status-failed">
          <span>Failure Events</span>
          <strong>{failureCount}</strong>
        </div>
        <div className="summary-count-card">
          <span>Read Errors</span>
          <strong>{data.summary.read_errors}</strong>
        </div>
      </div>

      <div className="section-card">
        <header>
          <h3>Summary</h3>
        </header>
        <ul className="metric-list">
          <li>
            <span>Alert events</span>
            <span>{data.summary.alert_events}</span>
          </li>
          <li>
            <span>Notification events</span>
            <span>{data.summary.notification_events}</span>
          </li>
          <li>
            <span>Runner events</span>
            <span>{data.summary.runner_events}</span>
          </li>
        </ul>
        {Object.keys(data.summary.by_type).length > 0 ? (
          <div className="metric-subsection">
            <h4>By Event Type</h4>
            <ul className="metric-list">
              {Object.entries(data.summary.by_type).map(([eventType, count]) => (
                <li key={eventType}>
                  <span>{eventType}</span>
                  <span>{count}</span>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
        {Object.keys(areaCounts).length > 0 ? (
          <div className="metric-subsection">
            <h4>By Area</h4>
            <ul className="metric-list">
              {Object.entries(areaCounts).map(([area, count]) => (
                <li key={area}>
                  <span>{area}</span>
                  <span>{count}</span>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
        {data.health_reasons.length > 0 ? (
          <p className="muted">Audit health reasons: {data.health_reasons.join(", ")}</p>
        ) : null}
      </div>

      <AuditFiltersBar filters={filters} onChange={setFilters} />

      <div className="investigation-layout">
        <div className="findings-list">
          {filteredSnapshots.length === 0 ? (
            <div className="query-state">
              {data.events.length === 0
                ? "현재 기록된 audit event가 없습니다."
                : "선택한 filter 조건에 맞는 audit event가 없습니다."}
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
