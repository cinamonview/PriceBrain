import { Link } from "react-router-dom";
import type { AuditEventSnapshot } from "../api/types";
import {
  deriveAuditArea,
  deriveAuditSeverity,
  metadataString,
} from "../utils/auditFilters";
import { sanitizeMetadataRecord } from "../utils/securityUtils";
import { UI, formatAreaLabel, formatAuditEventTypeLabel } from "../utils/uiLabels";
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
      <aside className="finding-detail-panel" aria-label="감사 이벤트 상세">
        <div className="finding-detail-header">
          <h3>감사 이벤트 상세</h3>
          <button type="button" onClick={onClose}>
            {UI.close}
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
    <aside className="finding-detail-panel" aria-label="감사 이벤트 상세">
      <div className="finding-detail-header">
        <h3>감사 이벤트 상세</h3>
        <button type="button" onClick={onClose}>
          {UI.close}
        </button>
      </div>
      <dl className="finding-detail-list">
        <div>
          <dt>이벤트 ID</dt>
          <dd>{event.event_id}</dd>
        </div>
        <div>
          <dt>이벤트 유형</dt>
          <dd>
            <AuditEventTypeBadge eventType={event.event_type} />
            <span className="muted"> ({event.event_type})</span>
          </dd>
        </div>
        <div>
          <dt>발생 시각</dt>
          <dd>{event.occurred_at}</dd>
        </div>
        <div>
          <dt>{UI.area}</dt>
          <dd>{formatAreaLabel(deriveAuditArea(event.event_type))}</dd>
        </div>
        <div>
          <dt>{UI.severity}</dt>
          <dd>
            <SeverityBadge severity={severity} />
          </dd>
        </div>
        <div>
          <dt>제목</dt>
          <dd>{formatAuditEventTypeLabel(event.event_type)}</dd>
        </div>
        {event.status ? (
          <div>
            <dt>상태 / 결과</dt>
            <dd>{event.status}</dd>
          </div>
        ) : null}
        {event.target_id ? (
          <div>
            <dt>{UI.target}</dt>
            <dd>
              <ResourceRef kind="Target" value={event.target_id} />
            </dd>
          </div>
        ) : null}
        {event.alert_id ? (
          <div>
            <dt>{UI.alert}</dt>
            <dd>
              <ResourceRef kind="Alert" value={event.alert_id} />
            </dd>
          </div>
        ) : null}
        {findingId ? (
          <div>
            <dt>발견 사항</dt>
            <dd>
              {findingId}
              <div className="action-card-links">
                <Link to="/investigation">{UI.viewFinding}</Link>
              </div>
            </dd>
          </div>
        ) : null}
        {executionId ? (
          <div>
            <dt>실행</dt>
            <dd>
              {executionId}
              <div className="action-card-links">
                <Link to="/execution">{UI.viewExecution}</Link>
              </div>
            </dd>
          </div>
        ) : null}
        {actionId ? (
          <div>
            <dt>조치</dt>
            <dd>
              {actionId}
              <div className="action-card-links">
                <Link to="/remediation">{UI.viewRemediation}</Link>
              </div>
            </dd>
          </div>
        ) : null}
        <div>
          <dt>{UI.summary}</dt>
          <dd>{snapshot.summary || "-"}</dd>
        </div>
        <div>
          <dt>{UI.message}</dt>
          <dd>{event.message || "-"}</dd>
        </div>
        {event.channel ? (
          <div>
            <dt>채널</dt>
            <dd>{event.channel}</dd>
          </div>
        ) : null}
        {event.classification ? (
          <div>
            <dt>분류</dt>
            <dd>{event.classification}</dd>
          </div>
        ) : null}
        {metadata ? (
          <div>
            <dt>{UI.metadata}</dt>
            <dd>
              <pre className="metadata-block">{JSON.stringify(metadata, null, 2)}</pre>
            </dd>
          </div>
        ) : null}
      </dl>
    </aside>
  );
}
