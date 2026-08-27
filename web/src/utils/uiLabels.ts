/** 사용자 표시용 한국어 UI 라벨 — API enum/필드명은 변경하지 않음 */

export const UI = {
  appName: "PriceBrain",
  operationsTitle: "PriceBrain 운영",
  operationsDashboard: "운영 대시보드",
  commandCenter: "운영 센터",
  dashboard: "대시보드",
  investigation: "조사",
  remediation: "조치 계획",
  executionHistory: "실행 이력",
  audit: "감사 로그",
  logout: "로그아웃",
  refresh: "새로고침",
  retry: "다시 시도",
  close: "닫기",
  loading: "불러오는 중...",
  signingIn: "로그인 중...",
  signIn: "로그인",
  email: "이메일",
  password: "비밀번호",
  unknownUser: "알 수 없는 사용자",
  backend: "백엔드",
  generatedAt: "생성 시각",
  lastRefresh: "마지막 새로고침",
  readOnly: "읽기 전용",
  summary: "요약",
  filters: "필터",
  viewControls: "보기 설정",
  search: "검색",
  all: "전체",
  failuresOnly: "실패 항목만",
  recent: "최근",
  yes: "예",
  no: "아니오",
  apply: "적용",
  reset: "초기화",
  details: "상세 보기",
  back: "뒤로",
  viewInvestigation: "조사 보기",
  viewRemediation: "조치 계획 보기",
  viewExecution: "실행 이력 보기",
  viewAudit: "감사 로그 보기",
  viewFinding: "발견 사항 보기",
  reviewAction: "조치 검토",
  noData: "표시할 데이터가 없습니다.",
  readError: "읽기 오류",
  metadata: "메타데이터",
  area: "영역",
  severity: "심각도",
  target: "대상",
  alert: "알림",
  message: "메시지",
  status: "상태",
  cause: "원인",
  occurred: "발생",
  required: "필요",
  notRequired: "불필요",
  planOnly: "계획만 생성",
  humanApprovalRequired: "사용자 승인 필요",
  autoExecutionDisabled: "자동 실행 비활성화",
  approvalRequired: "승인 필요",
  autoExecution: "자동 실행",
  flagged: "건 표시됨",
} as const;

const HEALTH_LABELS: Record<string, string> = {
  HEALTHY: "정상",
  PASS: "정상",
  DEGRADED: "일부 문제",
  CRITICAL: "치명적",
  UNKNOWN: "확인 불가",
};

const SEVERITY_LABELS: Record<string, string> = {
  ALL: "전체",
  CRITICAL: "치명적",
  ERROR: "오류",
  WARNING: "경고",
  INFO: "정보",
  UNKNOWN: "확인 불가",
};

const PRIORITY_LABELS: Record<string, string> = {
  CRITICAL: "치명적",
  HIGH: "높음",
  MEDIUM: "보통",
  LOW: "낮음",
  UNKNOWN: "확인 불가",
};

const EXECUTION_STATUS_LABELS: Record<string, string> = {
  PLANNED: "계획됨",
  DRY_RUN: "시험 실행",
  EXECUTED: "실행 완료",
  BLOCKED: "차단됨",
  FAILED: "실패",
  APPROVED: "승인됨",
  SKIPPED: "건너뜀",
  UNKNOWN: "확인 불가",
};

const AREA_LABELS: Record<string, string> = {
  crawler: "크롤러",
  price: "가격",
  alert: "가격 알림",
  notification: "알림 전송",
  runner: "실행기",
  audit: "감사 로그",
};

const ROLE_LABELS: Record<string, string> = {
  OPS_ADMIN: "운영 관리자",
  OPS_OPERATOR: "운영 담당자",
  OPS_VIEWER: "운영 조회자",
  NO_ROLE: "권한 없음",
};

const CONNECTION_LABELS: Record<string, string> = {
  connected: "연결됨",
  degraded: "인증 필요",
  error: "사용 불가",
  unknown: "확인 중...",
};

const FINDING_TITLE_LABELS: Record<string, string> = {
  CRAWLER_ACCESS_DENIED: "크롤러 접근 거부",
  CRAWLER_READ_ERROR: "크롤러 읽기 오류",
  CRAWLER_HTTP_ERROR: "크롤러 HTTP 오류",
  RUNNER_CYCLE_FAILURE: "실행기 주기 실패 반복",
  RUNNER_OK: "실행기 정상",
  NO_RECENT_SUCCESS: "최근 성공 기록 없음",
  NO_PRICE_HISTORY: "최근 가격 기록 없음",
  PRICE_INVALID: "가격 데이터 오류",
};

const AUDIT_EVENT_LABELS: Record<string, string> = {
  ALERT_EVALUATED: "알림 평가",
  ALERT_TRIGGERED: "알림 발생",
  ALERT_SKIPPED: "알림 건너뜀",
  ALERT_INVALID: "알림 무효",
  ALERT_CREATED: "알림 생성",
  NOTIFICATION_SENT: "알림 전송 완료",
  NOTIFICATION_FAILED: "알림 전송 실패",
  NOTIFICATION_SKIPPED: "알림 전송 건너뜀",
  RUNNER_CYCLE_COMPLETED: "실행기 주기 완료",
  RUNNER_CYCLE_FAILED: "실행기 주기 실패",
  REMEDIATION_PLANNED: "조치 계획 생성",
  REMEDIATION_APPROVAL_BLOCKED: "조치 승인 차단",
  REMEDIATION_DRY_RUN: "조치 시험 실행",
  REMEDIATION_EXECUTED: "조치 실행 완료",
  REMEDIATION_FAILED: "조치 실패",
};

const SORT_LABELS: Record<string, string> = {
  NEWEST: "최신순",
  OLDEST: "오래된순",
  TYPE: "유형순",
  SEVERITY: "심각도순",
  STATUS: "상태순",
  DURATION: "소요 시간순",
};

const MODE_LABELS: Record<string, string> = {
  ALL: "전체",
  DRY_RUN: "시험 실행",
  LIVE: "실제 실행",
  PLAN: "계획",
  EXECUTE: "실행",
};

function normalizeKey(value: string): string {
  return value.trim().toUpperCase();
}

export function formatHealthStatus(status: string | undefined): string {
  const key = normalizeKey(status ?? "UNKNOWN");
  return HEALTH_LABELS[key] ?? status ?? "확인 불가";
}

export function formatSeverityLabel(severity: string): string {
  const key = normalizeKey(severity);
  return SEVERITY_LABELS[key] ?? severity;
}

export function formatPriorityLabel(priority: string): string {
  const key = normalizeKey(priority);
  return PRIORITY_LABELS[key] ?? priority;
}

export function formatExecutionStatusLabel(status: string): string {
  const key = normalizeKey(status);
  return EXECUTION_STATUS_LABELS[key] ?? status;
}

export function formatAreaLabel(area: string): string {
  const key = area.trim().toLowerCase();
  if (!key || key === "unknown") {
    return "확인 불가";
  }
  return AREA_LABELS[key] ?? area;
}

export function formatRoleLabel(role: string): string {
  return ROLE_LABELS[role] ?? role;
}

export function formatConnectionLabel(status: string): string {
  return CONNECTION_LABELS[status] ?? status;
}

export function formatFindingTitle(code: string, fallback: string): string {
  const key = normalizeKey(code);
  return FINDING_TITLE_LABELS[key] ?? fallback;
}

export function formatAuditEventTypeLabel(eventType: string): string {
  const key = normalizeKey(eventType);
  return AUDIT_EVENT_LABELS[key] ?? eventType.replace(/_/g, " ");
}

export function formatSortLabel(sort: string): string {
  const key = normalizeKey(sort);
  return SORT_LABELS[key] ?? sort;
}

export function formatModeLabel(mode: string): string {
  const key = normalizeKey(mode);
  return MODE_LABELS[key] ?? mode;
}

export function formatYesNo(value: boolean): string {
  return value ? UI.yes : UI.no;
}

export function formatHealthLabel(prefix: string): string {
  return `${prefix} 상태`;
}

export function formatAutoRefresh(seconds: number): string {
  return `${seconds}초마다 자동 새로고침 (${UI.readOnly})`;
}

export function formatResourceKind(kind: "Target" | "Alert"): string {
  return kind === "Target" ? UI.target : UI.alert;
}

export function formatReadErrorBanner(error: string): string {
  const lower = error.toLowerCase();
  if (lower.includes("resourceexhausted") || lower.includes("429") || lower.includes("quota")) {
    return "Firestore 읽기 한도 초과";
  }
  return error;
}
