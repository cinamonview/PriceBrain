import { Link } from "react-router-dom";
import type { InvestigationFinding } from "../api/types";
import { SeverityBadge } from "./SeverityBadge";
import { ResourceRef } from "./ResourceRef";

interface CommandCenterFailurePanelProps {
  grouped: Record<"CRITICAL" | "ERROR" | "WARNING", InvestigationFinding[]>;
}

function FindingRow({ finding }: { finding: InvestigationFinding }) {
  return (
    <li className="command-center-finding-row">
      <div>
        <SeverityBadge severity={finding.severity} compact />
        <strong>{finding.code}</strong>
        <p className="finding-message">{finding.message}</p>
        <div className="finding-meta-inline">
          {finding.target_id ? <ResourceRef kind="Target" value={finding.target_id} /> : null}
          {finding.alert_id ? <ResourceRef kind="Alert" value={finding.alert_id} /> : null}
        </div>
      </div>
      <Link to="/investigation">View Investigation</Link>
    </li>
  );
}

export function CommandCenterFailurePanel({ grouped }: CommandCenterFailurePanelProps) {
  const total =
    grouped.CRITICAL.length + grouped.ERROR.length + grouped.WARNING.length;

  return (
    <section className="section-card command-center-failure-panel">
      <header>
        <h3>Critical / Failure Highlights</h3>
        <span className="muted">{total} findings</span>
      </header>
      {total === 0 ? (
        <p className="muted">No highlighted findings in the current filter scope.</p>
      ) : (
        <div className="failure-groups">
          {(["CRITICAL", "ERROR", "WARNING"] as const).map((severity) =>
            grouped[severity].length > 0 ? (
              <div key={severity} className={`failure-group failure-group-${severity.toLowerCase()}`}>
                <h4>{severity}</h4>
                <ul className="event-list">
                  {grouped[severity].map((finding) => (
                    <FindingRow key={finding.finding_id} finding={finding} />
                  ))}
                </ul>
              </div>
            ) : null,
          )}
        </div>
      )}
    </section>
  );
}
