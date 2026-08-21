import type { ExecutionHistoryEntry, ExecutionHistorySnapshot } from "../api/types";
import { INVESTIGATION_AREAS } from "./investigationFilters";

export type ExecutionStatusFilter =
  | "ALL"
  | "PLANNED"
  | "DRY_RUN"
  | "EXECUTED"
  | "BLOCKED"
  | "FAILED"
  | "APPROVED"
  | "SKIPPED"
  | "UNKNOWN";

export type ExecutionModeFilter = "ALL" | "PLAN" | "DRY_RUN" | "EXECUTE";

export type ExecutionSortOption = "NEWEST" | "OLDEST" | "STATUS" | "DURATION";

export interface ExecutionFilterState {
  status: ExecutionStatusFilter;
  mode: ExecutionModeFilter;
  area: string;
  failuresOnly: boolean;
  recentOnly: boolean;
  targetId: string;
  alertId: string;
  search: string;
  sort: ExecutionSortOption;
}

export const DEFAULT_EXECUTION_FILTERS: ExecutionFilterState = {
  status: "ALL",
  mode: "ALL",
  area: "ALL",
  failuresOnly: false,
  recentOnly: false,
  targetId: "",
  alertId: "",
  search: "",
  sort: "NEWEST",
};

export { INVESTIGATION_AREAS as EXECUTION_AREAS };

const STATUS_ORDER: Record<string, number> = {
  FAILED: 6,
  BLOCKED: 5,
  EXECUTED: 4,
  APPROVED: 3,
  DRY_RUN: 2,
  PLANNED: 1,
  SKIPPED: 0,
  UNKNOWN: 0,
};

function normalize(value: string | null | undefined): string {
  return (value ?? "").trim().toLowerCase();
}

export function flattenExecutionEntries(
  snapshots: ExecutionHistorySnapshot[],
): ExecutionHistoryEntry[] {
  return snapshots
    .map((snapshot) => snapshot.entry)
    .filter((entry): entry is ExecutionHistoryEntry => entry !== null && entry !== undefined);
}

function matchesSearch(entry: ExecutionHistoryEntry, search: string): boolean {
  const query = search.trim().toLowerCase();
  if (!query) {
    return true;
  }
  const haystack = [
    entry.execution_id,
    entry.action_id,
    entry.action_type,
    entry.title,
    entry.message,
    entry.status,
    entry.mode,
    entry.area,
    entry.target_id,
    entry.alert_id,
    entry.error_code,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  return haystack.includes(query);
}

export function filterExecutionEntries(
  entries: ExecutionHistoryEntry[],
  filters: ExecutionFilterState,
): ExecutionHistoryEntry[] {
  return entries.filter((entry) => {
    if (filters.failuresOnly && entry.status.toUpperCase() !== "FAILED") {
      return false;
    }
    if (filters.status !== "ALL" && entry.status.toUpperCase() !== filters.status) {
      return false;
    }
    if (filters.mode !== "ALL" && entry.mode.toUpperCase() !== filters.mode) {
      return false;
    }
    if (filters.area !== "ALL" && normalize(entry.area) !== normalize(filters.area)) {
      return false;
    }
    if (filters.targetId.trim()) {
      const target = normalize(entry.target_id);
      if (!target.includes(normalize(filters.targetId))) {
        return false;
      }
    }
    if (filters.alertId.trim()) {
      const alert = normalize(entry.alert_id);
      if (!alert.includes(normalize(filters.alertId))) {
        return false;
      }
    }
    return matchesSearch(entry, filters.search);
  });
}

function occurredTimestamp(entry: ExecutionHistoryEntry): number {
  const raw = entry.occurred_at ?? entry.started_at ?? entry.completed_at;
  if (!raw) {
    return 0;
  }
  const parsed = Date.parse(raw);
  return Number.isFinite(parsed) ? parsed : 0;
}

export function sortExecutionEntries(
  entries: ExecutionHistoryEntry[],
  sort: ExecutionSortOption,
): ExecutionHistoryEntry[] {
  const sorted = [...entries];
  sorted.sort((left, right) => {
    if (sort === "OLDEST") {
      const timeDiff = occurredTimestamp(left) - occurredTimestamp(right);
      if (timeDiff !== 0) {
        return timeDiff;
      }
      return left.execution_id.localeCompare(right.execution_id);
    }
    if (sort === "STATUS") {
      const statusDiff =
        (STATUS_ORDER[right.status.toUpperCase()] ?? 0) -
        (STATUS_ORDER[left.status.toUpperCase()] ?? 0);
      if (statusDiff !== 0) {
        return statusDiff;
      }
      return left.execution_id.localeCompare(right.execution_id);
    }
    if (sort === "DURATION") {
      const durationDiff = (right.duration_ms ?? 0) - (left.duration_ms ?? 0);
      if (durationDiff !== 0) {
        return durationDiff;
      }
      return left.execution_id.localeCompare(right.execution_id);
    }
    const timeDiff = occurredTimestamp(right) - occurredTimestamp(left);
    if (timeDiff !== 0) {
      return timeDiff;
    }
    return left.execution_id.localeCompare(right.execution_id);
  });
  return sorted;
}

export function applyExecutionFilters(
  snapshots: ExecutionHistorySnapshot[],
  filters: ExecutionFilterState,
): ExecutionHistoryEntry[] {
  const filtered = filterExecutionEntries(flattenExecutionEntries(snapshots), filters);
  const sorted = sortExecutionEntries(filtered, filters.sort);
  if (filters.recentOnly) {
    return sorted.slice(0, 10);
  }
  return sorted;
}

export function statusHint(status: string): string {
  switch (status.toUpperCase()) {
    case "PLANNED":
      return "계획만 생성된 상태";
    case "DRY_RUN":
      return "실제 mutation 없이 검증된 상태";
    case "EXECUTED":
      return "승인된 executor 호출 결과";
    case "BLOCKED":
      return "approval/security 경계에 의해 실행되지 않은 상태";
    case "FAILED":
      return "execution 과정에서 실패한 상태";
    case "APPROVED":
      return "승인은 확인되었으나 실행 전/중 상태";
    default:
      return "상태 확인 필요";
  }
}
