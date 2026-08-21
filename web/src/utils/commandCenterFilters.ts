import type {
  AuditEvent,
  CommandCenterResponse,
  InvestigationFinding,
  RemediationAction,
} from "../api/types";
import { deriveAuditSeverity } from "./auditFilters";

export interface CommandCenterFilterState {
  failuresOnly: boolean;
  area: string;
  severity: string;
  recentOnly: boolean;
  search: string;
}

export const DEFAULT_COMMAND_CENTER_FILTERS: CommandCenterFilterState = {
  failuresOnly: false,
  area: "ALL",
  severity: "ALL",
  recentOnly: false,
  search: "",
};

function normalize(value: string | null | undefined): string {
  return (value ?? "").trim().toLowerCase();
}

function matchesSearchFinding(finding: InvestigationFinding, search: string): boolean {
  const query = search.trim().toLowerCase();
  if (!query) {
    return true;
  }
  const haystack = [
    finding.finding_id,
    finding.code,
    finding.title,
    finding.message,
    finding.area,
    finding.target_id,
    finding.alert_id,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  return haystack.includes(query);
}

export function filterFindings(
  findings: InvestigationFinding[],
  filters: CommandCenterFilterState,
): InvestigationFinding[] {
  return findings.filter((finding) => {
    if (filters.failuresOnly) {
      const severity = finding.severity.toUpperCase();
      if (severity !== "CRITICAL" && severity !== "ERROR") {
        return false;
      }
    }
    if (filters.severity !== "ALL" && finding.severity.toUpperCase() !== filters.severity) {
      return false;
    }
    if (filters.area !== "ALL" && normalize(finding.area) !== normalize(filters.area)) {
      return false;
    }
    return matchesSearchFinding(finding, filters.search);
  });
}

export function groupFindingsBySeverity(
  findings: InvestigationFinding[],
): Record<"CRITICAL" | "ERROR" | "WARNING", InvestigationFinding[]> {
  return {
    CRITICAL: findings.filter((item) => item.severity.toUpperCase() === "CRITICAL"),
    ERROR: findings.filter((item) => item.severity.toUpperCase() === "ERROR"),
    WARNING: findings.filter((item) => item.severity.toUpperCase() === "WARNING"),
  };
}

export function parseDashboardAuditEvent(snapshot: Record<string, unknown>): AuditEvent | null {
  const event = snapshot.event;
  if (!event || typeof event !== "object" || Array.isArray(event)) {
    return null;
  }
  const record = event as Record<string, unknown>;
  if (!record.event_id || !record.event_type || !record.occurred_at) {
    return null;
  }
  return {
    event_id: String(record.event_id),
    event_type: String(record.event_type),
    occurred_at: String(record.occurred_at),
    alert_id: record.alert_id ? String(record.alert_id) : null,
    target_id: record.target_id ? String(record.target_id) : null,
    mall_id: record.mall_id ? String(record.mall_id) : null,
    channel: record.channel ? String(record.channel) : null,
    status: record.status ? String(record.status) : null,
    message: record.message ? String(record.message) : null,
    metadata: typeof record.metadata === "object" && record.metadata ? (record.metadata as Record<string, unknown>) : {},
  };
}

export function getRecentAuditEvents(
  data: CommandCenterResponse,
  limit = 8,
): Array<{ event: AuditEvent; summary: string }> {
  const events = data.dashboard.audit.event_snapshots
    .map((snapshot) => {
      const event = parseDashboardAuditEvent(snapshot);
      if (!event) {
        return null;
      }
      return {
        event,
        summary: isString(snapshot.summary) ? snapshot.summary : "",
      };
    })
    .filter((item): item is { event: AuditEvent; summary: string } => item !== null);
  return events.slice(0, limit);
}

function isString(value: unknown): value is string {
  return typeof value === "string";
}

export function filterAuditEventsForCommandCenter(
  events: Array<{ event: AuditEvent; summary: string }>,
  filters: CommandCenterFilterState,
): Array<{ event: AuditEvent; summary: string }> {
  return events.filter(({ event, summary }) => {
    if (filters.failuresOnly) {
      const severity = deriveAuditSeverity(event.event_type, event.status).toUpperCase();
      if (severity !== "ERROR" && severity !== "CRITICAL") {
        return false;
      }
    }
    if (filters.search.trim()) {
      const query = filters.search.trim().toLowerCase();
      const haystack = [event.event_id, event.event_type, event.message, summary, event.target_id, event.alert_id]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      if (!haystack.includes(query)) {
        return false;
      }
    }
    return true;
  });
}

export function countReadErrors(data: CommandCenterResponse): number {
  let count =
    (data.investigation.summary.read_errors ?? 0) +
    (data.remediation.read_errors ?? 0) +
    (data.execution.summary.read_errors ?? 0);
  const sections = [
    data.dashboard.crawler,
    data.dashboard.price,
    data.dashboard.alerts,
    data.dashboard.notifications,
    data.dashboard.runner,
    data.dashboard.audit,
  ];
  for (const section of sections) {
    if (section.read_error) {
      count += 1;
    }
  }
  return count;
}

export function countOperationalFailures(data: CommandCenterResponse): number {
  return (
    (data.investigation.summary.critical_count ?? 0) +
    (data.investigation.summary.error_count ?? 0) +
    (data.execution.summary.failed ?? 0) +
    (data.execution.summary.recent_failures ?? 0) +
    (data.dashboard.audit.recent_failures ?? 0) +
    (data.dashboard.notifications.failed ?? 0) +
    (data.dashboard.runner.recent_failed_cycles ?? 0) +
    (data.dashboard.crawler.recent_failures ?? 0)
  );
}

export function topRemediationActions(actions: RemediationAction[], limit = 5): RemediationAction[] {
  return actions.slice(0, limit);
}
