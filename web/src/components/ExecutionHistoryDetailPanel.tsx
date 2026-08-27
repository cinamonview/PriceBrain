import { Link } from "react-router-dom";
import type { ExecutionHistoryEntry } from "../api/types";
import { statusHint } from "../utils/executionFilters";
import { sanitizeMetadataRecord } from "../utils/securityUtils";
import { UI, formatAreaLabel, formatYesNo } from "../utils/uiLabels";
import { ExecutionStatusBadge } from "./ExecutionStatusBadge";
import { ResourceRef } from "./ResourceRef";

interface ExecutionHistoryDetailPanelProps {
  entry: ExecutionHistoryEntry | null;
  onClose: () => void;
}

function formatDuration(durationMs: number | null | undefined): string {
  if (durationMs === null || durationMs === undefined) {
    return "-";
  }
  return `${durationMs} ms`;
}

function findingIdFromMetadata(metadata: Record<string, unknown>): string | null {
  const value = metadata.finding_id;
  return typeof value === "string" ? value : null;
}

export function ExecutionHistoryDetailPanel({
  entry,
  onClose,
}: ExecutionHistoryDetailPanelProps) {
  if (!entry) {
    return null;
  }

  const metadata =
    entry.metadata && Object.keys(entry.metadata).length > 0
      ? sanitizeMetadataRecord(entry.metadata)
      : null;
  const findingId = findingIdFromMetadata(entry.metadata);

  return (
    <aside className="finding-detail-panel" aria-label="실행 이력 상세">
      <div className="finding-detail-header">
        <h3>실행 상세</h3>
        <button type="button" onClick={onClose}>
          {UI.close}
        </button>
      </div>
      <dl className="finding-detail-list">
        <div>
          <dt>실행 ID</dt>
          <dd>{entry.execution_id}</dd>
        </div>
        <div>
          <dt>조치 ID</dt>
          <dd>{entry.action_id}</dd>
        </div>
        <div>
          <dt>조치 유형</dt>
          <dd>{entry.action_type}</dd>
        </div>
        <div>
          <dt>실행 모드</dt>
          <dd>{entry.mode}</dd>
        </div>
        <div>
          <dt>{UI.status}</dt>
          <dd>
            <ExecutionStatusBadge status={entry.status} />
          </dd>
        </div>
        <div>
          <dt>{UI.area}</dt>
          <dd>{formatAreaLabel(entry.area)}</dd>
        </div>
        {entry.target_id ? (
          <div>
            <dt>{UI.target}</dt>
            <dd>
              <ResourceRef kind="Target" value={entry.target_id} />
            </dd>
          </div>
        ) : null}
        {entry.alert_id ? (
          <div>
            <dt>{UI.alert}</dt>
            <dd>
              <ResourceRef kind="Alert" value={entry.alert_id} />
            </dd>
          </div>
        ) : null}
        <div>
          <dt>시작 시각</dt>
          <dd>{entry.started_at ?? "-"}</dd>
        </div>
        <div>
          <dt>완료 시각</dt>
          <dd>{entry.completed_at ?? "-"}</dd>
        </div>
        <div>
          <dt>발생 시각</dt>
          <dd>{entry.occurred_at ?? "-"}</dd>
        </div>
        <div>
          <dt>소요 시간</dt>
          <dd>{formatDuration(entry.duration_ms)}</dd>
        </div>
        <div>
          <dt>변경 수행</dt>
          <dd>{formatYesNo(entry.mutation_performed)}</dd>
        </div>
        <div>
          <dt>승인 확인</dt>
          <dd>{formatYesNo(entry.approval_verified)}</dd>
        </div>
        <div>
          <dt>실행 정책</dt>
          <dd>{statusHint(entry.status)}</dd>
        </div>
        <div>
          <dt>결과 / 메시지</dt>
          <dd>{entry.message || "-"}</dd>
        </div>
        {entry.error_code ? (
          <div>
            <dt>실패 사유</dt>
            <dd>{entry.error_code}</dd>
          </div>
        ) : null}
        {findingId ? (
          <div>
            <dt>원본 발견 사항</dt>
            <dd>
              {findingId}
              <div className="action-card-links">
                <Link to="/investigation">{UI.viewFinding}</Link>
              </div>
            </dd>
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
