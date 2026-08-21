import { Link } from "react-router-dom";
import type { ExecutionHistoryEntry } from "../api/types";
import { formatAreaLabel } from "../utils/investigationFilters";
import { statusHint } from "../utils/executionFilters";
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
      <p className="finding-cause-label">Result:</p>
      <p className="finding-message">{entry.message || entry.error_code || "-"}</p>
      <div className="finding-meta-grid">
        <div>
          <span className="meta-label">Execution ID</span>
          <span>{entry.execution_id}</span>
        </div>
        <div>
          <span className="meta-label">Action ID</span>
          <span>{entry.action_id}</span>
        </div>
        <div>
          <span className="meta-label">Area</span>
          <span>{formatAreaLabel(entry.area)}</span>
        </div>
        {entry.target_id ? (
          <div>
            <span className="meta-label">Target</span>
            <ResourceRef kind="Target" value={entry.target_id} />
          </div>
        ) : null}
        {entry.alert_id ? (
          <div>
            <span className="meta-label">Alert</span>
            <ResourceRef kind="Alert" value={entry.alert_id} />
          </div>
        ) : null}
        <div>
          <span className="meta-label">Occurred</span>
          <span>{entry.occurred_at ?? entry.started_at ?? "-"}</span>
        </div>
        <div>
          <span className="meta-label">Duration</span>
          <span>{formatDuration(entry.duration_ms)}</span>
        </div>
        <div>
          <span className="meta-label">Mutation</span>
          <span>{entry.mutation_performed ? "Yes" : "No"}</span>
        </div>
        <div>
          <span className="meta-label">Approval verified</span>
          <span>{entry.approval_verified ? "Yes" : "No"}</span>
        </div>
      </div>
      <p className="finding-hint">{statusHint(entry.status)}</p>
      <div className="action-card-links">
        {findingId ? (
          <Link to="/investigation" onClick={(event) => event.stopPropagation()}>
            View Finding
          </Link>
        ) : null}
        <span className="muted">View Details</span>
      </div>
    </button>
  );
}
