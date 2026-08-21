import type { AuditEvent, AuditEventSnapshot } from "../api/types";
import { INVESTIGATION_AREAS } from "./investigationFilters";

export type AuditEventTypeFilter =
  | "ALL"
  | "ALERT_EVALUATED"
  | "ALERT_TRIGGERED"
  | "ALERT_SKIPPED"
  | "ALERT_INVALID"
  | "ALERT_CREATED"
  | "NOTIFICATION_SENT"
  | "NOTIFICATION_FAILED"
  | "NOTIFICATION_SKIPPED"
  | "RUNNER_CYCLE_COMPLETED"
  | "RUNNER_CYCLE_FAILED"
  | "REMEDIATION_PLANNED"
  | "REMEDIATION_APPROVAL_BLOCKED"
  | "REMEDIATION_DRY_RUN"
  | "REMEDIATION_EXECUTED"
  | "REMEDIATION_FAILED"
  | "UNKNOWN";

export type AuditSeverityFilter = "ALL" | "CRITICAL" | "ERROR" | "WARNING" | "INFO" | "UNKNOWN";

export type AuditSortOption = "NEWEST" | "OLDEST" | "TYPE" | "SEVERITY";

export interface AuditFilterState {
  eventType: AuditEventTypeFilter;
  severity: AuditSeverityFilter;
  area: string;
  failuresOnly: boolean;
  recentOnly: boolean;
  targetId: string;
  alertId: string;
  search: string;
  sort: AuditSortOption;
}

export const DEFAULT_AUDIT_FILTERS: AuditFilterState = {
  eventType: "ALL",
  severity: "ALL",
  area: "ALL",
  failuresOnly: false,
  recentOnly: false,
  targetId: "",
  alertId: "",
  search: "",
  sort: "NEWEST",
};

export { INVESTIGATION_AREAS as AUDIT_AREAS };

const FAILURE_EVENT_TYPES = new Set([
  "ALERT_INVALID",
  "NOTIFICATION_FAILED",
  "RUNNER_CYCLE_FAILED",
  "REMEDIATION_FAILED",
]);

const SEVERITY_ORDER: Record<string, number> = {
  CRITICAL: 4,
  ERROR: 3,
  WARNING: 2,
  INFO: 1,
  UNKNOWN: 0,
};

export function deriveAuditArea(eventType: string): string {
  const normalized = eventType.toUpperCase();
  if (normalized.startsWith("ALERT_")) {
    return "alert";
  }
  if (normalized.startsWith("NOTIFICATION_")) {
    return "notification";
  }
  if (normalized.startsWith("RUNNER_")) {
    return "runner";
  }
  if (normalized.startsWith("REMEDIATION_")) {
    return "remediation";
  }
  return "audit";
}

export function deriveAuditSeverity(eventType: string, status?: string | null): string {
  const normalized = eventType.toUpperCase();
  if (
    FAILURE_EVENT_TYPES.has(normalized) ||
    normalized.includes("FAILED") ||
    normalized.includes("INVALID") ||
    normalized.includes("BLOCKED")
  ) {
    return "ERROR";
  }
  if (normalized === "ALERT_TRIGGERED") {
    return "WARNING";
  }
  if (status && status.toUpperCase().includes("FAIL")) {
    return "ERROR";
  }
  return "INFO";
}

export function deriveAuditTitle(event: AuditEvent): string {
  return event.event_type.replace(/_/g, " ");
}

export function isFailureAuditEvent(event: AuditEvent): boolean {
  return FAILURE_EVENT_TYPES.has(event.event_type.toUpperCase());
}

export function flattenAuditEvents(snapshots: AuditEventSnapshot[]): AuditEvent[] {
  return snapshots
    .map((snapshot) => snapshot.event)
    .filter((event): event is AuditEvent => event !== null && event !== undefined);
}

export function computeAreaCounts(events: AuditEvent[]): Record<string, number> {
  const counts: Record<string, number> = {};
  for (const event of events) {
    const area = deriveAuditArea(event.event_type);
    counts[area] = (counts[area] ?? 0) + 1;
  }
  return counts;
}

export function countFailureEvents(events: AuditEvent[]): number {
  return events.filter(isFailureAuditEvent).length;
}

function normalize(value: string | null | undefined): string {
  return (value ?? "").trim().toLowerCase();
}

function matchesSearch(event: AuditEvent, snapshot: AuditEventSnapshot, search: string): boolean {
  const query = search.trim().toLowerCase();
  if (!query) {
    return true;
  }
  const haystack = [
    event.event_id,
    event.event_type,
    event.message,
    event.status,
    event.alert_id,
    event.target_id,
    event.channel,
    snapshot.summary,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  return haystack.includes(query);
}

export function filterAuditEvents(
  snapshots: AuditEventSnapshot[],
  filters: AuditFilterState,
): AuditEventSnapshot[] {
  return snapshots.filter((snapshot) => {
    if (snapshot.read_error && !filters.failuresOnly) {
      return filters.search.trim().length === 0;
    }
    const event = snapshot.event;
    if (!event) {
      return filters.failuresOnly ? Boolean(snapshot.read_error) : false;
    }
    if (filters.failuresOnly && !isFailureAuditEvent(event)) {
      return false;
    }
    if (filters.eventType !== "ALL" && event.event_type.toUpperCase() !== filters.eventType) {
      return false;
    }
    if (
      filters.severity !== "ALL" &&
      deriveAuditSeverity(event.event_type, event.status).toUpperCase() !== filters.severity
    ) {
      return false;
    }
    if (filters.area !== "ALL" && normalize(deriveAuditArea(event.event_type)) !== normalize(filters.area)) {
      return false;
    }
    if (filters.targetId.trim()) {
      const target = normalize(event.target_id);
      if (!target.includes(normalize(filters.targetId))) {
        return false;
      }
    }
    if (filters.alertId.trim()) {
      const alert = normalize(event.alert_id);
      if (!alert.includes(normalize(filters.alertId))) {
        return false;
      }
    }
    return matchesSearch(event, snapshot, filters.search);
  });
}

function occurredTimestamp(snapshot: AuditEventSnapshot): number {
  const raw = snapshot.event?.occurred_at;
  if (!raw) {
    return 0;
  }
  const parsed = Date.parse(raw);
  return Number.isFinite(parsed) ? parsed : 0;
}

export function sortAuditSnapshots(
  snapshots: AuditEventSnapshot[],
  sort: AuditSortOption,
): AuditEventSnapshot[] {
  const sorted = [...snapshots];
  sorted.sort((left, right) => {
    if (sort === "OLDEST") {
      const timeDiff = occurredTimestamp(left) - occurredTimestamp(right);
      if (timeDiff !== 0) {
        return timeDiff;
      }
      return (left.event?.event_id ?? "").localeCompare(right.event?.event_id ?? "");
    }
    if (sort === "TYPE") {
      const typeDiff = (left.event?.event_type ?? "").localeCompare(right.event?.event_type ?? "");
      if (typeDiff !== 0) {
        return typeDiff;
      }
      return occurredTimestamp(right) - occurredTimestamp(left);
    }
    if (sort === "SEVERITY") {
      const leftSeverity = deriveAuditSeverity(left.event?.event_type ?? "", left.event?.status);
      const rightSeverity = deriveAuditSeverity(right.event?.event_type ?? "", right.event?.status);
      const severityDiff =
        (SEVERITY_ORDER[rightSeverity.toUpperCase()] ?? 0) -
        (SEVERITY_ORDER[leftSeverity.toUpperCase()] ?? 0);
      if (severityDiff !== 0) {
        return severityDiff;
      }
      return occurredTimestamp(right) - occurredTimestamp(left);
    }
    const timeDiff = occurredTimestamp(right) - occurredTimestamp(left);
    if (timeDiff !== 0) {
      return timeDiff;
    }
    return (left.event?.event_id ?? "").localeCompare(right.event?.event_id ?? "");
  });
  return sorted;
}

export function applyAuditFilters(
  snapshots: AuditEventSnapshot[],
  filters: AuditFilterState,
): AuditEventSnapshot[] {
  const filtered = filterAuditEvents(snapshots, filters);
  const sorted = sortAuditSnapshots(filtered, filters.sort);
  if (filters.recentOnly) {
    return sorted.slice(0, 10);
  }
  return sorted;
}

export function metadataString(
  metadata: Record<string, unknown>,
  key: string,
): string | null {
  const value = metadata[key];
  return typeof value === "string" ? value : null;
}
