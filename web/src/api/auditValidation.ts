import type {
  AuditEvent,
  AuditEventSnapshot,
  AuditResponse,
  AuditSummary,
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

function optionalString(value: unknown): string | null {
  if (value === null || value === undefined) {
    return null;
  }
  return isString(value) ? value : null;
}

function optionalNumber(value: unknown): number | null {
  if (value === null || value === undefined) {
    return null;
  }
  return isNumber(value) ? value : null;
}

function parseStringRecord(value: unknown): Record<string, number> {
  const record: Record<string, number> = {};
  if (!isRecord(value)) {
    return record;
  }
  for (const [key, count] of Object.entries(value)) {
    if (isNumber(count)) {
      record[key] = count;
    }
  }
  return record;
}

function parseEvent(value: unknown): AuditEvent | null {
  if (!isRecord(value)) {
    return null;
  }
  if (!isString(value.event_id) || !isString(value.event_type) || !isString(value.occurred_at)) {
    return null;
  }
  return {
    event_id: value.event_id,
    event_type: value.event_type,
    occurred_at: value.occurred_at,
    alert_id: optionalString(value.alert_id),
    target_id: optionalString(value.target_id),
    mall_id: optionalString(value.mall_id),
    channel: optionalString(value.channel),
    status: optionalString(value.status),
    price: optionalNumber(value.price),
    previous_price: optionalNumber(value.previous_price),
    classification: optionalString(value.classification),
    runner_cycle_id: optionalString(value.runner_cycle_id),
    message: optionalString(value.message),
    metadata: isRecord(value.metadata) ? value.metadata : {},
  };
}

function parseSnapshot(value: unknown): AuditEventSnapshot | null {
  if (!isRecord(value)) {
    return null;
  }
  const summary = isString(value.summary) ? value.summary : "";
  if (value.event === null || value.event === undefined) {
    return {
      event: null,
      summary,
      read_error: optionalString(value.read_error) ?? "invalid event",
    };
  }
  const event = parseEvent(value.event);
  if (!event) {
    return {
      event: null,
      summary,
      read_error: optionalString(value.read_error) ?? "invalid event payload",
    };
  }
  return {
    event,
    summary,
    read_error: optionalString(value.read_error),
  };
}

function parseSummary(value: unknown): AuditSummary | null {
  if (!isRecord(value)) {
    return null;
  }
  return {
    total: isNumber(value.total) ? value.total : 0,
    recent: isNumber(value.recent) ? value.recent : 0,
    by_type: parseStringRecord(value.by_type),
    by_status: parseStringRecord(value.by_status),
    by_channel: parseStringRecord(value.by_channel),
    by_area: isRecord(value.by_area) ? parseStringRecord(value.by_area) : undefined,
    alert_events: isNumber(value.alert_events) ? value.alert_events : 0,
    notification_events: isNumber(value.notification_events) ? value.notification_events : 0,
    runner_events: isNumber(value.runner_events) ? value.runner_events : 0,
    failure_events: isNumber(value.failure_events) ? value.failure_events : undefined,
    read_errors: isNumber(value.read_errors) ? value.read_errors : 0,
  };
}

export function parseAuditResponse(value: unknown): AuditResponse | null {
  if (!isRecord(value) || !isString(value.generated_at) || !isString(value.health)) {
    return null;
  }
  const summary = parseSummary(value.summary);
  if (!summary || !Array.isArray(value.events)) {
    return null;
  }
  const events = value.events
    .map((item) => parseSnapshot(item))
    .filter((item): item is AuditEventSnapshot => item !== null);
  if (events.length !== value.events.length) {
    return null;
  }
  const healthReasons = Array.isArray(value.health_reasons)
    ? value.health_reasons.filter(isString)
    : [];
  return {
    generated_at: value.generated_at,
    health: value.health,
    health_reasons: healthReasons,
    summary,
    events,
  };
}
