import { Link } from "react-router-dom";
import type { ExecutionHistoryEntry } from "../api/types";
import { statusHint } from "../utils/executionFilters";
import { UI, formatAreaLabel, formatYesNo } from "../utils/uiLabels";
import { ExecutionStatusBadge } from "./ExecutionStatusBadge";
import { ResourceRef } from "./ResourceRef";

interface ExecutionHistoryCardProps {
  entry: ExecutionHistoryEntry;
  selected?: boolean;
  onSelect: (entry: ExecutionHistoryEntry) => void;
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

export function ExecutionHistoryCard({
  entry,
  selected = false,
  onSelect,
}: ExecutionHistoryCardProps) {
  const normalized = entry.status.toUpperCase();
  const findingId = findingIdFromMetadata(entry.metadata);

  return (
    <button
      type="button"
      className={`finding-card execution-status-border-${normalized.toLowerCase()}${selected ? " selected" : ""}`}
      onClick={() => onSelect(entry)}
      aria-pressed={selected}
    >
      <div className="finding-card-header">
        <ExecutionStatusBadge status={entry.status} />
        <span className="finding-code">{entry.mode}</span>
      </div>
      <h4>{entry.title || entry.action_type}</h4>
      <p className="finding-cause-label">결과:</p>
      <p className="finding-message">{entry.message || entry.error_code || "-"}</p>
      <div className="finding-meta-grid">
        <div>
          <span className="meta-label">실행 ID</span>
          <span>{entry.execution_id}</span>
        </div>
        <div>
          <span className="meta-label">조치 ID</span>
          <span>{entry.action_id}</span>
        </div>
        <div>
          <span className="meta-label">{UI.area}</span>
          <span>{formatAreaLabel(entry.area)}</span>
        </div>
        {entry.target_id ? (
          <div>
            <span className="meta-label">{UI.target}</span>
            <ResourceRef kind="Target" value={entry.target_id} />
          </div>
        ) : null}
        {entry.alert_id ? (
          <div>
            <span className="meta-label">{UI.alert}</span>
            <ResourceRef kind="Alert" value={entry.alert_id} />
          </div>
        ) : null}
        <div>
          <span className="meta-label">{UI.occurred}</span>
          <span>{entry.occurred_at ?? entry.started_at ?? "-"}</span>
        </div>
        <div>
          <span className="meta-label">소요 시간</span>
          <span>{formatDuration(entry.duration_ms)}</span>
        </div>
        <div>
          <span className="meta-label">변경 수행</span>
          <span>{formatYesNo(entry.mutation_performed)}</span>
        </div>
        <div>
          <span className="meta-label">승인 확인</span>
          <span>{formatYesNo(entry.approval_verified)}</span>
        </div>
      </div>
      <p className="finding-hint">{statusHint(entry.status)}</p>
      <div className="action-card-links">
        {findingId ? (
          <Link to="/investigation" onClick={(event) => event.stopPropagation()}>
            {UI.viewFinding}
          </Link>
        ) : null}
        <span className="muted">{UI.details}</span>
      </div>
    </button>
  );
}
