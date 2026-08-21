"""Pydantic response schemas for read-only operations API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class OperationsErrorResponse(BaseModel):
    detail: str


class DashboardSummarySchema(BaseModel):
    health: str
    reasons: list[str] = Field(default_factory=list)


class CrawlerDashboardSchema(BaseModel):
    total_targets: int = 0
    enabled_targets: int = 0
    disabled_targets: int = 0
    failed_targets: int = 0
    ssg_access_denied: int = 0
    high_priority_failed: int = 0
    recent_successes: int = 0
    recent_failures: int = 0
    by_mall: dict[str, int] = Field(default_factory=dict)
    recent_failure_targets: list[dict[str, Any]] = Field(default_factory=list)
    read_error: str | None = None


class PriceDashboardSchema(BaseModel):
    targets: int = 0
    with_price: int = 0
    without_price: int = 0
    price_down: int = 0
    price_up: int = 0
    unchanged: int = 0
    no_history: int = 0
    invalid_price: int = 0
    read_error: str | None = None


class AlertDashboardSchema(BaseModel):
    total: int = 0
    enabled: int = 0
    disabled: int = 0
    triggered_recently: int = 0
    never_triggered: int = 0
    invalid: int = 0
    by_type: dict[str, int] = Field(default_factory=dict)
    recent_invalid: int = 0
    read_error: str | None = None


class NotificationDashboardSchema(BaseModel):
    sent: int = 0
    failed: int = 0
    skipped: int = 0
    by_channel: dict[str, int] = Field(default_factory=dict)
    recent_failures: list[dict[str, Any]] = Field(default_factory=list)
    read_error: str | None = None


class RunnerDashboardSchema(BaseModel):
    last_cycle_status: str = "UNKNOWN"
    last_run_at: str | None = None
    duration_seconds: float | None = None
    total_alerts: int = 0
    evaluated: int = 0
    triggered: int = 0
    notification_sent: int = 0
    notification_failed: int = 0
    last_successful_cycle_at: str | None = None
    last_failed_cycle_at: str | None = None
    recent_cycles: int = 0
    recent_failed_cycles: int = 0
    read_error: str | None = None


class AuditDashboardSchema(BaseModel):
    recent_events: int = 0
    recent_failures: int = 0
    recent_alert_triggered: int = 0
    recent_notification_failed: int = 0
    recent_runner_failed: int = 0
    event_snapshots: list[dict[str, Any]] = Field(default_factory=list)
    read_error: str | None = None


class DashboardResponse(BaseModel):
    generated_at: str
    summary: DashboardSummarySchema
    crawler: CrawlerDashboardSchema
    price: PriceDashboardSchema
    alerts: AlertDashboardSchema
    notifications: NotificationDashboardSchema
    runner: RunnerDashboardSchema
    audit: AuditDashboardSchema


class InvestigationFindingSchema(BaseModel):
    finding_id: str
    severity: str
    area: str
    code: str
    title: str
    message: str
    target_id: str | None = None
    alert_id: str | None = None
    event_id: str | None = None
    occurred_at: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class InvestigationSummarySchema(BaseModel):
    total_findings: int = 0
    info_count: int = 0
    warning_count: int = 0
    error_count: int = 0
    critical_count: int = 0
    areas: dict[str, int] = Field(default_factory=dict)
    read_errors: int = 0


class InvestigationResponse(BaseModel):
    generated_at: str
    health: str
    summary: InvestigationSummarySchema
    findings: list[InvestigationFindingSchema] = Field(default_factory=list)
    dashboard_summary: DashboardSummarySchema
    crawler: CrawlerDashboardSchema
    price: PriceDashboardSchema
    alerts: AlertDashboardSchema
    notifications: NotificationDashboardSchema
    runner: RunnerDashboardSchema
    audit: AuditDashboardSchema


class RemediationActionSchema(BaseModel):
    action_id: str
    action_type: str
    priority: str
    risk: str
    finding_id: str
    area: str
    target_id: str | None = None
    alert_id: str | None = None
    title: str
    reason: str
    recommended_steps: list[str] = Field(default_factory=list)
    preconditions: list[str] = Field(default_factory=list)
    human_approval_required: bool = True
    auto_executable: bool = False
    read_error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RemediationPlanSummarySchema(BaseModel):
    total_actions: int = 0
    actionable_actions: int = 0
    no_action_count: int = 0
    by_priority: dict[str, int] = Field(default_factory=dict)
    by_area: dict[str, int] = Field(default_factory=dict)
    read_errors: int = 0


class RemediationPlanResponse(BaseModel):
    generated_at: str
    health: str
    total_findings: int = 0
    actionable_findings: int = 0
    actions: list[RemediationActionSchema] = Field(default_factory=list)
    read_errors: int = 0
    summary: RemediationPlanSummarySchema


class ExecutionHistoryEntrySchema(BaseModel):
    execution_id: str
    action_id: str
    action_type: str
    mode: str
    status: str
    priority: str = "MEDIUM"
    risk: str = "MEDIUM"
    area: str = "unknown"
    target_id: str | None = None
    alert_id: str | None = None
    title: str = ""
    started_at: str | None = None
    completed_at: str | None = None
    duration_ms: int | None = None
    mutation_performed: bool = False
    approval_verified: bool = False
    error_code: str | None = None
    message: str = ""
    occurred_at: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExecutionHistorySnapshotSchema(BaseModel):
    entry: ExecutionHistoryEntrySchema | None = None
    read_error: str | None = None


class ExecutionSummarySchema(BaseModel):
    total: int = 0
    planned: int = 0
    dry_run: int = 0
    approved: int = 0
    executed: int = 0
    blocked: int = 0
    failed: int = 0
    skipped: int = 0
    mutation_count: int = 0
    approval_failures: int = 0
    recent_failures: int = 0
    by_action_type: dict[str, int] = Field(default_factory=dict)
    by_area: dict[str, int] = Field(default_factory=dict)
    read_errors: int = 0


class ExecutionResponse(BaseModel):
    generated_at: str
    summary: ExecutionSummarySchema
    health: str
    health_reasons: list[str] = Field(default_factory=list)
    entries: list[ExecutionHistorySnapshotSchema] = Field(default_factory=list)


class AuditEventSchema(BaseModel):
    event_id: str
    event_type: str
    occurred_at: str
    alert_id: str | None = None
    target_id: str | None = None
    mall_id: str | None = None
    channel: str | None = None
    status: str | None = None
    price: int | None = None
    previous_price: int | None = None
    classification: str | None = None
    runner_cycle_id: str | None = None
    message: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AuditEventSnapshotSchema(BaseModel):
    event: AuditEventSchema | None = None
    summary: str = ""
    read_error: str | None = None


class AuditSummarySchema(BaseModel):
    total: int = 0
    recent: int = 0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    by_channel: dict[str, int] = Field(default_factory=dict)
    alert_events: int = 0
    notification_events: int = 0
    runner_events: int = 0
    failure_events: int = 0
    read_errors: int = 0


class AuditResponse(BaseModel):
    generated_at: str
    summary: AuditSummarySchema
    health: str
    health_reasons: list[str] = Field(default_factory=list)
    events: list[AuditEventSnapshotSchema] = Field(default_factory=list)


class CommandCenterHealthSchema(BaseModel):
    dashboard: str
    dashboard_reasons: list[str] = Field(default_factory=list)
    execution: str
    execution_reasons: list[str] = Field(default_factory=list)


class CommandCenterResponse(BaseModel):
    generated_at: str
    dashboard: DashboardResponse
    investigation: InvestigationResponse
    remediation: RemediationPlanResponse
    execution: ExecutionResponse
    health: CommandCenterHealthSchema
