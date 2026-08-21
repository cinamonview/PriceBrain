import type { InvestigationFinding } from "../api/types";
import { sanitizeMetadataRecord } from "../utils/securityUtils";
import { formatAreaLabel } from "../utils/investigationFilters";
import { ResourceRef } from "./ResourceRef";
import { SeverityBadge } from "./SeverityBadge";

interface FindingDetailPanelProps {
  finding: InvestigationFinding | null;
  onClose: () => void;
}

export function FindingDetailPanel({ finding, onClose }: FindingDetailPanelProps) {
  if (!finding) {
    return null;
  }

  const metadata =
    finding.metadata && Object.keys(finding.metadata).length > 0
      ? sanitizeMetadataRecord(finding.metadata)
      : null;

  return (
    <aside className="finding-detail-panel" aria-label="Finding detail">
      <div className="finding-detail-header">
        <h3>Finding Detail</h3>
        <button type="button" onClick={onClose}>
          Close
        </button>
      </div>
      <dl className="finding-detail-list">
        <div>
          <dt>Finding Code</dt>
          <dd>{finding.code}</dd>
        </div>
        <div>
          <dt>Severity</dt>
          <dd>
            <SeverityBadge severity={finding.severity} />
          </dd>
        </div>
        <div>
          <dt>Area</dt>
          <dd>{formatAreaLabel(finding.area)}</dd>
        </div>
        <div>
          <dt>Title</dt>
          <dd>{finding.title}</dd>
        </div>
        <div>
          <dt>Message</dt>
          <dd>{finding.message}</dd>
        </div>
        {finding.target_id ? (
          <div>
            <dt>Target ID</dt>
            <dd>
              <ResourceRef kind="Target" value={finding.target_id} />
            </dd>
          </div>
        ) : null}
        {finding.alert_id ? (
          <div>
            <dt>Alert ID</dt>
            <dd>
              <ResourceRef kind="Alert" value={finding.alert_id} />
            </dd>
          </div>
        ) : null}
        {finding.event_id ? (
          <div>
            <dt>Event ID</dt>
            <dd>{finding.event_id}</dd>
          </div>
        ) : null}
        {finding.occurred_at ? (
          <div>
            <dt>Occurred At</dt>
            <dd>{finding.occurred_at}</dd>
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
