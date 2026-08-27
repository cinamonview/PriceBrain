import { Link } from "react-router-dom";
import type { AuditEventSnapshot } from "../api/types";
import {
  deriveAuditArea,
  deriveAuditSeverity,
  metadataString,
} from "../utils/auditFilters";
import { UI, formatAreaLabel, formatAuditEventTypeLabel } from "../utils/uiLabels";
import { AuditEventTypeBadge, normalizeAuditEventType } from "./AuditEventTypeBadge";
import { ResourceRef } from "./ResourceRef";
import { SeverityBadge } from "./SeverityBadge";

interface AuditEventCardProps {
  snapshot: AuditEventSnapshot;
  selected?: boolean;
  onSelect: (snapshot: AuditEventSnapshot) => void;
}

export function AuditEventCard({ snapshot, selected = false, onSelect }: AuditEventCardProps) {
  if (snapshot.read_error && !snapshot.event) {
    return (
      <button
        type="button"
        className={`finding-card audit-event-invalid${selected ? " selected" : ""}`}
        onClick={() => onSelect(snapshot)}
        aria-pressed={selected}
      >
        <div className="finding-card-header">
          <span className="execution-status execution-status-failed">무효</span>
        </div>
        <h4>무효한 감사 이벤트</h4>
        <p className="finding-message">{snapshot.read_error}</p>
      </button>
    );
  }

  const event = snapshot.event;
  if (!event) {
    return null;
  }

  const severity = deriveAuditSeverity(event.event_type, event.status);
  const area = deriveAuditArea(event.event_type);
  const findingId = metadataString(event.metadata, "finding_id");
  const executionId = metadataString(event.metadata, "execution_id");
  const actionId = metadataString(event.metadata, "action_id");

  return (
    <button
      type="button"
      className={`finding-card audit-event-border-${normalizeAuditEventType(event.event_type).toLowerCase()}${selected ? " selected" : ""}`}
      onClick={() => onSelect(snapshot)}
      aria-pressed={selected}
    >
      <div className="finding-card-header">
        <AuditEventTypeBadge eventType={event.event_type} />
        <SeverityBadge severity={severity} compact />
      </div>
      <h4>{formatAuditEventTypeLabel(event.event_type)}</h4>
      <p className="finding-cause-label">{UI.message}:</p>
      <p className="finding-message">{event.message || snapshot.summary || "-"}</p>
      <div className="finding-meta-grid">
        <div>
          <span className="meta-label">이벤트 ID</span>
          <span>{event.event_id}</span>
        </div>
        <div>
          <span className="meta-label">{UI.occurred}</span>
          <span>{event.occurred_at}</span>
        </div>
        <div>
          <span className="meta-label">{UI.area}</span>
          <span>{formatAreaLabel(area)}</span>
        </div>
        {event.status ? (
          <div>
            <span className="meta-label">{UI.status}</span>
            <span>{event.status}</span>
          </div>
        ) : null}
        {event.target_id ? (
          <div>
            <span className="meta-label">{UI.target}</span>
            <ResourceRef kind="Target" value={event.target_id} />
          </div>
        ) : null}
        {event.alert_id ? (
          <div>
            <span className="meta-label">{UI.alert}</span>
            <ResourceRef kind="Alert" value={event.alert_id} />
          </div>
        ) : null}
        {findingId ? (
          <div>
            <span className="meta-label">발견 사항</span>
            <span>{findingId}</span>
          </div>
        ) : null}
      </div>
      <div className="action-card-links">
        {findingId ? (
          <Link to="/investigation" onClick={(event) => event.stopPropagation()}>
            {UI.viewFinding}
          </Link>
        ) : null}
        {executionId ? (
          <Link to="/execution" onClick={(event) => event.stopPropagation()}>
            {UI.viewExecution}
          </Link>
        ) : null}
        {actionId ? (
          <Link to="/remediation" onClick={(event) => event.stopPropagation()}>
            {UI.viewRemediation}
          </Link>
        ) : null}
        <span className="muted">{UI.details}</span>
      </div>
    </button>
  );
}
