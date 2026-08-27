interface ResourceRefProps {
  kind: "Target" | "Alert";
  value: string;
}

export function ResourceRef({ kind, value }: ResourceRefProps) {
  const label = kind === "Target" ? "대상" : "알림";
  return (
    <span className="resource-ref" aria-disabled="true" title={`${label} 상세 보기 (준비 중)`}>
      {label}: {value}
    </span>
  );
}
