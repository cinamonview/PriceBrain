import type { InvestigationFinding } from "../api/types";
import { formatAreaLabel } from "../utils/investigationFilters";
import { ResourceRef } from "./ResourceRef";
import { SeverityBadge, severityHint, normalizeSeverity } from "./SeverityBadge";

interface FindingCardProps {
  finding: InvestigationFinding;
  selected?: boolean;
  onSelect: (finding: InvestigationFinding) => void;
}

export function FindingCard({ finding, selected = false, onSelect }: FindingCardProps) {
  const severity = normalizeSeverity(finding.severity);

  return (
    <button
      type="button"
      className={`finding-card severity-border-${severity.toLowerCase()}${selected ? " selected" : ""}`}
      onClick={() => onSelect(finding)}
      aria-pressed={selected}
    >
      <div className="finding-card-header">
        <SeverityBadge severity={finding.severity} />
        <span className="finding-code">{finding.code}</span>
      </div>
      <h4>{finding.title}</h4>
      <p className="finding-cause-label">원인:</p>
      <p className="finding-message">{finding.message}</p>
      <div className="finding-meta-grid">
        <div>
          <span className="meta-label">영역</span>
          <span>{formatAreaLabel(finding.area)}</span>
        </div>
        {finding.target_id ? (
          <div>
            <span className="meta-label">대상</span>
            <ResourceRef kind="Target" value={finding.target_id} />
          </div>
        ) : null}
        {finding.alert_id ? (
          <div>
            <span className="meta-label">Alert</span>
            <ResourceRef kind="Alert" value={finding.alert_id} />
          </div>
        ) : null}
        {finding.occurred_at ? (
          <div>
            <span className="meta-label">발생</span>
            <span>{finding.occurred_at}</span>
          </div>
        ) : null}
      </div>
      <p className="finding-hint">{severityHint(severity)}</p>
    </button>
  );
}
