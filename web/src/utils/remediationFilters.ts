import type { RemediationAction } from "../api/types";
import { INVESTIGATION_AREAS } from "./investigationFilters";

export type PriorityFilter = "ALL" | "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";

export interface RemediationFilterState {
  priority: PriorityFilter;
  area: string;
  failuresOnly: boolean;
  targetId: string;
  alertId: string;
  search: string;
}

export const DEFAULT_REMEDIATION_FILTERS: RemediationFilterState = {
  priority: "ALL",
  area: "ALL",
  failuresOnly: false,
  targetId: "",
  alertId: "",
  search: "",
};

export { INVESTIGATION_AREAS as REMEDIATION_AREAS };

function normalize(value: string | null | undefined): string {
  return (value ?? "").trim().toLowerCase();
}

function matchesSearch(action: RemediationAction, search: string): boolean {
  const query = search.trim().toLowerCase();
  if (!query) {
    return true;
  }
  const haystack = [
    action.action_id,
    action.action_type,
    action.title,
    action.reason,
    action.area,
    action.finding_id,
    action.target_id,
    action.alert_id,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  return haystack.includes(query);
}

export function filterRemediationActions(
  actions: RemediationAction[],
  filters: RemediationFilterState,
): RemediationAction[] {
  return actions.filter((action) => {
    if (filters.failuresOnly && action.action_type === "NO_ACTION") {
      return false;
    }
    if (filters.priority !== "ALL" && action.priority.toUpperCase() !== filters.priority) {
      return false;
    }
    if (filters.area !== "ALL" && normalize(action.area) !== normalize(filters.area)) {
      return false;
    }
    if (filters.targetId.trim()) {
      const target = normalize(action.target_id);
      if (!target.includes(normalize(filters.targetId))) {
        return false;
      }
    }
    if (filters.alertId.trim()) {
      const alert = normalize(action.alert_id);
      if (!alert.includes(normalize(filters.alertId))) {
        return false;
      }
    }
    return matchesSearch(action, filters.search);
  });
}

export function priorityCount(
  byPriority: Record<string, number>,
  priority: string,
): number {
  return byPriority[priority] ?? 0;
}
