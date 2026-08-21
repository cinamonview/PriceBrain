"""Pure remediation rule engine — maps investigation findings to actions."""

from __future__ import annotations

import uuid
from typing import Any

from pricebrain_app.crawler.investigation_operations_models import (
    DashboardInvestigationSnapshot,
    InvestigationFinding,
)
from pricebrain_app.crawler.remediation_operations_models import (
    RemediationAction,
    RemediationActionType,
    RemediationPriority,
    RemediationRisk,
)

FINDING_ACTION_MAP: dict[str, tuple[RemediationActionType, RemediationPriority, RemediationRisk, str, tuple[str, ...]]] = {
    "CRAWLER_ACCESS_DENIED": (
        RemediationActionType.REVIEW_SSG_ACCESS,
        RemediationPriority.HIGH,
        RemediationRisk.HIGH,
        "SSG 접근 거부 상태 확인 필요",
        (
            "Firestore에서 해당 target의 last_error_code를 확인합니다.",
            "SSG 환경 제약(HTTP 403)인지 운영 설정 문제인지 구분합니다.",
            "필요 시 crawl interval 또는 target 우선순위를 검토합니다.",
        ),
    ),
    "CRAWLER_HTTP_ERROR": (
        RemediationActionType.REVIEW_CRAWLER_TARGET,
        RemediationPriority.HIGH,
        RemediationRisk.HIGH,
        "Crawler HTTP 오류 target 검토 필요",
        (
            "실패 target의 last_status / last_error_message를 확인합니다.",
            "일시적 네트워크 오류인지 구조적 오류인지 분류합니다.",
        ),
    ),
    "CRAWLER_NO_SUCCESS": (
        RemediationActionType.REVIEW_CRAWLER_TARGET,
        RemediationPriority.HIGH,
        RemediationRisk.MEDIUM,
        "최근 crawl 성공이 없는 target 검토 필요",
        (
            "enabled target 중 최근 SUCCESS 기록이 없는지 확인합니다.",
            "worker/scheduler 상태와 target due 상태를 함께 확인합니다.",
        ),
    ),
    "PRICE_NO_HISTORY": (
        RemediationActionType.REVIEW_PRICE_HISTORY,
        RemediationPriority.MEDIUM,
        RemediationRisk.MEDIUM,
        "GPU 가격 history 부재 검토 필요",
        (
            "price_history collection에 관측값이 있는지 확인합니다.",
            "crawler 실패 또는 ingest 문제와 연관 여부를 확인합니다.",
        ),
    ),
    "PRICE_READ_ERROR": (
        RemediationActionType.REVIEW_PRICE_HISTORY,
        RemediationPriority.HIGH,
        RemediationRisk.HIGH,
        "Price operations read error 검토 필요",
        (
            "PriceOperationsView 조회 오류 원인을 확인합니다.",
            "listing / price_history document 상태를 점검합니다.",
        ),
    ),
    "ALERT_NO_RECENT_EVALUATION": (
        RemediationActionType.REVIEW_ALERT,
        RemediationPriority.MEDIUM,
        RemediationRisk.MEDIUM,
        "Alert runner evaluation 부재 검토 필요",
        (
            "Price Alert Runner가 최근 cycle을 수행했는지 확인합니다.",
            "enabled alert와 runner health를 함께 확인합니다.",
        ),
    ),
    "ALERT_READ_ERROR": (
        RemediationActionType.REVIEW_ALERT,
        RemediationPriority.HIGH,
        RemediationRisk.HIGH,
        "Alert read/evaluation 오류 검토 필요",
        (
            "price_alerts document 형식을 확인합니다.",
            "malformed alert가 evaluation을 방해하는지 확인합니다.",
        ),
    ),
    "NOTIFICATION_FAILURE": (
        RemediationActionType.REVIEW_NOTIFICATION,
        RemediationPriority.HIGH,
        RemediationRisk.HIGH,
        "Notification failure 검토 필요",
        (
            "최근 notification failure event를 확인합니다.",
            "channel adapter 설정과 payload를 점검합니다.",
        ),
    ),
    "NOTIFICATION_FAILURE_REPEATED": (
        RemediationActionType.REVIEW_NOTIFICATION,
        RemediationPriority.CRITICAL,
        RemediationRisk.HIGH,
        "반복 notification failure 즉시 검토 필요",
        (
            "반복 실패 channel과 alert를 식별합니다.",
            "adapter 장애 또는 설정 오류 가능성을 우선 확인합니다.",
        ),
    ),
    "RUNNER_CYCLE_FAILED": (
        RemediationActionType.REVIEW_RUNNER,
        RemediationPriority.HIGH,
        RemediationRisk.MEDIUM,
        "Runner cycle failure 검토 필요",
        (
            "최근 runner cycle result와 errors를 확인합니다.",
            "alert evaluation 또는 notification 단계 실패 여부를 확인합니다.",
        ),
    ),
    "RUNNER_CYCLE_FAILURE_REPEATED": (
        RemediationActionType.REVIEW_RUNNER,
        RemediationPriority.CRITICAL,
        RemediationRisk.HIGH,
        "반복 runner cycle failure 즉시 검토 필요",
        (
            "최근 failed cycle 수와 error message를 확인합니다.",
            "alert service / notification adapter 상태를 함께 점검합니다.",
        ),
    ),
    "AUDIT_READ_ERROR": (
        RemediationActionType.REVIEW_AUDIT,
        RemediationPriority.MEDIUM,
        RemediationRisk.MEDIUM,
        "Audit read error 검토 필요",
        (
            "malformed audit event document를 식별합니다.",
            "audit store/event schema 불일치 여부를 확인합니다.",
        ),
    ),
    "RUNNER_HEALTHY": (
        RemediationActionType.NO_ACTION,
        RemediationPriority.LOW,
        RemediationRisk.LOW,
        "Runner cycle 정상 — 추가 조치 불필요",
        ("현재 runner health는 정상입니다.",),
    ),
}


def build_remediation_actions(
    snapshot: DashboardInvestigationSnapshot,
) -> tuple[list[RemediationAction], int]:
    actions: list[RemediationAction] = []
    read_errors = 0
    for finding in snapshot.findings:
        action, error = remediate_finding(finding)
        if error is not None:
            read_errors += 1
        if action is not None:
            actions.append(action)
    return actions, read_errors


def remediate_finding(
    finding: InvestigationFinding,
) -> tuple[RemediationAction | None, str | None]:
    try:
        mapping = FINDING_ACTION_MAP.get(finding.code)
        if mapping is None:
            return (
                _build_action(
                    finding=finding,
                    action_type=RemediationActionType.VERIFY_CONFIGURATION,
                    priority=RemediationPriority.MEDIUM,
                    risk=RemediationRisk.MEDIUM,
                    reason=f"Unknown finding code: {finding.code}",
                    steps=(
                        "Investigation finding code를 확인합니다.",
                        "운영 문서 또는 담당자에게 escalation합니다.",
                    ),
                ),
                None,
            )
        action_type, priority, risk, reason, steps = mapping
        return (
            _build_action(
                finding=finding,
                action_type=action_type,
                priority=priority,
                risk=risk,
                reason=reason,
                steps=steps,
            ),
            None,
        )
    except Exception as exc:
        return (
            RemediationAction(
                action_id=uuid.uuid4().hex,
                action_type=RemediationActionType.VERIFY_CONFIGURATION,
                priority=RemediationPriority.MEDIUM,
                risk=RemediationRisk.MEDIUM,
                finding_id=finding.finding_id,
                area=finding.area,
                title="Remediation rule error",
                reason=str(exc),
                recommended_steps=("Review malformed finding manually.",),
                read_error=str(exc),
                human_approval_required=True,
                auto_executable=False,
            ),
            str(exc),
        )


def _build_action(
    *,
    finding: InvestigationFinding,
    action_type: RemediationActionType,
    priority: RemediationPriority,
    risk: RemediationRisk,
    reason: str,
    steps: tuple[str, ...],
) -> RemediationAction:
    preconditions = _default_preconditions(finding, action_type)
    occurred_at_ts = finding.occurred_at.timestamp() if finding.occurred_at else 0
    return RemediationAction(
        action_id=uuid.uuid4().hex,
        action_type=action_type,
        priority=priority,
        risk=risk,
        finding_id=finding.finding_id,
        area=finding.area,
        target_id=finding.target_id,
        alert_id=finding.alert_id,
        title=finding.title,
        reason=reason,
        recommended_steps=steps,
        preconditions=preconditions,
        human_approval_required=True,
        auto_executable=False,
        metadata={
            "finding_code": finding.code,
            "finding_severity": finding.severity.value,
            "occurred_at_ts": occurred_at_ts,
        },
    )


def _default_preconditions(
    finding: InvestigationFinding,
    action_type: RemediationActionType,
) -> tuple[str, ...]:
    if action_type is RemediationActionType.NO_ACTION:
        return ("No operator action required.",)
    base = ("Human approval required before any automated remediation.",)
    if finding.target_id:
        return base + (f"Target scope: {finding.target_id}",)
    if finding.alert_id:
        return base + (f"Alert scope: {finding.alert_id}",)
    return base
