import { Link } from "react-router-dom";
import type { RemediationAction } from "../api/types";
import { UI, formatAreaLabel, formatYesNo } from "../utils/uiLabels";
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
      <p className="finding-cause-label">근거:</p>
      <p className="finding-message">{action.reason}</p>
      <div className="finding-meta-grid">
        <div>
          <span className="meta-label">조치 ID</span>
          <span>{action.action_id}</span>
        </div>
        <div>
          <span className="meta-label">{UI.area}</span>
          <span>{formatAreaLabel(action.area)}</span>
        </div>
        {action.target_id ? (
          <div>
            <span className="meta-label">{UI.target}</span>
            <ResourceRef kind="Target" value={action.target_id} />
          </div>
        ) : null}
        {action.alert_id ? (
          <div>
            <span className="meta-label">{UI.alert}</span>
            <ResourceRef kind="Alert" value={action.alert_id} />
          </div>
        ) : null}
        <div>
          <span className="meta-label">원본 발견 사항</span>
          <span>{action.finding_id}</span>
        </div>
        <div>
          <span className="meta-label">{UI.approvalRequired}</span>
          <span>{action.human_approval_required ? UI.required : UI.notRequired}</span>
        </div>
        <div>
          <span className="meta-label">자동 실행 가능</span>
          <span>{formatYesNo(action.auto_executable)}</span>
        </div>
      </div>
      <div className="action-card-links">
        <Link to="/investigation" onClick={(event) => event.stopPropagation()}>
          {UI.viewFinding}
        </Link>
        <span className="muted">{UI.reviewAction}</span>
      </div>
    </button>
  );
}
