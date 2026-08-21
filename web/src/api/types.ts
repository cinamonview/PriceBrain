export type HealthStatus = "HEALTHY" | "DEGRADED" | "CRITICAL" | "UNKNOWN";

export type OpsRole = "OPS_VIEWER" | "OPS_OPERATOR" | "OPS_ADMIN";

export interface DashboardSummary {
  health: string;
  reasons: string[];
}

export interface CrawlerDashboard {
  total_targets: number;
  enabled_targets: number;
  disabled_targets: number;
  failed_targets: number;
  ssg_access_denied: number;
  high_priority_failed: number;
  recent_successes: number;
  recent_failures: number;
  by_mall: Record<string, number>;
  recent_failure_targets: Record<string, unknown>[];
  read_error?: string | null;
}

export interface PriceDashboard {
  targets: number;
  with_price: number;
  without_price: number;
  price_down: number;
  price_up: number;
  unchanged: number;
  no_history: number;
  invalid_price: number;
  read_error?: string | null;
}

export interface AlertDashboard {
  total: number;
  enabled: number;
  disabled: number;
  triggered_recently: number;
  never_triggered: number;
  invalid: number;
  by_type: Record<string, number>;
  recent_invalid: number;
  read_error?: string | null;
}

export interface NotificationDashboard {
  sent: number;
  failed: number;
  skipped: number;
  by_channel: Record<string, number>;
  recent_failures: Record<string, unknown>[];
  read_error?: string | null;
}

export interface RunnerDashboard {
  last_cycle_status: string;
  last_run_at?: string | null;
  duration_seconds?: number | null;
  total_alerts: number;
  evaluated: number;
  triggered: number;
  notification_sent: number;
  notification_failed: number;
  last_successful_cycle_at?: string | null;
  last_failed_cycle_at?: string | null;
  recent_cycles: number;
  recent_failed_cycles: number;
  read_error?: string | null;
}

export interface AuditDashboard {
  recent_events: number;
  recent_failures: number;
  recent_alert_triggered: number;
  recent_notification_failed: number;
  recent_runner_failed: number;
  event_snapshots: Record<string, unknown>[];
  read_error?: string | null;
}

export interface DashboardResponse {
  generated_at: string;
  summary: DashboardSummary;
  crawler: CrawlerDashboard;
  price: PriceDashboard;
  alerts: AlertDashboard;
  notifications: NotificationDashboard;
  runner: RunnerDashboard;
  audit: AuditDashboard;
}

export interface InvestigationSummary {
  total_findings: number;
  info_count: number;
  warning_count: number;
  error_count: number;
  critical_count: number;
  areas: Record<string, number>;
  read_errors: number;
}

export interface InvestigationFinding {
  finding_id: string;
  severity: string;
  area: string;
  code: string;
  title: string;
  message: string;
  target_id?: string | null;
  alert_id?: string | null;
  event_id?: string | null;
  occurred_at?: string | null;
  metadata: Record<string, unknown>;
}

export interface InvestigationResponse {
  generated_at: string;
  health: string;
  summary: InvestigationSummary;
  findings: InvestigationFinding[];
  dashboard_summary: DashboardSummary;
  crawler: CrawlerDashboard;
  price: PriceDashboard;
  alerts: AlertDashboard;
  notifications: NotificationDashboard;
  runner: RunnerDashboard;
  audit: AuditDashboard;
}

export interface RemediationAction {
  action_id: string;
  action_type: string;
  priority: string;
  risk: string;
  finding_id: string;
  area: string;
  target_id?: string | null;
  alert_id?: string | null;
  title: string;
  reason: string;
  recommended_steps: string[];
  preconditions: string[];
  human_approval_required: boolean;
  auto_executable: boolean;
  read_error?: string | null;
  metadata: Record<string, unknown>;
}

export interface RemediationPlanSummary {
  total_actions: number;
  actionable_actions: number;
  no_action_count: number;
  by_priority: Record<string, number>;
  by_area: Record<string, number>;
  read_errors: number;
}

export interface RemediationPlanResponse {
  generated_at: string;
  health: string;
  total_findings: number;
  actionable_findings: number;
  actions: RemediationAction[];
  read_errors: number;
  summary: RemediationPlanSummary;
}

export interface ExecutionSummary {
  total: number;
  planned: number;
  dry_run: number;
  approved: number;
  executed: number;
  blocked: number;
  failed: number;
  skipped: number;
  mutation_count: number;
  approval_failures: number;
  recent_failures: number;
  by_action_type: Record<string, number>;
  by_area: Record<string, number>;
  read_errors: number;
}

export interface ExecutionHistoryEntry {
  execution_id: string;
  action_id: string;
  action_type: string;
  mode: string;
  status: string;
  priority: string;
  risk: string;
  area: string;
  target_id?: string | null;
  alert_id?: string | null;
  title: string;
  started_at?: string | null;
  completed_at?: string | null;
  duration_ms?: number | null;
  mutation_performed: boolean;
  approval_verified: boolean;
  error_code?: string | null;
  message: string;
  occurred_at?: string | null;
  metadata: Record<string, unknown>;
}

export interface ExecutionHistorySnapshot {
  entry?: ExecutionHistoryEntry | null;
  read_error?: string | null;
}

export interface ExecutionResponse {
  generated_at: string;
  summary: ExecutionSummary;
  health: string;
  health_reasons: string[];
  entries: ExecutionHistorySnapshot[];
}

export interface CommandCenterHealth {
  dashboard: string;
  dashboard_reasons: string[];
  execution: string;
  execution_reasons: string[];
}

export interface CommandCenterResponse {
  generated_at: string;
  dashboard: DashboardResponse;
  investigation: InvestigationResponse;
  remediation: RemediationPlanResponse;
  execution: ExecutionResponse;
  health: CommandCenterHealth;
}

export type QueryStatus = "idle" | "loading" | "success" | "error" | "unauthorized" | "forbidden";
