import { Link } from "react-router-dom";
import { HealthBadge } from "./HealthBadge";

interface MetricItem {
  label: string;
  value: string | number;
}

interface CommandCenterAreaCardProps {
  title: string;
  health?: string;
  statusLabel?: string;
  statusValue?: string;
  metrics: MetricItem[];
  readError?: string | null;
  linkTo: string;
  linkLabel: string;
}

export function CommandCenterAreaCard({
  title,
  health,
  statusLabel,
  statusValue,
  metrics,
  readError,
  linkTo,
  linkLabel,
}: CommandCenterAreaCardProps) {
  return (
    <section className="section-card command-center-area-card">
      <header>
        <h3>{title}</h3>
        {health ? <HealthBadge label={`${title} Health`} status={health} /> : null}
      </header>
      {readError ? <p className="read-error-banner">{readError}</p> : null}
      {statusLabel && statusValue ? (
        <p className="command-center-status-line">
          <span>{statusLabel}</span>
          <strong>{statusValue}</strong>
        </p>
      ) : null}
      <ul className="metric-list">
        {metrics.map((metric) => (
          <li key={metric.label}>
            <span>{metric.label}</span>
            <span>{metric.value}</span>
          </li>
        ))}
      </ul>
      <div className="action-card-links">
        <Link to={linkTo}>{linkLabel}</Link>
      </div>
    </section>
  );
}
