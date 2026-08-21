export type ActionPriority = "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | "UNKNOWN";

export function normalizePriority(value: string | undefined): ActionPriority {
  const normalized = (value ?? "UNKNOWN").toUpperCase();
  if (
    normalized === "CRITICAL" ||
    normalized === "HIGH" ||
    normalized === "MEDIUM" ||
    normalized === "LOW"
  ) {
    return normalized;
  }
  return "UNKNOWN";
}

interface PriorityBadgeProps {
  priority: string;
}

export function PriorityBadge({ priority }: PriorityBadgeProps) {
  const normalized = normalizePriority(priority);
  return (
    <span className={`priority-badge priority-${normalized.toLowerCase()}`}>{normalized}</span>
  );
}
