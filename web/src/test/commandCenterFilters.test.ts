import { describe, expect, it } from "vitest";
import type { CommandCenterResponse } from "../api/types";
import {
  countOperationalFailures,
  countReadErrors,
  filterFindings,
  DEFAULT_COMMAND_CENTER_FILTERS,
} from "../utils/commandCenterFilters";

const mockData = {
  investigation: {
    summary: { read_errors: 1, critical_count: 1, error_count: 1 },
    findings: [
      {
        finding_id: "f1",
        severity: "CRITICAL",
        area: "runner",
        code: "RUNNER_CYCLE_FAILED",
        title: "Runner failed",
        message: "failure",
        metadata: {},
      },
    ],
  },
  remediation: { read_errors: 0 },
  execution: { summary: { read_errors: 0, failed: 1, recent_failures: 1 } },
  dashboard: {
    crawler: { read_error: "crawler read error" },
    price: {},
    alerts: {},
    notifications: { failed: 1 },
    runner: { recent_failures: 1, recent_failed_cycles: 1 },
    audit: { recent_failures: 1 },
  },
} as unknown as CommandCenterResponse;

describe("commandCenterFilters", () => {
  it("counts read errors and operational failures from API fields", () => {
    expect(countReadErrors(mockData)).toBeGreaterThan(0);
    expect(countOperationalFailures(mockData)).toBeGreaterThan(0);
  });

  it("filters findings without reclassifying severity", () => {
    const filtered = filterFindings(mockData.investigation.findings, {
      ...DEFAULT_COMMAND_CENTER_FILTERS,
      failuresOnly: true,
    });
    expect(filtered).toHaveLength(1);
    expect(filtered[0]?.severity).toBe("CRITICAL");
  });
});
