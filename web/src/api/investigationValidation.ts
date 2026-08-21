import type { InvestigationFinding, InvestigationResponse, InvestigationSummary } from "./types";

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

function parseFinding(value: unknown): InvestigationFinding | null {
  if (!isRecord(value)) {
    return null;
  }
  if (
    !isString(value.finding_id) ||
    !isString(value.severity) ||
    !isString(value.area) ||
    !isString(value.code) ||
    !isString(value.title) ||
    !isString(value.message)
  ) {
    return null;
  }
  return {
    finding_id: value.finding_id,
    severity: value.severity,
    area: value.area,
    code: value.code,
    title: value.title,
    message: value.message,
    target_id: optionalString(value.target_id),
    alert_id: optionalString(value.alert_id),
    event_id: optionalString(value.event_id),
    occurred_at: optionalString(value.occurred_at),
    metadata: isRecord(value.metadata) ? value.metadata : {},
  };
}

function parseSummary(value: unknown): InvestigationSummary | null {
  if (!isRecord(value)) {
    return null;
  }
  const areas: Record<string, number> = {};
  if (isRecord(value.areas)) {
    for (const [key, count] of Object.entries(value.areas)) {
      if (isNumber(count)) {
        areas[key] = count;
      }
    }
  }
  return {
    total_findings: isNumber(value.total_findings) ? value.total_findings : 0,
    info_count: isNumber(value.info_count) ? value.info_count : 0,
    warning_count: isNumber(value.warning_count) ? value.warning_count : 0,
    error_count: isNumber(value.error_count) ? value.error_count : 0,
    critical_count: isNumber(value.critical_count) ? value.critical_count : 0,
    areas,
    read_errors: isNumber(value.read_errors) ? value.read_errors : 0,
  };
}

export function parseInvestigationResponse(value: unknown): InvestigationResponse | null {
  if (!isRecord(value) || !isString(value.generated_at) || !isString(value.health)) {
    return null;
  }
  const summary = parseSummary(value.summary);
  if (!summary || !Array.isArray(value.findings)) {
    return null;
  }
  const findings = value.findings
    .map((item) => parseFinding(item))
    .filter((item): item is InvestigationFinding => item !== null);
  if (findings.length !== value.findings.length) {
    return null;
  }

  const candidate = value as unknown as InvestigationResponse;
  return {
    ...candidate,
    generated_at: value.generated_at,
    health: value.health,
    summary,
    findings,
  };
}
