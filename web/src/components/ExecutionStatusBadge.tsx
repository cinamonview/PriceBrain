export type ExecutionStatus =
  | "PLANNED"
  | "DRY_RUN"
  | "EXECUTED"
  | "BLOCKED"
  | "FAILED"
  | "APPROVED"
  | "SKIPPED"
  | "UNKNOWN";

export function normalizeExecutionStatus(value: string | undefined): ExecutionStatus {
  const normalized = (value ?? "UNKNOWN").toUpperCase();
  if (
    normalized === "PLANNED" ||
    normalized === "DRY_RUN" ||
    normalized === "EXECUTED" ||
    normalized === "BLOCKED" ||
    normalized === "FAILED" ||
    normalized === "APPROVED" ||
    normalized === "SKIPPED"
  ) {
    return normalized;
  }
  return "UNKNOWN";
}

interface ExecutionStatusBadgeProps {
  status: string;
}

export function ExecutionStatusBadge({ status }: ExecutionStatusBadgeProps) {
  const normalized = normalizeExecutionStatus(status);
  return (
    <span className={`execution-status execution-status-${normalized.toLowerCase()}`}>
      {normalized}
    </span>
  );
}
