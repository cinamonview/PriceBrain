import type {
  ExecutionHistoryEntry,
  ExecutionHistorySnapshot,
  ExecutionResponse,
  ExecutionSummary,
} from "./types";

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

function optionalNumber(value: unknown): number | null {
  if (value === null || value === undefined) {
    return null;
  }
  return isNumber(value) ? value : null;
}

function optionalString(value: unknown): string | null {
  if (value === null || value === undefined) {
    return null;
  }
  return isString(value) ? value : null;
}

function parseEntry(value: unknown): ExecutionHistoryEntry | null {
  if (!isRecord(value)) {
    return null;
  }
  if (
    !isString(value.execution_id) ||
    !isString(value.action_id) ||
    !isString(value.action_type) ||
    !isString(value.mode) ||
    !isString(value.status) ||
    !isBoolean(value.mutation_performed) ||
    !isBoolean(value.approval_verified)
  ) {
    return null;
  }
  return {
    execution_id: value.execution_id,
    action_id: value.action_id,
    action_type: value.action_type,
    mode: value.mode,
    status: value.status,
    priority: isString(value.priority) ? value.priority : "MEDIUM",
    risk: isString(value.risk) ? value.risk : "MEDIUM",
    area: isString(value.area) ? value.area : "unknown",
    target_id: optionalString(value.target_id),
    alert_id: optionalString(value.alert_id),
    title: isString(value.title) ? value.title : "",
    started_at: optionalString(value.started_at),
    completed_at: optionalString(value.completed_at),
    duration_ms: optionalNumber(value.duration_ms),
    mutation_performed: value.mutation_performed,
    approval_verified: value.approval_verified,
    error_code: optionalString(value.error_code),
    message: isString(value.message) ? value.message : "",
    occurred_at: optionalString(value.occurred_at),
    metadata: isRecord(value.metadata) ? value.metadata : {},
  };
}

function parseSnapshot(value: unknown): ExecutionHistorySnapshot | null {
  if (!isRecord(value)) {
    return null;
  }
  if (value.entry === null || value.entry === undefined) {
    return { entry: null, read_error: optionalString(value.read_error) };
  }
  const entry = parseEntry(value.entry);
  if (!entry) {
    return null;
  }
  return { entry, read_error: optionalString(value.read_error) };
}

function parseSummary(value: unknown): ExecutionSummary | null {
  if (!isRecord(value)) {
    return null;
  }
  const byActionType: Record<string, number> = {};
  const byArea: Record<string, number> = {};
  if (isRecord(value.by_action_type)) {
    for (const [key, count] of Object.entries(value.by_action_type)) {
      if (isNumber(count)) {
        byActionType[key] = count;
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
    total: isNumber(value.total) ? value.total : 0,
    planned: isNumber(value.planned) ? value.planned : 0,
    dry_run: isNumber(value.dry_run) ? value.dry_run : 0,
    approved: isNumber(value.approved) ? value.approved : 0,
    executed: isNumber(value.executed) ? value.executed : 0,
    blocked: isNumber(value.blocked) ? value.blocked : 0,
    failed: isNumber(value.failed) ? value.failed : 0,
    skipped: isNumber(value.skipped) ? value.skipped : 0,
    mutation_count: isNumber(value.mutation_count) ? value.mutation_count : 0,
    approval_failures: isNumber(value.approval_failures) ? value.approval_failures : 0,
    recent_failures: isNumber(value.recent_failures) ? value.recent_failures : 0,
    by_action_type: byActionType,
    by_area: byArea,
    read_errors: isNumber(value.read_errors) ? value.read_errors : 0,
  };
}

export function parseExecutionResponse(value: unknown): ExecutionResponse | null {
  if (!isRecord(value) || !isString(value.generated_at) || !isString(value.health)) {
    return null;
  }
  const summary = parseSummary(value.summary);
  if (!summary || !Array.isArray(value.entries)) {
    return null;
  }
  const entries = value.entries
    .map((item) => parseSnapshot(item))
    .filter((item): item is ExecutionHistorySnapshot => item !== null);
  if (entries.length !== value.entries.length) {
    return null;
  }
  const healthReasons = Array.isArray(value.health_reasons)
    ? value.health_reasons.filter(isString)
    : [];
  return {
    generated_at: value.generated_at,
    summary,
    health: value.health,
    health_reasons: healthReasons,
    entries,
  };
}
