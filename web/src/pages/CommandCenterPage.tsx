import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { parseCommandCenterResponse } from "../api/commandCenterValidation";
import { ApiError } from "../api/operationsApi";
import { CommandCenterAreaCard } from "../components/CommandCenterAreaCard";
import { CommandCenterFailurePanel } from "../components/CommandCenterFailurePanel";
import { CommandCenterFiltersBar } from "../components/CommandCenterFiltersBar";
import { CommandCenterOverview } from "../components/CommandCenterOverview";
import { AuditEventTypeBadge } from "../components/AuditEventTypeBadge";
import { QueryState } from "../components/HealthBadge";
import { CommandCenterLoadingSkeleton } from "../components/LoadingSkeleton";
import { PriorityBadge } from "../components/PriorityBadge";
import { ResourceRef } from "../components/ResourceRef";
import { SeverityBadge } from "../components/SeverityBadge";
import { ExecutionStatusBadge } from "../components/ExecutionStatusBadge";
import { getRefreshIntervalMs, useOperationsQuery } from "../hooks/useOperationsQuery";
import { deriveAuditSeverity } from "../utils/auditFilters";
import {
  DEFAULT_COMMAND_CENTER_FILTERS,
  countOperationalFailures,
  countReadErrors,
  filterAuditEventsForCommandCenter,
  filterFindings,
  getRecentAuditEvents,
  groupFindingsBySeverity,
  topRemediationActions,
} from "../utils/commandCenterFilters";
import { UI, formatExecutionStatusLabel, formatYesNo } from "../utils/uiLabels";

function commandCenterErrorMessage(status: string, fallback: string | null): string | null {
  if (status === "unauthorized") {
    return "인증이 필요합니다.";
  }
  if (status === "forbidden") {
    return "운영 센터 정보를 볼 권한이 없습니다.";
  }
  if (status === "error") {
    return "운영 센터 정보를 불러오지 못했습니다.";
  }
  return fallback;
}

export function CommandCenterPage() {
  const { user, operationsApi } = useAuth();
  const enabled = Boolean(user);
  const [filters, setFilters] = useState(DEFAULT_COMMAND_CENTER_FILTERS);
  const [lastRefreshedAt, setLastRefreshedAt] = useState<string | null>(null);
  const refreshIntervalMs = getRefreshIntervalMs();

  const fetchCommandCenter = useMemo(
    () => async () => {
      const raw = await operationsApi.getCommandCenter();
      const parsed = parseCommandCenterResponse(raw);
      if (!parsed) {
        throw new ApiError(500, "운영 센터 정보를 불러오지 못했습니다.");
      }
      return parsed;
    },
    [operationsApi],
  );

  const { data, status, errorMessage, refresh } = useOperationsQuery({
    enabled,
    fetcher: fetchCommandCenter,
    refreshMs: refreshIntervalMs,
  });

  useEffect(() => {
    if (data) {
      setLastRefreshedAt(new Date().toISOString());
    }
  }, [data?.generated_at]);

  const filteredFindings = useMemo(
    () => (data ? filterFindings(data.investigation.findings, filters) : []),
    [data, filters],
  );
  const groupedFindings = useMemo(() => groupFindingsBySeverity(filteredFindings), [filteredFindings]);

  const auditEvents = useMemo(() => {
    if (!data) {
      return [];
    }
    const recent = getRecentAuditEvents(data, filters.recentOnly ? 5 : 8);
    return filterAuditEventsForCommandCenter(recent, filters);
  }, [data, filters]);

  const remediationActions = useMemo(
    () => (data ? topRemediationActions(data.remediation.actions, filters.recentOnly ? 3 : 5) : []),
    [data, filters.recentOnly],
  );

  const executionEntries = useMemo(() => {
    if (!data) {
      return [];
    }
    const entries = data.execution.entries
      .map((snapshot) => snapshot.entry)
      .filter((entry) => entry !== null && entry !== undefined);
    return filters.recentOnly ? entries.slice(0, 5) : entries.slice(0, 8);
  }, [data, filters.recentOnly]);

  if ((status === "loading" || status === "idle") && !data) {
    return <CommandCenterLoadingSkeleton />;
  }

  if (status !== "success" || !data) {
    return (
      <QueryState
        status={status}
        message={commandCenterErrorMessage(status, errorMessage)}
        onRetry={() => void refresh()}
      />
    );
  }

  const failureCount = countOperationalFailures(data);
  const readErrorCount = countReadErrors(data);
  const dashboard = data.dashboard;

  return (
    <div className="page-stack command-center-page">
      <CommandCenterOverview
        generatedAt={data.generated_at}
        lastRefreshedAt={lastRefreshedAt}
        refreshIntervalMs={refreshIntervalMs}
        overallHealth={data.health.dashboard}
        dashboardReasons={data.health.dashboard_reasons}
        investigationHealth={data.investigation.health}
        remediationHealth={data.remediation.health}
        executionHealth={data.health.execution}
        executionReasons={data.health.execution_reasons}
        failureCount={failureCount}
        readErrorCount={readErrorCount}
        onRefresh={() => void refresh()}
      />

      <CommandCenterFiltersBar filters={filters} onChange={setFilters} />

      <CommandCenterFailurePanel grouped={groupedFindings} />

      <div className="command-center-grid">
        <CommandCenterAreaCard
          title="크롤러"
          health={dashboard.summary.health}
          metrics={[
            { label: "전체 대상", value: dashboard.crawler.total_targets },
            { label: "활성", value: dashboard.crawler.enabled_targets },
            { label: "최근 성공", value: dashboard.crawler.recent_successes },
            { label: "최근 실패", value: dashboard.crawler.recent_failures },
            { label: "접근 거부", value: dashboard.crawler.ssg_access_denied },
          ]}
          readError={dashboard.crawler.read_error}
          linkTo="/investigation"
          linkLabel={UI.viewInvestigation}
        />
        <CommandCenterAreaCard
          title="가격"
          health={dashboard.summary.health}
          metrics={[
            { label: "대상", value: dashboard.price.targets },
            { label: "가격 있음", value: dashboard.price.with_price },
            { label: "가격 없음", value: dashboard.price.without_price },
            { label: "이력 없음", value: dashboard.price.no_history },
            { label: "잘못된 가격", value: dashboard.price.invalid_price },
          ]}
          readError={dashboard.price.read_error}
          linkTo="/investigation"
          linkLabel={UI.viewInvestigation}
        />
        <CommandCenterAreaCard
          title="가격 알림"
          health={data.investigation.health}
          metrics={[
            { label: "전체", value: dashboard.alerts.total },
            { label: "활성", value: dashboard.alerts.enabled },
            { label: "비활성", value: dashboard.alerts.disabled },
            { label: "최근 발생", value: dashboard.alerts.triggered_recently },
            { label: "무효", value: dashboard.alerts.invalid },
          ]}
          readError={dashboard.alerts.read_error}
          linkTo="/investigation"
          linkLabel={UI.viewInvestigation}
        />
        <CommandCenterAreaCard
          title="알림 전송"
          health={data.investigation.health}
          metrics={[
            { label: "전송 완료", value: dashboard.notifications.sent },
            { label: "실패", value: dashboard.notifications.failed },
            { label: "건너뜀", value: dashboard.notifications.skipped },
            {
              label: "최근 실패",
              value: dashboard.notifications.recent_failures.length,
            },
          ]}
          readError={dashboard.notifications.read_error}
          linkTo="/audit"
          linkLabel={UI.viewAudit}
        />
        <CommandCenterAreaCard
          title="실행기"
          statusLabel="마지막 주기 상태"
          statusValue={dashboard.runner.last_cycle_status}
          metrics={[
            { label: "마지막 실행", value: dashboard.runner.last_run_at ?? "-" },
            { label: "실행 시간(초)", value: dashboard.runner.duration_seconds ?? "-" },
            { label: "최근 실행 횟수", value: dashboard.runner.recent_cycles },
            { label: "실패한 실행 횟수", value: dashboard.runner.recent_failed_cycles },
            { label: "평가 대상", value: dashboard.runner.evaluated },
          ]}
          readError={dashboard.runner.read_error}
          linkTo="/execution"
          linkLabel={UI.viewExecution}
        />
        <CommandCenterAreaCard
          title="감사 로그"
          health={data.investigation.health}
          metrics={[
            { label: "최근 이벤트", value: dashboard.audit.recent_events },
            { label: "최근 실패", value: dashboard.audit.recent_failures },
            { label: "알림 발생", value: dashboard.audit.recent_alert_triggered },
            {
              label: "알림 전송 실패",
              value: dashboard.audit.recent_notification_failed,
            },
          ]}
          readError={dashboard.audit.read_error}
          linkTo="/audit"
          linkLabel={UI.viewAudit}
        />
        <CommandCenterAreaCard
          title="조치 계획"
          health={data.remediation.health}
          metrics={[
            { label: "전체 조치", value: data.remediation.summary.total_actions },
            { label: "조치 필요", value: data.remediation.summary.actionable_actions },
            { label: "읽기 오류", value: data.remediation.read_errors },
            { label: "사용자 승인 필요", value: `${UI.yes} (${UI.planOnly})` },
            { label: "자동 실행", value: "비활성화" },
          ]}
          linkTo="/remediation"
          linkLabel={UI.viewRemediation}
        />
        <CommandCenterAreaCard
          title="실행"
          health={data.execution.health}
          metrics={[
            { label: formatExecutionStatusLabel("PLANNED"), value: data.execution.summary.planned },
            { label: formatExecutionStatusLabel("DRY_RUN"), value: data.execution.summary.dry_run },
            { label: formatExecutionStatusLabel("EXECUTED"), value: data.execution.summary.executed },
            { label: formatExecutionStatusLabel("BLOCKED"), value: data.execution.summary.blocked },
            { label: formatExecutionStatusLabel("FAILED"), value: data.execution.summary.failed },
          ]}
          linkTo="/execution"
          linkLabel={UI.viewExecution}
        />
      </div>

      <div className="command-center-detail-grid">
        <section className="section-card">
          <header>
            <h3>최근 실행 이력</h3>
            <Link to="/execution">{UI.viewExecution}</Link>
          </header>
          {executionEntries.length === 0 ? (
            <p className="muted">최근 실행 이력이 없습니다.</p>
          ) : (
            <ul className="compact-list">
              {executionEntries.map((entry) => (
                <li key={entry!.execution_id}>
                  <ExecutionStatusBadge status={entry!.status} />
                  <strong>{entry!.action_type}</strong>
                  <span>{entry!.occurred_at ?? entry!.started_at ?? "-"}</span>
                  <span>{entry!.message || entry!.error_code || "-"}</span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="section-card">
          <header>
            <h3>최근 감사 이벤트</h3>
            <Link to="/audit">{UI.viewAudit}</Link>
          </header>
          {auditEvents.length === 0 ? (
            <p className="muted">최근 감사 이벤트가 없습니다.</p>
          ) : (
            <ul className="compact-list">
              {auditEvents.map(({ event, summary }) => (
                <li key={event.event_id}>
                  <AuditEventTypeBadge eventType={event.event_type} />
                  <SeverityBadge severity={deriveAuditSeverity(event.event_type, event.status)} compact />
                  <strong>{event.event_type}</strong>
                  <span>{event.occurred_at}</span>
                  <span>{event.message || summary}</span>
                  {event.target_id ? <ResourceRef kind="Target" value={event.target_id} /> : null}
                  {event.alert_id ? <ResourceRef kind="Alert" value={event.alert_id} /> : null}
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="section-card">
          <header>
            <h3>조치 항목</h3>
            <Link to="/remediation">{UI.viewRemediation}</Link>
          </header>
          {remediationActions.length === 0 ? (
            <p className="muted">표시할 조치 항목이 없습니다.</p>
          ) : (
            <ul className="compact-list">
              {remediationActions.map((action) => (
                <li key={action.action_id}>
                  <PriorityBadge priority={action.priority} />
                  <strong>{action.action_type}</strong>
                  <span>{action.action_id}</span>
                  <span>{action.title}</span>
                  <span>
                    {UI.approvalRequired}: {formatYesNo(action.human_approval_required)} /{" "}
                    {UI.autoExecution}: {formatYesNo(action.auto_executable)}
                  </span>
                  <Link to="/remediation">{UI.viewRemediation}</Link>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}
