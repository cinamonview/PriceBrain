import { Link } from "react-router-dom";
import type { RemediationAction } from "../api/types";
import { formatAreaLabel } from "../utils/investigationFilters";
import { PriorityBadge } from "./PriorityBadge";
import { ResourceRef } from "./ResourceRef";

interface RemediationActionCardProps {
  action: RemediationAction;
  selected?: boolean;
  onSelect: (action: RemediationAction) => void;
}

export function RemediationActionCard({
  action,
  selected = false,
  onSelect,
}: RemediationActionCardProps) {
  const priority = action.priority.toUpperCase();

  return (
    <button
      type="button"
      className={`finding-card priority-border-${priority.toLowerCase()}${selected ? " selected" : ""}`}
      onClick={() => onSelect(action)}
      aria-pressed={selected}
    >
      <div className="finding-card-header">
        <PriorityBadge priority={action.priority} />
        <span className="finding-code">{action.action_type}</span>
      </div>
      <h4>{action.title}</h4>
      <p className="finding-cause-label">Rationale:</p>
      <p className="finding-message">{action.reason}</p>
      <div className="finding-meta-grid">
        <div>
          <span className="meta-label">Action ID</span>
          <span>{action.action_id}</span>
        </div>
        <div>
          <span className="meta-label">Area</span>
          <span>{formatAreaLabel(action.area)}</span>
        </div>
        {action.target_id ? (
          <div>
            <span className="meta-label">Target</span>
            <ResourceRef kind="Target" value={action.target_id} />
          </div>
        ) : null}
        {action.alert_id ? (
          <div>
            <span className="meta-label">Alert</span>
            <ResourceRef kind="Alert" value={action.alert_id} />
          </div>
        ) : null}
        <div>
          <span className="meta-label">Source finding</span>
          <span>{action.finding_id}</span>
        </div>
        <div>
          <span className="meta-label">Approval</span>
          <span>{action.human_approval_required ? "Required" : "Not required"}</span>
        </div>
        <div>
          <span className="meta-label">Auto executable</span>
          <span>{action.auto_executable ? "Yes" : "No"}</span>
        </div>
      </div>
      <div className="action-card-links">
        <Link to="/investigation" onClick={(event) => event.stopPropagation()}>
          View Finding
        </Link>
        <span className="muted">Review Action</span>
      </div>
    </button>
  );
}
