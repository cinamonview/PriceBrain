import { Link } from "react-router-dom";
import type { RemediationAction } from "../api/types";
import { formatAreaLabel } from "../utils/investigationFilters";
import { sanitizeMetadataRecord } from "../utils/securityUtils";
import { PriorityBadge } from "./PriorityBadge";
import { ResourceRef } from "./ResourceRef";

interface RemediationActionDetailPanelProps {
  action: RemediationAction | null;
  onClose: () => void;
}

export function RemediationActionDetailPanel({
  action,
  onClose,
}: RemediationActionDetailPanelProps) {
  if (!action) {
    return null;
  }

  const metadata =
    action.metadata && Object.keys(action.metadata).length > 0
      ? sanitizeMetadataRecord(action.metadata)
      : null;

  return (
    <aside className="finding-detail-panel" aria-label="Remediation action detail">
      <div className="finding-detail-header">
        <h3>Action Detail</h3>
        <button type="button" onClick={onClose}>
          Close
        </button>
      </div>
      <dl className="finding-detail-list">
        <div>
          <dt>Action ID</dt>
          <dd>{action.action_id}</dd>
        </div>
        <div>
          <dt>Action Type</dt>
          <dd>{action.action_type}</dd>
        </div>
        <div>
          <dt>Priority</dt>
          <dd>
            <PriorityBadge priority={action.priority} />
          </dd>
        </div>
        <div>
          <dt>Risk</dt>
          <dd>{action.risk}</dd>
        </div>
        <div>
          <dt>Area</dt>
          <dd>{formatAreaLabel(action.area)}</dd>
        </div>
        <div>
          <dt>Title</dt>
          <dd>{action.title}</dd>
        </div>
        <div>
          <dt>Remediation Rationale</dt>
          <dd>{action.reason}</dd>
        </div>
        <div>
          <dt>Source Finding</dt>
          <dd>
            {action.finding_id}
            <div className="action-card-links">
              <Link to="/investigation">View Finding</Link>
            </div>
          </dd>
        </div>
        {action.target_id ? (
          <div>
            <dt>Target ID</dt>
            <dd>
              <ResourceRef kind="Target" value={action.target_id} />
            </dd>
          </div>
        ) : null}
        {action.alert_id ? (
          <div>
            <dt>Alert ID</dt>
            <dd>
              <ResourceRef kind="Alert" value={action.alert_id} />
            </dd>
          </div>
        ) : null}
        <div>
          <dt>Required Approval</dt>
          <dd>{action.human_approval_required ? "Human approval required" : "Not required"}</dd>
        </div>
        <div>
          <dt>Execution Policy</dt>
          <dd>
            {action.auto_executable
              ? "Auto execution allowed by policy flag"
              : "Auto execution disabled — plan review only"}
          </dd>
        </div>
        {action.recommended_steps.length > 0 ? (
          <div>
            <dt>Recommended Steps</dt>
            <dd>
              <ul className="metric-list">
                {action.recommended_steps.map((step) => (
                  <li key={step}>{step}</li>
                ))}
              </ul>
            </dd>
          </div>
        ) : null}
        {action.preconditions.length > 0 ? (
          <div>
            <dt>Preconditions</dt>
            <dd>
              <ul className="metric-list">
                {action.preconditions.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </dd>
          </div>
        ) : null}
        {action.read_error ? (
          <div>
            <dt>Read Error</dt>
            <dd className="read-error">{action.read_error}</dd>
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
