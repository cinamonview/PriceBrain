import { describe, expect, it } from "vitest";
import type { ExecutionHistoryEntry } from "../api/types";
import {
  DEFAULT_EXECUTION_FILTERS,
  applyExecutionFilters,
  filterExecutionEntries,
  sortExecutionEntries,
} from "../utils/executionFilters";

const entries: ExecutionHistoryEntry[] = [
  {
    execution_id: "exec-failed",
    action_id: "a-1",
    action_type: "REVIEW_RUNNER",
    mode: "EXECUTE",
    status: "FAILED",
    priority: "HIGH",
    risk: "HIGH",
    area: "runner",
    target_id: "target-1",
    alert_id: null,
    title: "Failed execution",
    message: "Execution failed",
    mutation_performed: false,
    approval_verified: false,
    occurred_at: "2026-08-21T12:00:00Z",
    metadata: {},
  },
  {
    execution_id: "exec-blocked",
    action_id: "a-2",
    action_type: "REVIEW_CRAWLER_TARGET",
    mode: "EXECUTE",
    status: "BLOCKED",
    priority: "MEDIUM",
    risk: "MEDIUM",
    area: "crawler",
    target_id: "ssg_123",
    alert_id: "alert-1",
    title: "Blocked execution",
    message: "Approval boundary blocked execution",
    mutation_performed: false,
    approval_verified: false,
    occurred_at: "2026-08-21T11:00:00Z",
    duration_ms: 120,
    metadata: {},
  },
  {
    execution_id: "exec-planned",
    action_id: "a-3",
    action_type: "REVIEW_ALERT",
    mode: "PLAN",
    status: "PLANNED",
    priority: "LOW",
    risk: "LOW",
    area: "alert",
    title: "Planned execution",
    message: "Plan created",
    mutation_performed: false,
    approval_verified: false,
    occurred_at: "2026-08-21T10:00:00Z",
    metadata: {},
  },
];

describe("executionFilters", () => {
  it("filters by status and failures only", () => {
    const failedOnly = filterExecutionEntries(entries, {
      ...DEFAULT_EXECUTION_FILTERS,
      status: "FAILED",
    });
    expect(failedOnly).toHaveLength(1);
    expect(failedOnly[0]?.execution_id).toBe("exec-failed");

    const failuresOnly = filterExecutionEntries(entries, {
      ...DEFAULT_EXECUTION_FILTERS,
      failuresOnly: true,
    });
    expect(failuresOnly.every((item) => item.status === "FAILED")).toBe(true);
  });

  it("sorts newest first by default", () => {
    const sorted = sortExecutionEntries(entries, "NEWEST");
    expect(sorted[0]?.execution_id).toBe("exec-failed");
    expect(sorted.at(-1)?.execution_id).toBe("exec-planned");
  });

  it("limits recent entries when recentOnly is enabled", () => {
    const many = Array.from({ length: 12 }, (_, index) => ({
      ...entries[0],
      execution_id: `exec-${index}`,
      occurred_at: `2026-08-21T${String(index).padStart(2, "0")}:00:00Z`,
    }));
    const result = applyExecutionFilters(
      many.map((entry) => ({ entry })),
      { ...DEFAULT_EXECUTION_FILTERS, recentOnly: true },
    );
    expect(result).toHaveLength(10);
  });
});
