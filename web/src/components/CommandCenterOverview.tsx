import { Link } from "react-router-dom";
import { HealthBadge } from "./HealthBadge";

interface CommandCenterOverviewProps {
  generatedAt: string;
  lastRefreshedAt: string | null;
  refreshIntervalMs: number;
  overallHealth: string;
  dashboardReasons: string[];
  investigationHealth: string;
  remediationHealth: string;
  executionHealth: string;
  executionReasons: string[];
  failureCount: number;
  readErrorCount: number;
  onRefresh: () => void;
}

export function CommandCenterOverview({
  generatedAt,
  lastRefreshedAt,
  refreshIntervalMs,
  overallHealth,
  dashboardReasons,
  investigationHealth,
  remediationHealth,
  executionHealth,
  executionReasons,
  failureCount,
  readErrorCount,
  onRefresh,
}: CommandCenterOverviewProps) {
  return (
    <section className="section-card command-center-overview">
      <div className="page-header">
        <div>
          <h2>PriceBrain Command Center</h2>
          <p className="muted">Generated at {generatedAt}</p>
          {lastRefreshedAt ? <p className="muted">Last refresh: {lastRefreshedAt}</p> : null}
          <p className="muted">
            Auto-refresh every {Math.round(refreshIntervalMs / 1000)}s (read-only)
          </p>
        </div>
        <button type="button" onClick={onRefresh}>
          Refresh
        </button>
      </div>

      <div className="health-grid command-center-health-grid">
        <HealthBadge label="Overall Health" status={overallHealth} />
        <HealthBadge label="Investigation Health" status={investigationHealth} />
        <HealthBadge label="Remediation Health" status={remediationHealth} />
        <HealthBadge label="Execution Health" status={executionHealth} />
        <div className="summary-count-card execution-status-failed">
          <span>Failure Count</span>
          <strong>{failureCount}</strong>
        </div>
        <div className="summary-count-card">
          <span>Read Errors</span>
          <strong>{readErrorCount}</strong>
        </div>
      </div>

      {dashboardReasons.length > 0 ? (
        <p className="muted">Dashboard health reasons: {dashboardReasons.join(", ")}</p>
      ) : null}
      {executionReasons.length > 0 ? (
        <p className="muted">Execution health reasons: {executionReasons.join(", ")}</p>
      ) : null}

      <div className="action-card-links">
        <Link to="/investigation">View Investigation</Link>
        <Link to="/remediation">View Remediation</Link>
        <Link to="/execution">View Execution</Link>
        <Link to="/audit">View Audit</Link>
      </div>
    </section>
  );
}
