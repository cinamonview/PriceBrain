import type { InvestigationFinding } from "../api/types";
import { sanitizeMetadataRecord } from "../utils/securityUtils";
import { formatAreaLabel } from "../utils/investigationFilters";
import { UI, formatFindingTitle } from "../utils/uiLabels";
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
    <aside className="finding-detail-panel" aria-label="발견 사항 상세">
      <div className="finding-detail-header">
        <h3>발견 사항 상세</h3>
        <button type="button" onClick={onClose}>
          {UI.close}
        </button>
      </div>
      <dl className="finding-detail-list">
        <div>
          <dt>발견 코드</dt>
          <dd>{finding.code}</dd>
        </div>
        <div>
          <dt>{UI.severity}</dt>
          <dd>
            <SeverityBadge severity={finding.severity} />
          </dd>
        </div>
        <div>
          <dt>{UI.area}</dt>
          <dd>{formatAreaLabel(finding.area)}</dd>
        </div>
        <div>
          <dt>제목</dt>
          <dd>{formatFindingTitle(finding.code, finding.title)}</dd>
        </div>
        <div>
          <dt>{UI.message}</dt>
          <dd>{finding.message}</dd>
        </div>
        {finding.target_id ? (
          <div>
            <dt>대상 ID</dt>
            <dd>
              <ResourceRef kind="Target" value={finding.target_id} />
            </dd>
          </div>
        ) : null}
        {finding.alert_id ? (
          <div>
            <dt>알림 ID</dt>
            <dd>
              <ResourceRef kind="Alert" value={finding.alert_id} />
            </dd>
          </div>
        ) : null}
        {finding.event_id ? (
          <div>
            <dt>이벤트 ID</dt>
            <dd>{finding.event_id}</dd>
          </div>
        ) : null}
        {finding.occurred_at ? (
          <div>
            <dt>발생 시각</dt>
            <dd>{finding.occurred_at}</dd>
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
