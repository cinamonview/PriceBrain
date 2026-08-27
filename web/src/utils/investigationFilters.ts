import type { InvestigationFinding } from "../api/types";

export type SeverityFilter = "ALL" | "CRITICAL" | "ERROR" | "WARNING" | "INFO";

export interface InvestigationFilterState {
  severity: SeverityFilter;
  area: string;
  failuresOnly: boolean;
  targetId: string;
  alertId: string;
  search: string;
}

export const DEFAULT_INVESTIGATION_FILTERS: InvestigationFilterState = {
  severity: "ALL",
  area: "ALL",
  failuresOnly: false,
  targetId: "",
  alertId: "",
  search: "",
};

export const INVESTIGATION_AREAS = [
  "crawler",
  "price",
  "alert",
  "notification",
  "runner",
  "audit",
] as const;

function normalize(value: string | null | undefined): string {
  return (value ?? "").trim().toLowerCase();
}

function matchesSearch(finding: InvestigationFinding, search: string): boolean {
  const query = search.trim().toLowerCase();
  if (!query) {
    return true;
  }
  const haystack = [
    finding.code,
    finding.title,
    finding.message,
    finding.area,
    finding.target_id,
    finding.alert_id,
    finding.event_id,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  return haystack.includes(query);
}

export function filterInvestigationFindings(
  findings: InvestigationFinding[],
  filters: InvestigationFilterState,
): InvestigationFinding[] {
  return findings.filter((finding) => {
    if (filters.failuresOnly && finding.severity.toUpperCase() === "INFO") {
      return false;
    }
    if (filters.severity !== "ALL" && finding.severity.toUpperCase() !== filters.severity) {
      return false;
    }
    if (filters.area !== "ALL" && normalize(finding.area) !== normalize(filters.area)) {
      return false;
    }
    if (filters.targetId.trim()) {
      const target = normalize(finding.target_id);
      if (!target.includes(normalize(filters.targetId))) {
        return false;
      }
    }
    if (filters.alertId.trim()) {
      const alert = normalize(finding.alert_id);
      if (!alert.includes(normalize(filters.alertId))) {
        return false;
      }
    }
    return matchesSearch(finding, filters.search);
  });
}

export { formatAreaLabel } from "./uiLabels";
