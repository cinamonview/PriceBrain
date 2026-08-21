import { parseExecutionResponse } from "./executionValidation";
import { parseInvestigationResponse } from "./investigationValidation";
import { parseRemediationPlanResponse } from "./remediationValidation";
import type {
  AuditDashboard,
  CommandCenterHealth,
  CommandCenterResponse,
  DashboardResponse,
  DashboardSummary,
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

function parseStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter(isString);
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

function parseSummary(value: unknown): DashboardSummary | null {
  if (!isRecord(value) || !isString(value.health)) {
    return null;
  }
  return {
    health: value.health,
    reasons: parseStringArray(value.reasons),
  };
}

function parseAuditDashboard(value: unknown): AuditDashboard {
  if (!isRecord(value)) {
    return {
      recent_events: 0,
      recent_failures: 0,
      recent_alert_triggered: 0,
      recent_notification_failed: 0,
      recent_runner_failed: 0,
      event_snapshots: [],
    };
  }
  return {
    recent_events: isNumber(value.recent_events) ? value.recent_events : 0,
    recent_failures: isNumber(value.recent_failures) ? value.recent_failures : 0,
    recent_alert_triggered: isNumber(value.recent_alert_triggered) ? value.recent_alert_triggered : 0,
    recent_notification_failed: isNumber(value.recent_notification_failed)
      ? value.recent_notification_failed
      : 0,
    recent_runner_failed: isNumber(value.recent_runner_failed) ? value.recent_runner_failed : 0,
    event_snapshots: Array.isArray(value.event_snapshots)
      ? value.event_snapshots.filter(isRecord)
      : [],
    read_error: optionalString(value.read_error),
  };
}

function parseDashboardResponse(value: unknown): DashboardResponse | null {
  if (!isRecord(value) || !isString(value.generated_at)) {
    return null;
  }
  const summary = parseSummary(value.summary);
  if (!summary) {
    return null;
  }
  const crawler = isRecord(value.crawler) ? value.crawler : {};
  const price = isRecord(value.price) ? value.price : {};
  const alerts = isRecord(value.alerts) ? value.alerts : {};
  const notifications = isRecord(value.notifications) ? value.notifications : {};
  const runner = isRecord(value.runner) ? value.runner : {};
  return {
    generated_at: value.generated_at,
    summary,
    crawler: {
      total_targets: isNumber(crawler.total_targets) ? crawler.total_targets : 0,
      enabled_targets: isNumber(crawler.enabled_targets) ? crawler.enabled_targets : 0,
      disabled_targets: isNumber(crawler.disabled_targets) ? crawler.disabled_targets : 0,
      failed_targets: isNumber(crawler.failed_targets) ? crawler.failed_targets : 0,
      ssg_access_denied: isNumber(crawler.ssg_access_denied) ? crawler.ssg_access_denied : 0,
      high_priority_failed: isNumber(crawler.high_priority_failed) ? crawler.high_priority_failed : 0,
      recent_successes: isNumber(crawler.recent_successes) ? crawler.recent_successes : 0,
      recent_failures: isNumber(crawler.recent_failures) ? crawler.recent_failures : 0,
      by_mall: parseStringRecord(crawler.by_mall),
      recent_failure_targets: Array.isArray(crawler.recent_failure_targets)
        ? crawler.recent_failure_targets.filter(isRecord)
        : [],
      read_error: optionalString(crawler.read_error),
    },
    price: {
      targets: isNumber(price.targets) ? price.targets : 0,
      with_price: isNumber(price.with_price) ? price.with_price : 0,
      without_price: isNumber(price.without_price) ? price.without_price : 0,
      price_down: isNumber(price.price_down) ? price.price_down : 0,
      price_up: isNumber(price.price_up) ? price.price_up : 0,
      unchanged: isNumber(price.unchanged) ? price.unchanged : 0,
      no_history: isNumber(price.no_history) ? price.no_history : 0,
      invalid_price: isNumber(price.invalid_price) ? price.invalid_price : 0,
      read_error: optionalString(price.read_error),
    },
    alerts: {
      total: isNumber(alerts.total) ? alerts.total : 0,
      enabled: isNumber(alerts.enabled) ? alerts.enabled : 0,
      disabled: isNumber(alerts.disabled) ? alerts.disabled : 0,
      triggered_recently: isNumber(alerts.triggered_recently) ? alerts.triggered_recently : 0,
      never_triggered: isNumber(alerts.never_triggered) ? alerts.never_triggered : 0,
      invalid: isNumber(alerts.invalid) ? alerts.invalid : 0,
      by_type: parseStringRecord(alerts.by_type),
      recent_invalid: isNumber(alerts.recent_invalid) ? alerts.recent_invalid : 0,
      read_error: optionalString(alerts.read_error),
    },
    notifications: {
      sent: isNumber(notifications.sent) ? notifications.sent : 0,
      failed: isNumber(notifications.failed) ? notifications.failed : 0,
      skipped: isNumber(notifications.skipped) ? notifications.skipped : 0,
      by_channel: parseStringRecord(notifications.by_channel),
      recent_failures: Array.isArray(notifications.recent_failures)
        ? notifications.recent_failures.filter(isRecord)
        : [],
      read_error: optionalString(notifications.read_error),
    },
    runner: {
      last_cycle_status: isString(runner.last_cycle_status) ? runner.last_cycle_status : "UNKNOWN",
      last_run_at: optionalString(runner.last_run_at),
      duration_seconds: isNumber(runner.duration_seconds) ? runner.duration_seconds : null,
      total_alerts: isNumber(runner.total_alerts) ? runner.total_alerts : 0,
      evaluated: isNumber(runner.evaluated) ? runner.evaluated : 0,
      triggered: isNumber(runner.triggered) ? runner.triggered : 0,
      notification_sent: isNumber(runner.notification_sent) ? runner.notification_sent : 0,
      notification_failed: isNumber(runner.notification_failed) ? runner.notification_failed : 0,
      last_successful_cycle_at: optionalString(runner.last_successful_cycle_at),
      last_failed_cycle_at: optionalString(runner.last_failed_cycle_at),
      recent_cycles: isNumber(runner.recent_cycles) ? runner.recent_cycles : 0,
      recent_failed_cycles: isNumber(runner.recent_failed_cycles) ? runner.recent_failed_cycles : 0,
      read_error: optionalString(runner.read_error),
    },
    audit: parseAuditDashboard(value.audit),
  };
}

function parseHealth(value: unknown): CommandCenterHealth | null {
  if (!isRecord(value) || !isString(value.dashboard) || !isString(value.execution)) {
    return null;
  }
  return {
    dashboard: value.dashboard,
    dashboard_reasons: parseStringArray(value.dashboard_reasons),
    execution: value.execution,
    execution_reasons: parseStringArray(value.execution_reasons),
  };
}

export function parseCommandCenterResponse(value: unknown): CommandCenterResponse | null {
  if (!isRecord(value) || !isString(value.generated_at)) {
    return null;
  }
  const health = parseHealth(value.health);
  const dashboard = parseDashboardResponse(value.dashboard);
  const investigation = parseInvestigationResponse(value.investigation);
  const remediation = parseRemediationPlanResponse(value.remediation);
  const execution = parseExecutionResponse(value.execution);
  if (!health || !dashboard || !investigation || !remediation || !execution) {
    return null;
  }
  return {
    generated_at: value.generated_at,
    health,
    dashboard,
    investigation,
    remediation,
    execution,
  };
}
