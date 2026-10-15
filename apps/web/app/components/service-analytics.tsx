"use client";
import { useState, type CSSProperties } from "react";
import type { Service } from "../lib/api";
// DEC-387: approved AnalyticsDashboard/TimeSeries frame, without the demo generator.
const metrics = [
  [
    "Request rate",
    "req/s",
    "#1d4ed8",
    "Requests per second across a measured interval.",
  ],
  [
    "Error rate",
    "%",
    "#b91c1c",
    "Failed requests as a share of measured request volume.",
  ],
  [
    "p95 latency",
    "ms",
    "#6d28d9",
    "95th percentile of the measured latency distribution.",
  ],
];
export function ServiceAnalytics({ service }: { service: Service }) {
  const [metric, setMetric] = useState(0);
  return (
    <section
      className="an-dashboard application-analytics"
      aria-labelledby="analytics-title"
    >
      <div className="an-section-heading">
        <div>
          <span className="an-eyebrow">Performance</span>
          <h2 id="analytics-title">Understand the signal.</h2>
        </div>
        <span className="ws-tag">Monitoring unknown</span>
      </div>
      <div className="an-toolbar">
        <label>
          Metric
          <select
            aria-label="Performance metric"
            value={metric}
            onChange={(e) => setMetric(Number(e.target.value))}
          >
            {metrics.map(([label], i) => (
              <option key={label} value={i}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <p>Time range unavailable · No measured series</p>
      </div>
      <div className="an-metrics">
        {metrics.map(([label, unit, color, context], index) => (
          <button
            key={label}
            className="an-metric"
            aria-pressed={index === metric}
            onClick={() => setMetric(index)}
            style={{ "--series": color } as CSSProperties}
          >
            <span className="an-metric-label">
              {label}
              <span aria-hidden="true">{index === metric ? "●" : "↗"}</span>
            </span>
            <strong>
              — <small>{unit}</small>
            </strong>
            <span className="an-delta">Unavailable</span>
            <span className="an-metric-context">{context}</span>
          </button>
        ))}
        <div className="an-metric application-incident-metric">
          <span className="an-metric-label">Active incidents</span>
          <strong>{service.active_incident_count ?? "—"}</strong>
          <span className="an-delta">Persisted incident records</span>
          <span className="an-metric-context">
            An incident count is not a health measurement.
          </span>
        </div>
      </div>
      <section
        className="an-panel an-primary-chart"
        aria-labelledby="chart-title"
      >
        <div className="an-section-heading">
          <div>
            <span className="an-eyebrow">Application performance</span>
            <h3 id="chart-title">{metrics[metric][0]}</h3>
          </div>
          <span>{service.name}</span>
        </div>
        <div className="an-chart">
          <div className="an-chart-legend">
            <span>
              <i style={{ background: metrics[metric][2] }} />
              {metrics[metric][0]} · {metrics[metric][1]}
            </span>
            <span>No values plotted</span>
          </div>
          <div className="an-empty-chart" role="status">
            <div>
              <span className="mono">TELEMETRY UNAVAILABLE</span>
              <h3>No performance data available yet.</h3>
              <p>{metrics[metric][3]}</p>
              <p>
                A service-scoped time-series source is not available. Missing
                data does not mean zero traffic or zero errors.
              </p>
            </div>
          </div>
        </div>
        <p className="an-footnote">
          Registration and HTTP healthchecks do not establish metrics, logs or
          traces. Incident evidence is available separately when collected.
        </p>
      </section>
    </section>
  );
}
