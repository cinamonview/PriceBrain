import { useAuth } from "../auth/AuthContext";
import { HealthBadge, QueryState, SectionCard } from "../components/HealthBadge";
import { getRefreshIntervalMs, useOperationsQuery } from "../hooks/useOperationsQuery";

export function CommandCenterPage() {
  const { user, operationsApi } = useAuth();
  const enabled = Boolean(user);
  const { data, status, errorMessage, refresh } = useOperationsQuery({
    enabled,
    fetcher: operationsApi.getCommandCenter,
    refreshMs: getRefreshIntervalMs(),
  });

  if (status !== "success" || !data) {
    return <QueryState status={status} message={errorMessage} onRetry={() => void refresh()} />;
  }

  const overallHealth = data.health.dashboard;
  const events = data.dashboard.audit.event_snapshots.slice(0, 5);

  return (
    <div className="page-stack">
      <div className="page-header">
        <div>
          <h2>Command Center</h2>
          <p className="muted">Generated at {data.generated_at}</p>
        </div>
        <button type="button" onClick={() => void refresh()}>
          Refresh
        </button>
      </div>

      <div className="health-grid">
        <HealthBadge label="Overall Dashboard Health" status={overallHealth} />
        <HealthBadge label="Execution Health" status={data.health.execution} />
        <HealthBadge label="Investigation Health" status={data.investigation.health} />
        <HealthBadge label="Remediation Health" status={data.remediation.health} />
        <HealthBadge label="Runner Status" status={data.dashboard.runner.last_cycle_status} />
        <HealthBadge
          label="Notification Health"
          status={data.dashboard.notifications.failed > 0 ? "DEGRADED" : "HEALTHY"}
        />
      </div>

      <div className="card-grid">
        <SectionCard title="Dashboard">
          <ul className="metric-list">
            <li>Crawler targets: {data.dashboard.crawler.total_targets}</li>
            <li>Failed targets: {data.dashboard.crawler.failed_targets}</li>
            <li>Price targets: {data.dashboard.price.targets}</li>
            <li>Alerts: {data.dashboard.alerts.total}</li>
          </ul>
        </SectionCard>
        <SectionCard title="Investigation">
          <ul className="metric-list">
            <li>Total findings: {data.investigation.summary.total_findings}</li>
            <li>Critical: {data.investigation.summary.critical_count}</li>
            <li>Warnings: {data.investigation.summary.warning_count}</li>
          </ul>
        </SectionCard>
        <SectionCard title="Remediation Plan">
          <ul className="metric-list">
            <li>Actionable actions: {data.remediation.summary.actionable_actions}</li>
            <li>Total actions: {data.remediation.summary.total_actions}</li>
            <li>Plan only / human approval required</li>
          </ul>
        </SectionCard>
        <SectionCard title="Execution History">
          <ul className="metric-list">
            <li>Total entries: {data.execution.summary.total}</li>
            <li>Blocked: {data.execution.summary.blocked}</li>
            <li>Failed: {data.execution.summary.failed}</li>
            <li>Mutations: {data.execution.summary.mutation_count}</li>
          </ul>
        </SectionCard>
      </div>

      <SectionCard title="Recent Important Events">
        {events.length === 0 ? (
          <p className="muted">No recent audit events.</p>
        ) : (
          <ul className="event-list">
            {events.map((event, index) => {
              const item = event as Record<string, unknown>;
              return (
                <li key={`${String(item.event_type ?? "event")}-${index}`}>
                  <strong>{String(item.event_type ?? "UNKNOWN")}</strong>
                  <span>{String(item.status ?? "-")}</span>
                  <span>{String(item.occurred_at ?? item.message ?? "")}</span>
                </li>
              );
            })}
          </ul>
        )}
      </SectionCard>
    </div>
  );
}
