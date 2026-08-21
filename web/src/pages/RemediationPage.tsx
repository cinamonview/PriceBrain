export function RemediationPage() {
  return (
    <div className="placeholder-page">
      <h2>Remediation</h2>
      <div className="policy-banner">
        <strong>Plan only</strong>
        <span>Human approval required</span>
        <span>Auto execution disabled</span>
      </div>
      <p>
        This dashboard phase exposes remediation planning policy only. No execute action, approval token
        input, or mutation controls are available in the web UI.
      </p>
    </div>
  );
}
