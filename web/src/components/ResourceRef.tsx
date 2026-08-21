interface ResourceRefProps {
  kind: "Target" | "Alert";
  value: string;
}

export function ResourceRef({ kind, value }: ResourceRefProps) {
  return (
    <span className="resource-ref" aria-disabled="true" title={`${kind} detail view coming soon`}>
      {kind}: {value}
    </span>
  );
}
