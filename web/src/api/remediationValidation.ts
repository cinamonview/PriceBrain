import type { RemediationAction, RemediationPlanResponse, RemediationPlanSummary } from "./types";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isString(value: unknown): value is string {
  return typeof value === "string";
}

function isNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function isBoolean(value: unknown): value is boolean {
  return typeof value === "boolean";
}

function optionalString(value: unknown): string | null {
  if (value === null || value === undefined) {
    return null;
  }
  return isString(value) ? value : null;
}

function parseStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter(isString);
}

function parseAction(value: unknown): RemediationAction | null {
  if (!isRecord(value)) {
    return null;
  }
  if (
    !isString(value.action_id) ||
    !isString(value.action_type) ||
    !isString(value.priority) ||
    !isString(value.risk) ||
    !isString(value.finding_id) ||
    !isString(value.area) ||
    !isString(value.title) ||
    !isString(value.reason) ||
    !isBoolean(value.human_approval_required) ||
    !isBoolean(value.auto_executable)
  ) {
    return null;
  }
  return {
    action_id: value.action_id,
    action_type: value.action_type,
    priority: value.priority,
    risk: value.risk,
    finding_id: value.finding_id,
    area: value.area,
    target_id: optionalString(value.target_id),
    alert_id: optionalString(value.alert_id),
    title: value.title,
    reason: value.reason,
    recommended_steps: parseStringArray(value.recommended_steps),
    preconditions: parseStringArray(value.preconditions),
    human_approval_required: value.human_approval_required,
    auto_executable: value.auto_executable,
    read_error: optionalString(value.read_error),
    metadata: isRecord(value.metadata) ? value.metadata : {},
  };
}

function parseSummary(value: unknown): RemediationPlanSummary | null {
  if (!isRecord(value)) {
    return null;
  }
  const byPriority: Record<string, number> = {};
  const byArea: Record<string, number> = {};
  if (isRecord(value.by_priority)) {
    for (const [key, count] of Object.entries(value.by_priority)) {
      if (isNumber(count)) {
        byPriority[key] = count;
      }
    }
  }
  if (isRecord(value.by_area)) {
    for (const [key, count] of Object.entries(value.by_area)) {
      if (isNumber(count)) {
        byArea[key] = count;
      }
    }
  }
  return {
    total_actions: isNumber(value.total_actions) ? value.total_actions : 0,
    actionable_actions: isNumber(value.actionable_actions) ? value.actionable_actions : 0,
    no_action_count: isNumber(value.no_action_count) ? value.no_action_count : 0,
    by_priority: byPriority,
    by_area: byArea,
    read_errors: isNumber(value.read_errors) ? value.read_errors : 0,
  };
}

export function parseRemediationPlanResponse(value: unknown): RemediationPlanResponse | null {
  if (!isRecord(value) || !isString(value.generated_at) || !isString(value.health)) {
    return null;
  }
  const summary = parseSummary(value.summary);
  if (!summary || !Array.isArray(value.actions)) {
    return null;
  }
  const actions = value.actions
    .map((item) => parseAction(item))
    .filter((item): item is RemediationAction => item !== null);
  if (actions.length !== value.actions.length) {
    return null;
  }
  return {
    generated_at: value.generated_at,
    health: value.health,
    total_findings: isNumber(value.total_findings) ? value.total_findings : 0,
    actionable_findings: isNumber(value.actionable_findings) ? value.actionable_findings : 0,
    actions,
    read_errors: isNumber(value.read_errors) ? value.read_errors : 0,
    summary,
  };
}
