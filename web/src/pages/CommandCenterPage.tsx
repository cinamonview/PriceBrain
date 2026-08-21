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

function commandCenterErrorMessage(status: string, fallback: string | null): string | null {
  if (status === "unauthorized") {
    return "인증이 필요합니다.";
  }
  if (status === "forbidden") {
    return "Command Center 정보를 볼 권한이 없습니다.";
  }
  if (status === "error") {
    return "Command Center 정보를 불러오지 못했습니다.";
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
        throw new ApiError(500, "Command Center 정보를 불러오지 못했습니다.");
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
          title="Crawler"
          health={dashboard.summary.health}
          metrics={[
            { label: "Total targets", value: dashboard.crawler.total_targets },
            { label: "Enabled", value: dashboard.crawler.enabled_targets },
            { label: "Recent success", value: dashboard.crawler.recent_successes },
            { label: "Recent failure", value: dashboard.crawler.recent_failures },
            { label: "Access denied", value: dashboard.crawler.ssg_access_denied },
          ]}
          readError={dashboard.crawler.read_error}
          linkTo="/investigation"
          linkLabel="View Investigation"
        />
        <CommandCenterAreaCard
          title="Price"
          health={dashboard.summary.health}
          metrics={[
            { label: "Targets", value: dashboard.price.targets },
            { label: "With price", value: dashboard.price.with_price },
            { label: "Without price", value: dashboard.price.without_price },
            { label: "No history", value: dashboard.price.no_history },
            { label: "Invalid price", value: dashboard.price.invalid_price },
          ]}
          readError={dashboard.price.read_error}
          linkTo="/investigation"
          linkLabel="View Investigation"
        />
        <CommandCenterAreaCard
          title="Alerts"
          health={data.investigation.health}
          metrics={[
            { label: "Total", value: dashboard.alerts.total },
            { label: "Enabled", value: dashboard.alerts.enabled },
            { label: "Disabled", value: dashboard.alerts.disabled },
            { label: "Recently triggered", value: dashboard.alerts.triggered_recently },
            { label: "Invalid", value: dashboard.alerts.invalid },
          ]}
          readError={dashboard.alerts.read_error}
          linkTo="/investigation"
          linkLabel="View Investigation"
        />
        <CommandCenterAreaCard
          title="Notifications"
          health={data.investigation.health}
          metrics={[
            { label: "Sent", value: dashboard.notifications.sent },
            { label: "Failed", value: dashboard.notifications.failed },
            { label: "Skipped", value: dashboard.notifications.skipped },
            {
              label: "Recent failures",
              value: dashboard.notifications.recent_failures.length,
            },
          ]}
          readError={dashboard.notifications.read_error}
          linkTo="/audit"
          linkLabel="View Audit"
        />
        <CommandCenterAreaCard
          title="Runner"
          statusLabel="Last cycle status"
          statusValue={dashboard.runner.last_cycle_status}
          metrics={[
            { label: "Last run", value: dashboard.runner.last_run_at ?? "-" },
            { label: "Duration (s)", value: dashboard.runner.duration_seconds ?? "-" },
            { label: "Recent cycles", value: dashboard.runner.recent_cycles },
            { label: "Failed cycles", value: dashboard.runner.recent_failed_cycles },
            { label: "Evaluated", value: dashboard.runner.evaluated },
          ]}
          readError={dashboard.runner.read_error}
          linkTo="/execution"
          linkLabel="View Execution"
        />
        <CommandCenterAreaCard
          title="Audit"
          health={data.investigation.health}
          metrics={[
            { label: "Recent events", value: dashboard.audit.recent_events },
            { label: "Recent failures", value: dashboard.audit.recent_failures },
            { label: "Alert triggered", value: dashboard.audit.recent_alert_triggered },
            {
              label: "Notification failed",
              value: dashboard.audit.recent_notification_failed,
            },
          ]}
          readError={dashboard.audit.read_error}
          linkTo="/audit"
          linkLabel="View Audit"
        />
        <CommandCenterAreaCard
          title="Remediation"
          health={data.remediation.health}
          metrics={[
            { label: "Total actions", value: data.remediation.summary.total_actions },
            { label: "Actionable", value: data.remediation.summary.actionable_actions },
            { label: "Read errors", value: data.remediation.read_errors },
            { label: "Human approval required", value: "Yes (plan only)" },
            { label: "Auto execution", value: "Disabled" },
          ]}
          linkTo="/remediation"
          linkLabel="View Remediation"
        />
        <CommandCenterAreaCard
          title="Execution"
          health={data.execution.health}
          metrics={[
            { label: "PLANNED", value: data.execution.summary.planned },
            { label: "DRY_RUN", value: data.execution.summary.dry_run },
            { label: "EXECUTED", value: data.execution.summary.executed },
            { label: "BLOCKED", value: data.execution.summary.blocked },
            { label: "FAILED", value: data.execution.summary.failed },
          ]}
          linkTo="/execution"
          linkLabel="View Execution"
        />
      </div>

      <div className="command-center-detail-grid">
        <section className="section-card">
          <header>
            <h3>Recent Execution History</h3>
            <Link to="/execution">View Execution</Link>
          </header>
          {executionEntries.length === 0 ? (
            <p className="muted">No recent execution entries.</p>
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
            <h3>Recent Audit Events</h3>
            <Link to="/audit">View Audit</Link>
          </header>
          {auditEvents.length === 0 ? (
            <p className="muted">No recent audit events.</p>
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
            <h3>Remediation Actions</h3>
            <Link to="/remediation">View Remediation</Link>
          </header>
          {remediationActions.length === 0 ? (
            <p className="muted">No remediation actions available.</p>
          ) : (
            <ul className="compact-list">
              {remediationActions.map((action) => (
                <li key={action.action_id}>
                  <PriorityBadge priority={action.priority} />
                  <strong>{action.action_type}</strong>
                  <span>{action.action_id}</span>
                  <span>{action.title}</span>
                  <span>
                    Approval required: {action.human_approval_required ? "Yes" : "No"} / Auto:{" "}
                    {action.auto_executable ? "Yes" : "No"}
                  </span>
                  <Link to="/remediation">View Remediation</Link>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}
