import type { ReactNode } from "react";
import type { HealthStatus } from "../api/types";
import { UI, formatHealthStatus } from "../utils/uiLabels";

export function normalizeHealth(value: string | undefined): HealthStatus {
  const normalized = (value ?? "UNKNOWN").toUpperCase();
  if (
    normalized === "HEALTHY" ||
    normalized === "DEGRADED" ||
    normalized === "CRITICAL" ||
    normalized === "UNKNOWN"
  ) {
    return normalized;
  }
  return "UNKNOWN";
}

interface HealthBadgeProps {
  label: string;
  status: string;
}

export function HealthBadge({ label, status }: HealthBadgeProps) {
  const normalized = normalizeHealth(status);
  return (
    <div className={`health-badge health-${normalized.toLowerCase()}`}>
      <span className="health-badge-label">{label}</span>
      <strong>{formatHealthStatus(normalized)}</strong>
    </div>
  );
}

interface QueryStateProps {
  status: string;
  message?: string | null;
  onRetry?: () => void;
}

export function QueryState({ status, message, onRetry }: QueryStateProps) {
  if (status === "loading" || status === "idle") {
    return <div className="query-state">{UI.loading}</div>;
  }
  if (status === "unauthorized") {
    return <div className="query-state error">{message ?? "인증이 필요합니다."}</div>;
  }
  if (status === "forbidden") {
    return <div className="query-state error">{message ?? "이 작업을 볼 권한이 없습니다."}</div>;
  }
  if (status === "error") {
    return (
      <div className="query-state error">
        <p>{message ?? "운영 정보를 불러오지 못했습니다."}</p>
        {onRetry ? (
          <button type="button" onClick={onRetry}>
            {UI.retry}
          </button>
        ) : null}
      </div>
    );
  }
  return null;
}

interface SectionCardProps {
  title: string;
  children: ReactNode;
  readError?: string | null;
}

export function SectionCard({ title, children, readError }: SectionCardProps) {
  return (
    <section className="section-card">
      <header>
        <h3>{title}</h3>
        {readError ? <span className="read-error">{UI.readError}</span> : null}
      </header>
      <div>{children}</div>
    </section>
  );
}
