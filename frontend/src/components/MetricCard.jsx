export default function MetricCard({
  title,
  value,
  unit = "%",
  description,
  icon,
  badgeText,
}) {
  const numericValue = Number(value);
  const formattedValue = Number.isFinite(numericValue)
    ? numericValue.toFixed(1)
    : "0.0";

  const percentage = Math.min(
    100,
    Math.max(0, numericValue || 0)
  );

  let statusClass = "progress-normal";
  if (percentage >= 85) {
    statusClass = "progress-danger";
  } else if (percentage >= 65) {
    statusClass = "progress-warning";
  }

  return (
    <div className="metric-card">
      <div className="metric-card-top">
        <div className="metric-info">
          <div className="metric-label-row">
            <span className="metric-title">{title}</span>
            {badgeText && <span className="metric-badge">{badgeText}</span>}
          </div>
          <h3 className="metric-value">
            {formattedValue}
            <span className="metric-unit">{unit}</span>
          </h3>
        </div>

        <div className="metric-icon-wrap" aria-hidden="true">
          {icon}
        </div>
      </div>

      <div
        className="progress-track"
        role="progressbar"
        aria-valuenow={percentage}
        aria-valuemin="0"
        aria-valuemax="100"
      >
        <div
          className={`progress-fill ${statusClass}`}
          style={{ width: `${percentage}%` }}
        />
      </div>

      {description && <p className="metric-description">{description}</p>}
    </div>
  );
}
