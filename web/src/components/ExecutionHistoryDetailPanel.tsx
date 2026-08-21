import { Link } from "react-router-dom";
import type { ExecutionHistoryEntry } from "../api/types";
import { formatAreaLabel } from "../utils/investigationFilters";
import { statusHint } from "../utils/executionFilters";
import { sanitizeMetadataRecord } from "../utils/securityUtils";
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
    <aside className="finding-detail-panel" aria-label="Execution history detail">
      <div className="finding-detail-header">
        <h3>Execution Detail</h3>
        <button type="button" onClick={onClose}>
          Close
        </button>
      </div>
      <dl className="finding-detail-list">
        <div>
          <dt>Execution ID</dt>
          <dd>{entry.execution_id}</dd>
        </div>
        <div>
          <dt>Action ID</dt>
          <dd>{entry.action_id}</dd>
        </div>
        <div>
          <dt>Action Type</dt>
          <dd>{entry.action_type}</dd>
        </div>
        <div>
          <dt>Mode</dt>
          <dd>{entry.mode}</dd>
        </div>
        <div>
          <dt>Status</dt>
          <dd>
            <ExecutionStatusBadge status={entry.status} />
          </dd>
        </div>
        <div>
          <dt>Area</dt>
          <dd>{formatAreaLabel(entry.area)}</dd>
        </div>
        {entry.target_id ? (
          <div>
            <dt>Target</dt>
            <dd>
              <ResourceRef kind="Target" value={entry.target_id} />
            </dd>
          </div>
        ) : null}
        {entry.alert_id ? (
          <div>
            <dt>Alert</dt>
            <dd>
              <ResourceRef kind="Alert" value={entry.alert_id} />
            </dd>
          </div>
        ) : null}
        <div>
          <dt>Started At</dt>
          <dd>{entry.started_at ?? "-"}</dd>
        </div>
        <div>
          <dt>Completed At</dt>
          <dd>{entry.completed_at ?? "-"}</dd>
        </div>
        <div>
          <dt>Occurred At</dt>
          <dd>{entry.occurred_at ?? "-"}</dd>
        </div>
        <div>
          <dt>Duration</dt>
          <dd>{formatDuration(entry.duration_ms)}</dd>
        </div>
        <div>
          <dt>Mutation Performed</dt>
          <dd>{entry.mutation_performed ? "Yes" : "No"}</dd>
        </div>
        <div>
          <dt>Approval Verified</dt>
          <dd>{entry.approval_verified ? "Yes" : "No"}</dd>
        </div>
        <div>
          <dt>Execution Policy</dt>
          <dd>{statusHint(entry.status)}</dd>
        </div>
        <div>
          <dt>Result / Message</dt>
          <dd>{entry.message || "-"}</dd>
        </div>
        {entry.error_code ? (
          <div>
            <dt>Failure Reason</dt>
            <dd>{entry.error_code}</dd>
          </div>
        ) : null}
        {findingId ? (
          <div>
            <dt>Source Finding</dt>
            <dd>
              {findingId}
              <div className="action-card-links">
                <Link to="/investigation">View Finding</Link>
              </div>
            </dd>
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
