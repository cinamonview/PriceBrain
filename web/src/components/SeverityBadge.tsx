export type FindingSeverity = "CRITICAL" | "ERROR" | "WARNING" | "INFO" | "UNKNOWN";

export function normalizeSeverity(value: string | undefined): FindingSeverity {
  const normalized = (value ?? "UNKNOWN").toUpperCase();
  if (
    normalized === "CRITICAL" ||
    normalized === "ERROR" ||
    normalized === "WARNING" ||
    normalized === "INFO"
  ) {
    return normalized;
  }
  return "UNKNOWN";
}

interface SeverityBadgeProps {
  severity: string;
  compact?: boolean;
}

import { formatSeverityLabel } from "../utils/uiLabels";

export function SeverityBadge({ severity, compact = false }: SeverityBadgeProps) {
  const normalized = normalizeSeverity(severity);
  return (
    <span
      className={`severity-badge severity-${normalized.toLowerCase()}${compact ? " compact" : ""}`}
      title={normalized}
    >
      {formatSeverityLabel(normalized)}
    </span>
  );
}

export function severityHint(severity: FindingSeverity): string {
  switch (severity) {
    case "CRITICAL":
      return "즉시 확인이 필요한 상태";
    case "ERROR":
      return "운영 오류";
    case "WARNING":
      return "확인 권장";
    case "INFO":
      return "정상 또는 참고 정보";
    default:
      return "상태 확인 필요";
  }
}
