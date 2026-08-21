import { describe, expect, it } from "vitest";
import { parseCommandCenterResponse } from "../api/commandCenterValidation";

describe("commandCenterValidation", () => {
  it("parses command center response", () => {
    const parsed = parseCommandCenterResponse({
      generated_at: "2026-08-21T12:00:00Z",
      health: {
        dashboard: "DEGRADED",
        dashboard_reasons: ["failures"],
        execution: "CRITICAL",
        execution_reasons: ["recent failures"],
      },
      dashboard: {
        generated_at: "2026-08-21T12:00:00Z",
        summary: { health: "DEGRADED", reasons: [] },
        crawler: { total_targets: 2, recent_failures: 1 },
        price: { targets: 2 },
        alerts: { total: 1 },
        notifications: { sent: 1, failed: 1, skipped: 0, recent_failures: [] },
        runner: { last_cycle_status: "FAILED", recent_failed_cycles: 1 },
        audit: { recent_events: 1, event_snapshots: [] },
      },
      investigation: {
        generated_at: "2026-08-21T12:00:00Z",
        health: "DEGRADED",
        summary: {
          total_findings: 1,
          critical_count: 0,
          warning_count: 1,
          error_count: 0,
          info_count: 0,
          areas: {},
          read_errors: 0,
        },
        findings: [],
        dashboard_summary: { health: "DEGRADED", reasons: [] },
        crawler: {},
        price: {},
        alerts: {},
        notifications: {},
        runner: {},
        audit: {},
      },
      remediation: {
        generated_at: "2026-08-21T12:00:00Z",
        health: "DEGRADED",
        summary: { total_actions: 1, actionable_actions: 1, no_action_count: 0, by_priority: {}, by_area: {}, read_errors: 0 },
        actions: [],
        total_findings: 1,
        actionable_findings: 1,
        read_errors: 0,
      },
      execution: {
        generated_at: "2026-08-21T12:00:00Z",
        health: "CRITICAL",
        health_reasons: [],
        summary: { total: 1, failed: 1, blocked: 0, planned: 0, dry_run: 0, executed: 0, approved: 0, skipped: 0, mutation_count: 0, approval_failures: 0, recent_failures: 1, by_action_type: {}, by_area: {}, read_errors: 0 },
        entries: [],
      },
    });

    expect(parsed?.health.execution).toBe("CRITICAL");
    expect(parsed?.dashboard.crawler.total_targets).toBe(2);
  });
});
