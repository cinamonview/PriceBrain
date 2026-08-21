import { Link } from "react-router-dom";
import type { AuditEventSnapshot } from "../api/types";
import {
  deriveAuditArea,
  deriveAuditSeverity,
  deriveAuditTitle,
  metadataString,
} from "../utils/auditFilters";
import { formatAreaLabel } from "../utils/investigationFilters";
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
          <span className="execution-status execution-status-failed">INVALID</span>
        </div>
        <h4>Invalid audit event</h4>
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
      <h4>{deriveAuditTitle(event)}</h4>
      <p className="finding-cause-label">Message:</p>
      <p className="finding-message">{event.message || snapshot.summary || "-"}</p>
      <div className="finding-meta-grid">
        <div>
          <span className="meta-label">Event ID</span>
          <span>{event.event_id}</span>
        </div>
        <div>
          <span className="meta-label">Occurred</span>
          <span>{event.occurred_at}</span>
        </div>
        <div>
          <span className="meta-label">Area</span>
          <span>{formatAreaLabel(area)}</span>
        </div>
        {event.status ? (
          <div>
            <span className="meta-label">Status</span>
            <span>{event.status}</span>
          </div>
        ) : null}
        {event.target_id ? (
          <div>
            <span className="meta-label">Target</span>
            <ResourceRef kind="Target" value={event.target_id} />
          </div>
        ) : null}
        {event.alert_id ? (
          <div>
            <span className="meta-label">Alert</span>
            <ResourceRef kind="Alert" value={event.alert_id} />
          </div>
        ) : null}
        {findingId ? (
          <div>
            <span className="meta-label">Finding</span>
            <span>{findingId}</span>
          </div>
        ) : null}
      </div>
      <div className="action-card-links">
        {findingId ? (
          <Link to="/investigation" onClick={(event) => event.stopPropagation()}>
            View Finding
          </Link>
        ) : null}
        {executionId ? (
          <Link to="/execution" onClick={(event) => event.stopPropagation()}>
            View Execution
          </Link>
        ) : null}
        {actionId ? (
          <Link to="/remediation" onClick={(event) => event.stopPropagation()}>
            View Remediation
          </Link>
        ) : null}
        <span className="muted">View Details</span>
      </div>
    </button>
  );
}
