import { describe, expect, it } from "vitest";
import type { InvestigationFinding } from "../api/types";
import {
  DEFAULT_INVESTIGATION_FILTERS,
  filterInvestigationFindings,
} from "../utils/investigationFilters";

const findings: InvestigationFinding[] = [
  {
    finding_id: "f-critical",
    severity: "CRITICAL",
    area: "runner",
    code: "RUNNER_CYCLE_FAILURE",
    title: "Runner Cycle Failure Repeated",
    message: "최근 Runner cycle이 반복적으로 실패했습니다.",
    target_id: null,
    alert_id: null,
    occurred_at: "2026-08-21T10:00:00Z",
    metadata: {},
  },
  {
    finding_id: "f-error",
    severity: "ERROR",
    area: "crawler",
    code: "CRAWLER_READ_ERROR",
    title: "Crawler Read Error",
    message: "Crawler read failed",
    target_id: "ssg_123",
    alert_id: null,
    occurred_at: "2026-08-21T09:00:00Z",
    metadata: {},
  },
  {
    finding_id: "f-warning",
    severity: "WARNING",
    area: "crawler",
    code: "CRAWLER_ACCESS_DENIED",
    title: "Crawler Access Denied",
    message: "SSG 접근이 거부되었습니다.",
    target_id: "ssg_456",
    alert_id: null,
    occurred_at: "2026-08-21T08:00:00Z",
    metadata: {},
  },
  {
    finding_id: "f-info",
    severity: "INFO",
    area: "runner",
    code: "RUNNER_OK",
    title: "Runner Healthy",
    message: "Runner cycle succeeded",
    target_id: null,
    alert_id: "alert-1",
    occurred_at: "2026-08-21T07:00:00Z",
    metadata: {},
  },
];

describe("filterInvestigationFindings", () => {
  it("filters by severity", () => {
    const result = filterInvestigationFindings(findings, {
      ...DEFAULT_INVESTIGATION_FILTERS,
      severity: "CRITICAL",
    });
    expect(result).toHaveLength(1);
    expect(result[0]?.finding_id).toBe("f-critical");
  });

  it("filters by area", () => {
    const result = filterInvestigationFindings(findings, {
      ...DEFAULT_INVESTIGATION_FILTERS,
      area: "crawler",
    });
    expect(result).toHaveLength(2);
  });

  it("filters failures only by excluding INFO", () => {
    const result = filterInvestigationFindings(findings, {
      ...DEFAULT_INVESTIGATION_FILTERS,
      failuresOnly: true,
    });
    expect(result.every((item) => item.severity !== "INFO")).toBe(true);
  });

  it("filters by target id", () => {
    const result = filterInvestigationFindings(findings, {
      ...DEFAULT_INVESTIGATION_FILTERS,
      targetId: "ssg_123",
    });
    expect(result).toHaveLength(1);
  });

  it("filters by alert id", () => {
    const result = filterInvestigationFindings(findings, {
      ...DEFAULT_INVESTIGATION_FILTERS,
      alertId: "alert-1",
    });
    expect(result).toHaveLength(1);
  });

  it("filters by search text", () => {
    const result = filterInvestigationFindings(findings, {
      ...DEFAULT_INVESTIGATION_FILTERS,
      search: "access denied",
    });
    expect(result).toHaveLength(1);
    expect(result[0]?.code).toBe("CRAWLER_ACCESS_DENIED");
  });
});
