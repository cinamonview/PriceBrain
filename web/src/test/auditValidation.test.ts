import { describe, expect, it } from "vitest";
import { parseAuditResponse } from "../api/auditValidation";

describe("auditValidation", () => {
  it("parses valid audit response", () => {
    const parsed = parseAuditResponse({
      generated_at: "2026-08-21T12:00:00Z",
      health: "HEALTHY",
      health_reasons: [],
      summary: {
        total: 1,
        recent: 1,
        by_type: { ALERT_TRIGGERED: 1 },
        by_status: { TRIGGERED: 1 },
        by_channel: {},
        alert_events: 1,
        notification_events: 0,
        runner_events: 0,
        read_errors: 0,
      },
      events: [
        {
          summary: "alert=a1 target=ssg_1",
          event: {
            event_id: "evt-1",
            event_type: "ALERT_TRIGGERED",
            occurred_at: "2026-08-21T11:00:00Z",
            alert_id: "a1",
            target_id: "ssg_1",
            metadata: {},
          },
        },
      ],
    });

    expect(parsed?.events).toHaveLength(1);
    expect(parsed?.events[0]?.event?.event_id).toBe("evt-1");
  });

  it("isolates malformed events without rejecting the whole payload", () => {
    const parsed = parseAuditResponse({
      generated_at: "2026-08-21T12:00:00Z",
      health: "DEGRADED",
      health_reasons: ["read errors"],
      summary: {
        total: 1,
        recent: 1,
        by_type: {},
        by_status: {},
        by_channel: {},
        alert_events: 0,
        notification_events: 0,
        runner_events: 0,
        read_errors: 1,
      },
      events: [
        {
          summary: "invalid event",
          event: { broken: true },
          read_error: "missing event_id",
        },
      ],
    });

    expect(parsed?.events[0]?.read_error).toBe("missing event_id");
    expect(parsed?.events[0]?.event).toBeNull();
  });
});
