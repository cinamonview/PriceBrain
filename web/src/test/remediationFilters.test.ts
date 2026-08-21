import { describe, expect, it } from "vitest";
import type { RemediationAction } from "../api/types";
import {
  DEFAULT_REMEDIATION_FILTERS,
  filterRemediationActions,
  priorityCount,
} from "../utils/remediationFilters";

const actions: RemediationAction[] = [
  {
    action_id: "a-high",
    action_type: "REVIEW_RUNNER",
    priority: "HIGH",
    risk: "HIGH",
    finding_id: "f-1",
    area: "runner",
    title: "Review runner cycle",
    reason: "Runner failures detected",
    recommended_steps: ["Inspect runner logs"],
    preconditions: [],
    human_approval_required: true,
    auto_executable: false,
    metadata: {},
  },
  {
    action_id: "a-medium",
    action_type: "REVIEW_CRAWLER_TARGET",
    priority: "MEDIUM",
    risk: "MEDIUM",
    finding_id: "f-2",
    area: "crawler",
    target_id: "ssg_123",
    alert_id: null,
    title: "Review crawler target",
    reason: "Target access denied",
    recommended_steps: [],
    preconditions: [],
    human_approval_required: true,
    auto_executable: false,
    metadata: {},
  },
  {
    action_id: "a-low",
    action_type: "NO_ACTION",
    priority: "LOW",
    risk: "LOW",
    finding_id: "f-3",
    area: "runner",
    title: "No action",
    reason: "Informational only",
    recommended_steps: [],
    preconditions: [],
    human_approval_required: true,
    auto_executable: false,
    metadata: {},
  },
];

describe("filterRemediationActions", () => {
  it("filters by priority", () => {
    const result = filterRemediationActions(actions, {
      ...DEFAULT_REMEDIATION_FILTERS,
      priority: "HIGH",
    });
    expect(result).toHaveLength(1);
    expect(result[0]?.action_id).toBe("a-high");
  });

  it("filters failures only by excluding NO_ACTION", () => {
    const result = filterRemediationActions(actions, {
      ...DEFAULT_REMEDIATION_FILTERS,
      failuresOnly: true,
    });
    expect(result.every((item) => item.action_type !== "NO_ACTION")).toBe(true);
  });
});

describe("priorityCount", () => {
  it("reads priority counts from summary map", () => {
    expect(priorityCount({ HIGH: 2, MEDIUM: 1 }, "HIGH")).toBe(2);
    expect(priorityCount({}, "LOW")).toBe(0);
  });
});
