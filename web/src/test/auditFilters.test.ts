import { describe, expect, it } from "vitest";
import type { AuditEventSnapshot } from "../api/types";
import {
  DEFAULT_AUDIT_FILTERS,
  applyAuditFilters,
  deriveAuditSeverity,
  isFailureAuditEvent,
} from "../utils/auditFilters";

const snapshots: AuditEventSnapshot[] = [
  {
    summary: "alert triggered",
    event: {
      event_id: "evt-triggered",
      event_type: "ALERT_TRIGGERED",
      occurred_at: "2026-08-21T12:00:00Z",
      alert_id: "a1",
      target_id: "ssg_1",
      metadata: {},
    },
  },
  {
    summary: "notification failed",
    event: {
      event_id: "evt-failed",
      event_type: "NOTIFICATION_FAILED",
      occurred_at: "2026-08-21T11:00:00Z",
      alert_id: "a2",
      status: "FAILED",
      metadata: {},
    },
  },
];

describe("auditFilters", () => {
  it("derives severity and failure classification", () => {
    expect(deriveAuditSeverity("ALERT_TRIGGERED")).toBe("WARNING");
    expect(deriveAuditSeverity("NOTIFICATION_FAILED", "FAILED")).toBe("ERROR");
    expect(isFailureAuditEvent(snapshots[1]!.event!)).toBe(true);
  });

  it("filters by event type, severity, failures-only, and search", () => {
    const byType = applyAuditFilters(snapshots, {
      ...DEFAULT_AUDIT_FILTERS,
      eventType: "NOTIFICATION_FAILED",
    });
    expect(byType).toHaveLength(1);
    expect(byType[0]?.event?.event_id).toBe("evt-failed");

    const failuresOnly = applyAuditFilters(snapshots, {
      ...DEFAULT_AUDIT_FILTERS,
      failuresOnly: true,
    });
    expect(failuresOnly).toHaveLength(1);

    const search = applyAuditFilters(snapshots, {
      ...DEFAULT_AUDIT_FILTERS,
      search: "triggered",
    });
    expect(search[0]?.event?.event_id).toBe("evt-triggered");
  });
});
