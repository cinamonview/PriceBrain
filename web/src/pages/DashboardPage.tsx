import { useAuth } from "../auth/AuthContext";
import { HealthBadge, QueryState, SectionCard } from "../components/HealthBadge";
import { getRefreshIntervalMs, useOperationsQuery } from "../hooks/useOperationsQuery";

export function DashboardPage() {
  const { user, operationsApi } = useAuth();
  const enabled = Boolean(user);
  const { data, status, errorMessage, refresh } = useOperationsQuery({
    enabled,
    fetcher: operationsApi.getDashboard,
    refreshMs: getRefreshIntervalMs(),
  });

  if (status !== "success" || !data) {
    return <QueryState status={status} message={errorMessage} onRetry={() => void refresh()} />;
  }

  return (
    <div className="page-stack">
      <div className="page-header">
        <div>
          <h2>Dashboard</h2>
          <p className="muted">Generated at {data.generated_at}</p>
        </div>
        <HealthBadge label="Dashboard Health" status={data.summary.health} />
      </div>

      <div className="card-grid">
        <SectionCard title="Crawler" readError={data.crawler.read_error}>
          <ul className="metric-list">
            <li>Total targets: {data.crawler.total_targets}</li>
            <li>Failed: {data.crawler.failed_targets}</li>
            <li>SSG access denied: {data.crawler.ssg_access_denied}</li>
            <li>Recent failures: {data.crawler.recent_failures}</li>
          </ul>
        </SectionCard>
        <SectionCard title="Price" readError={data.price.read_error}>
          <ul className="metric-list">
            <li>Targets: {data.price.targets}</li>
            <li>With price: {data.price.with_price}</li>
            <li>No history: {data.price.no_history}</li>
            <li>Invalid price: {data.price.invalid_price}</li>
          </ul>
        </SectionCard>
        <SectionCard title="Alerts" readError={data.alerts.read_error}>
          <ul className="metric-list">
            <li>Total: {data.alerts.total}</li>
            <li>Enabled: {data.alerts.enabled}</li>
            <li>Invalid: {data.alerts.invalid}</li>
            <li>Recent invalid: {data.alerts.recent_invalid}</li>
          </ul>
        </SectionCard>
        <SectionCard title="Notifications" readError={data.notifications.read_error}>
          <ul className="metric-list">
            <li>Sent: {data.notifications.sent}</li>
            <li>Failed: {data.notifications.failed}</li>
            <li>Skipped: {data.notifications.skipped}</li>
            <li>Recent failures: {data.notifications.recent_failures.length}</li>
          </ul>
        </SectionCard>
        <SectionCard title="Runner" readError={data.runner.read_error}>
          <ul className="metric-list">
            <li>Status: {data.runner.last_cycle_status}</li>
            <li>Recent cycles: {data.runner.recent_cycles}</li>
            <li>Recent failed cycles: {data.runner.recent_failed_cycles}</li>
            <li>Notification failed: {data.runner.notification_failed}</li>
          </ul>
        </SectionCard>
        <SectionCard title="Audit" readError={data.audit.read_error}>
          <ul className="metric-list">
            <li>Recent events: {data.audit.recent_events}</li>
            <li>Recent failures: {data.audit.recent_failures}</li>
            <li>Alert triggered: {data.audit.recent_alert_triggered}</li>
            <li>Runner failed: {data.audit.recent_runner_failed}</li>
          </ul>
        </SectionCard>
      </div>
    </div>
  );
}
