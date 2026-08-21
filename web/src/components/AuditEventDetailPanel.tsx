import { Link } from "react-router-dom";
import type { AuditEventSnapshot } from "../api/types";
import {
  deriveAuditArea,
  deriveAuditSeverity,
  deriveAuditTitle,
  metadataString,
} from "../utils/auditFilters";
import { formatAreaLabel } from "../utils/investigationFilters";
import { sanitizeMetadataRecord } from "../utils/securityUtils";
import { AuditEventTypeBadge } from "./AuditEventTypeBadge";
import { ResourceRef } from "./ResourceRef";
import { SeverityBadge } from "./SeverityBadge";

interface AuditEventDetailPanelProps {
  snapshot: AuditEventSnapshot | null;
  onClose: () => void;
}

export function AuditEventDetailPanel({ snapshot, onClose }: AuditEventDetailPanelProps) {
  if (!snapshot) {
    return null;
  }

  if (snapshot.read_error && !snapshot.event) {
    return (
      <aside className="finding-detail-panel" aria-label="Audit event detail">
        <div className="finding-detail-header">
          <h3>Audit Event Detail</h3>
          <button type="button" onClick={onClose}>
            Close
          </button>
        </div>
        <p className="finding-message">{snapshot.read_error}</p>
      </aside>
    );
  }

  const event = snapshot.event;
  if (!event) {
    return null;
  }

  const metadata =
    event.metadata && Object.keys(event.metadata).length > 0
      ? sanitizeMetadataRecord(event.metadata)
      : null;
  const findingId = metadataString(event.metadata, "finding_id");
  const executionId = metadataString(event.metadata, "execution_id");
  const actionId = metadataString(event.metadata, "action_id");
  const severity = deriveAuditSeverity(event.event_type, event.status);

  return (
    <aside className="finding-detail-panel" aria-label="Audit event detail">
      <div className="finding-detail-header">
        <h3>Audit Event Detail</h3>
        <button type="button" onClick={onClose}>
          Close
        </button>
      </div>
      <dl className="finding-detail-list">
        <div>
          <dt>Event ID</dt>
          <dd>{event.event_id}</dd>
        </div>
        <div>
          <dt>Event Type</dt>
          <dd>
            <AuditEventTypeBadge eventType={event.event_type} />
          </dd>
        </div>
        <div>
          <dt>Occurred At</dt>
          <dd>{event.occurred_at}</dd>
        </div>
        <div>
          <dt>Area</dt>
          <dd>{formatAreaLabel(deriveAuditArea(event.event_type))}</dd>
        </div>
        <div>
          <dt>Severity</dt>
          <dd>
            <SeverityBadge severity={severity} />
          </dd>
        </div>
        <div>
          <dt>Title</dt>
          <dd>{deriveAuditTitle(event)}</dd>
        </div>
        {event.status ? (
          <div>
            <dt>Status / Result</dt>
            <dd>{event.status}</dd>
          </div>
        ) : null}
        {event.target_id ? (
          <div>
            <dt>Target</dt>
            <dd>
              <ResourceRef kind="Target" value={event.target_id} />
            </dd>
          </div>
        ) : null}
        {event.alert_id ? (
          <div>
            <dt>Alert</dt>
            <dd>
              <ResourceRef kind="Alert" value={event.alert_id} />
            </dd>
          </div>
        ) : null}
        {findingId ? (
          <div>
            <dt>Finding</dt>
            <dd>
              {findingId}
              <div className="action-card-links">
                <Link to="/investigation">View Finding</Link>
              </div>
            </dd>
          </div>
        ) : null}
        {executionId ? (
          <div>
            <dt>Execution</dt>
            <dd>
              {executionId}
              <div className="action-card-links">
                <Link to="/execution">View Execution</Link>
              </div>
            </dd>
          </div>
        ) : null}
        {actionId ? (
          <div>
            <dt>Remediation Action</dt>
            <dd>
              {actionId}
              <div className="action-card-links">
                <Link to="/remediation">View Remediation</Link>
              </div>
            </dd>
          </div>
        ) : null}
        <div>
          <dt>Summary</dt>
          <dd>{snapshot.summary || "-"}</dd>
        </div>
        <div>
          <dt>Message</dt>
          <dd>{event.message || "-"}</dd>
        </div>
        {event.channel ? (
          <div>
            <dt>Channel</dt>
            <dd>{event.channel}</dd>
          </div>
        ) : null}
        {event.classification ? (
          <div>
            <dt>Classification</dt>
            <dd>{event.classification}</dd>
          </div>
        ) : null}
        {metadata ? (
          <div>
            <dt>Metadata</dt>
            <dd>
              <pre className="metadata-block">{JSON.stringify(metadata, null, 2)}</pre>
            </dd>
          </div>
        ) : null}
      </dl>
    </aside>
  );
}
