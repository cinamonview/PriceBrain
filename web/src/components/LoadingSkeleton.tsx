export function InvestigationLoadingSkeleton() {
  return (
    <div className="page-stack investigation-loading" aria-busy="true" aria-live="polite">
      <div className="skeleton-block skeleton-title" />
      <div className="summary-grid">
        {Array.from({ length: 5 }).map((_, index) => (
          <div key={index} className="skeleton-block skeleton-card" />
        ))}
      </div>
      <div className="skeleton-block skeleton-filter" />
      {Array.from({ length: 3 }).map((_, index) => (
        <div key={index} className="skeleton-block skeleton-finding" />
      ))}
    </div>
  );
}
