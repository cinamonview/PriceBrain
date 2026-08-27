import { Link } from "react-router-dom";
import type { RemediationAction } from "../api/types";
import { sanitizeMetadataRecord } from "../utils/securityUtils";
import { UI, formatAreaLabel } from "../utils/uiLabels";
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
    <aside className="finding-detail-panel" aria-label="조치 상세">
      <div className="finding-detail-header">
        <h3>조치 상세</h3>
        <button type="button" onClick={onClose}>
          {UI.close}
        </button>
      </div>
      <dl className="finding-detail-list">
        <div>
          <dt>조치 ID</dt>
          <dd>{action.action_id}</dd>
        </div>
        <div>
          <dt>조치 유형</dt>
          <dd>{action.action_type}</dd>
        </div>
        <div>
          <dt>우선순위</dt>
          <dd>
            <PriorityBadge priority={action.priority} />
          </dd>
        </div>
        <div>
          <dt>위험도</dt>
          <dd>{action.risk}</dd>
        </div>
        <div>
          <dt>{UI.area}</dt>
          <dd>{formatAreaLabel(action.area)}</dd>
        </div>
        <div>
          <dt>제목</dt>
          <dd>{action.title}</dd>
        </div>
        <div>
          <dt>조치 근거</dt>
          <dd>{action.reason}</dd>
        </div>
        <div>
          <dt>원본 발견 사항</dt>
          <dd>
            {action.finding_id}
            <div className="action-card-links">
              <Link to="/investigation">{UI.viewFinding}</Link>
            </div>
          </dd>
        </div>
        {action.target_id ? (
          <div>
            <dt>대상 ID</dt>
            <dd>
              <ResourceRef kind="Target" value={action.target_id} />
            </dd>
          </div>
        ) : null}
        {action.alert_id ? (
          <div>
            <dt>알림 ID</dt>
            <dd>
              <ResourceRef kind="Alert" value={action.alert_id} />
            </dd>
          </div>
        ) : null}
        <div>
          <dt>필요 승인</dt>
          <dd>{action.human_approval_required ? UI.humanApprovalRequired : UI.notRequired}</dd>
        </div>
        <div>
          <dt>실행 정책</dt>
          <dd>
            {action.auto_executable
              ? "정책상 자동 실행 허용됨"
              : "자동 실행 비활성화 — 계획 검토만 가능"}
          </dd>
        </div>
        {action.recommended_steps.length > 0 ? (
          <div>
            <dt>권장 단계</dt>
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
            <dt>전제 조건</dt>
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
            <dt>{UI.readError}</dt>
            <dd className="read-error">{action.read_error}</dd>
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
