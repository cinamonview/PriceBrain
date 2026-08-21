export type AuditEventTypeBadgeValue =
  | "ALERT"
  | "NOTIFICATION"
  | "RUNNER"
  | "REMEDIATION"
  | "UNKNOWN";

export function normalizeAuditEventType(value: string | undefined): AuditEventTypeBadgeValue {
  const normalized = (value ?? "UNKNOWN").toUpperCase();
  if (normalized.startsWith("ALERT_")) {
    return "ALERT";
  }
  if (normalized.startsWith("NOTIFICATION_")) {
    return "NOTIFICATION";
  }
  if (normalized.startsWith("RUNNER_")) {
    return "RUNNER";
  }
  if (normalized.startsWith("REMEDIATION_")) {
    return "REMEDIATION";
  }
  return "UNKNOWN";
}

interface AuditEventTypeBadgeProps {
  eventType: string;
}

export function AuditEventTypeBadge({ eventType }: AuditEventTypeBadgeProps) {
  const normalized = normalizeAuditEventType(eventType);
  return (
    <span className={`audit-event-type audit-event-type-${normalized.toLowerCase()}`}>
      {eventType}
    </span>
  );
}
