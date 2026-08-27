import { Link } from "react-router-dom";
import { HealthBadge } from "./HealthBadge";
import { UI, formatAutoRefresh, formatHealthLabel } from "../utils/uiLabels";

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
          <h2>PriceBrain {UI.commandCenter}</h2>
          <p className="muted">
            {UI.generatedAt} {generatedAt}
          </p>
          {lastRefreshedAt ? (
            <p className="muted">
              {UI.lastRefresh}: {lastRefreshedAt}
            </p>
          ) : null}
          <p className="muted">{formatAutoRefresh(Math.round(refreshIntervalMs / 1000))}</p>
        </div>
        <button type="button" onClick={onRefresh}>
          {UI.refresh}
        </button>
      </div>

      <div className="health-grid command-center-health-grid">
        <HealthBadge label={formatHealthLabel("전체")} status={overallHealth} />
        <HealthBadge label={formatHealthLabel(UI.investigation)} status={investigationHealth} />
        <HealthBadge label={formatHealthLabel(UI.remediation)} status={remediationHealth} />
        <HealthBadge label={formatHealthLabel("실행")} status={executionHealth} />
        <div className="summary-count-card execution-status-failed">
          <span>실패 건수</span>
          <strong>{failureCount}</strong>
        </div>
        <div className="summary-count-card">
          <span>읽기 오류</span>
          <strong>{readErrorCount}</strong>
        </div>
      </div>

      {dashboardReasons.length > 0 ? (
        <p className="muted">대시보드 상태 사유: {dashboardReasons.join(", ")}</p>
      ) : null}
      {executionReasons.length > 0 ? (
        <p className="muted">실행 상태 사유: {executionReasons.join(", ")}</p>
      ) : null}

      <div className="action-card-links">
        <Link to="/investigation">{UI.viewInvestigation}</Link>
        <Link to="/remediation">{UI.viewRemediation}</Link>
        <Link to="/execution">{UI.viewExecution}</Link>
        <Link to="/audit">{UI.viewAudit}</Link>
      </div>
    </section>
  );
}
