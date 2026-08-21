import { describe, expect, it } from "vitest";
import { parseAuditResponse } from "../api/auditValidation";
import { parseCommandCenterResponse } from "../api/commandCenterValidation";
import { parseExecutionResponse } from "../api/executionValidation";
import { parseInvestigationResponse } from "../api/investigationValidation";
import { parseRemediationPlanResponse } from "../api/remediationValidation";

describe("live integration validation pipeline", () => {
  it("parses representative operations API payloads end-to-end", () => {
    const investigation = parseInvestigationResponse({
      generated_at: "2026-08-21T12:00:00Z",
      health: "DEGRADED",
      summary: {
        total_findings: 1,
        info_count: 0,
        warning_count: 1,
        error_count: 0,
        critical_count: 0,
        areas: { crawler: 1 },
        read_errors: 0,
      },
      findings: [
        {
          finding_id: "f-1",
          severity: "WARNING",
          area: "crawler",
          code: "SSG_ACCESS_DENIED",
          title: "Access denied",
          message: "SSG access denied",
          metadata: { approval_token: "secret" },
        },
      ],
      dashboard_summary: { health: "DEGRADED", reasons: [] },
      crawler: {},
      price: {},
      alerts: {},
      notifications: {},
      runner: {},
      audit: {},
    });
    expect(investigation?.findings[0]?.code).toBe("SSG_ACCESS_DENIED");

    const remediation = parseRemediationPlanResponse({
      generated_at: "2026-08-21T12:00:00Z",
      health: "DEGRADED",
      summary: {
        total_actions: 1,
        actionable_actions: 1,
        no_action_count: 0,
        by_priority: { HIGH: 1 },
        by_area: { runner: 1 },
        read_errors: 0,
      },
      actions: [
        {
          action_id: "a-1",
          action_type: "REVIEW_RUNNER",
          priority: "HIGH",
          risk: "HIGH",
          finding_id: "f-1",
          area: "runner",
          title: "Review runner",
          reason: "Failure",
          recommended_steps: [],
          preconditions: [],
          human_approval_required: true,
          auto_executable: false,
          metadata: {},
        },
      ],
      total_findings: 1,
      actionable_findings: 1,
      read_errors: 0,
    });
    expect(remediation?.actions[0]?.human_approval_required).toBe(true);

    const execution = parseExecutionResponse({
      generated_at: "2026-08-21T12:00:00Z",
      health: "HEALTHY",
      health_reasons: [],
      summary: {
        total: 0,
        planned: 0,
        dry_run: 0,
        approved: 0,
        executed: 0,
        blocked: 0,
        failed: 0,
        skipped: 0,
        mutation_count: 0,
        approval_failures: 0,
        recent_failures: 0,
        by_action_type: {},
        by_area: {},
        read_errors: 0,
      },
      entries: [],
    });
    expect(execution?.health).toBe("HEALTHY");

    const audit = parseAuditResponse({
      generated_at: "2026-08-21T12:00:00Z",
      health: "DEGRADED",
      health_reasons: ["recent audit failures"],
      summary: {
        total: 1,
        recent: 1,
        by_type: { NOTIFICATION_FAILED: 1 },
        by_status: { FAILED: 1 },
        by_channel: { email: 1 },
        alert_events: 0,
        notification_events: 1,
        runner_events: 0,
        failure_events: 1,
        read_errors: 0,
      },
      events: [
        {
          summary: "notification failed",
          event: {
            event_id: "evt-1",
            event_type: "NOTIFICATION_FAILED",
            occurred_at: "2026-08-21T11:00:00Z",
            metadata: { api_key: "secret-key" },
          },
        },
      ],
    });
    expect(audit?.events[0]?.event?.event_id).toBe("evt-1");

    const commandCenter = parseCommandCenterResponse({
      generated_at: "2026-08-21T12:00:00Z",
      health: {
        dashboard: "DEGRADED",
        dashboard_reasons: [],
        execution: "HEALTHY",
        execution_reasons: [],
      },
      dashboard: {
        generated_at: "2026-08-21T12:00:00Z",
        summary: { health: "DEGRADED", reasons: [] },
        crawler: { total_targets: 1 },
        price: { targets: 1 },
        alerts: { total: 0 },
        notifications: { sent: 0, failed: 0, skipped: 0, recent_failures: [] },
        runner: { last_cycle_status: "SUCCESS" },
        audit: { recent_events: 0, event_snapshots: [] },
      },
      investigation: {
        generated_at: "2026-08-21T12:00:00Z",
        health: "DEGRADED",
        summary: {
          total_findings: 1,
          info_count: 0,
          warning_count: 1,
          error_count: 0,
          critical_count: 0,
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
        summary: {
          total_actions: 0,
          actionable_actions: 0,
          no_action_count: 0,
          by_priority: {},
          by_area: {},
          read_errors: 0,
        },
        actions: [],
        total_findings: 0,
        actionable_findings: 0,
        read_errors: 0,
      },
      execution: {
        generated_at: "2026-08-21T12:00:00Z",
        health: "HEALTHY",
        health_reasons: [],
        summary: {
          total: 0,
          planned: 0,
          dry_run: 0,
          approved: 0,
          executed: 0,
          blocked: 0,
          failed: 0,
          skipped: 0,
          mutation_count: 0,
          approval_failures: 0,
          recent_failures: 0,
          by_action_type: {},
          by_area: {},
          read_errors: 0,
        },
        entries: [],
      },
    });
    expect(commandCenter?.health.dashboard).toBe("DEGRADED");
  });
});
