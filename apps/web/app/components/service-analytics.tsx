"use client";
import { useState, type CSSProperties } from "react";
import Link from "next/link";
import type { Service, IncidentListResponse } from "../lib/api";
import { HealthStatus } from "./project-visuals";
import { DetailDialog } from "./detail-dialog";
import { StatusBadge } from "./status-badge";
const metrics = [
  [
    "Request rate",
    "req/s",
    "#1d4ed8",
    "Requests per second across a defined interval.",
  ],
  [
    "Error rate",
    "%",
    "#b91c1c",
    "Failed requests divided by total requests; weighted by volume.",
  ],
  [
    "p95 latency",
    "ms",
    "#6d28d9",
    "95th percentile of the latency distribution.",
  ],
  [
    "p99 latency",
    "ms",
    "#6d28d9",
    "99th percentile of the latency distribution.",
  ],
  [
    "Success SLI",
    "%",
    "#166534",
    "Successful eligible requests divided by eligible requests.",
  ],
  [
    "Error budget",
    "%",
    "#92400e",
    "Requires a defined SLO target and compliance window.",
  ],
];
export function ServiceAnalytics({
  service,
  incidents,
  error,
}: {
  service: Service;
  incidents: IncidentListResponse | null;
  error: string | null;
}) {
  const [metric, setMetric] = useState(0),
    [drawer, setDrawer] = useState(false);
  const rows =
    incidents?.items.filter((i) => i.service_id === service.id) ?? [];
  return (
    <div className="an-dashboard">
      <section id="analytics">
        <div className="an-section-heading">
          <div>
            <span className="an-eyebrow">01 / Operational analytics</span>
            <h2>Understand the signal.</h2>
          </div>
          <span className="an-demo">Telemetry unavailable</span>
        </div>
        <div className="an-alert">
          <span className="badge badge-neutral">Unknown</span>
          <div>
            <h3>Live series unavailable</h3>
            <p>
              This API does not expose scoped time-series data. Registration
              does not establish monitoring health.
            </p>
          </div>
          <Link className="ws-button" href="/onboarding">
            Review connection ↗
          </Link>
        </div>
        <div className="an-toolbar">
          <label>
            Selected period
            <select aria-label="Time range" disabled>
              <option>Unavailable</option>
            </select>
          </label>
          <label>
            Service scope
            <select aria-label="Service scope" disabled>
              <option>{service.name}</option>
            </select>
          </label>
          <label className="an-check">
            <input type="checkbox" disabled />
            Compare previous period
          </label>
          <span className="an-resolution">
            Auto resolution
            <br />
            <strong>Not available</strong>
          </span>
        </div>
        <p className="an-clock">
          No observation window reported · No live readings plotted
          <br />
          Service scope: {service.id}
        </p>
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
              <span className="an-delta">No measurement available</span>
              <span className="an-metric-context">{context}</span>
            </button>
          ))}
        </div>
        <section
          className="an-panel an-primary-chart"
          aria-labelledby="chart-title"
        >
          <div className="an-section-heading">
            <div>
              <span className="an-eyebrow">Selected metric</span>
              <h3 id="chart-title">{metrics[metric][0]}</h3>
            </div>
            <span>{service.name} · No observation window</span>
          </div>
          <div className="an-chart">
            <div className="an-chart-legend">
              <span>
                <i style={{ background: metrics[metric][2] }} />
                {metrics[metric][0]}
              </span>
              <span>No values plotted</span>
            </div>
            <div className="an-empty-chart" role="status">
              <div>
                <span className="mono">NO AUTHORIZED SERIES</span>
                <h3>Waiting for a supported data source.</h3>
                <p>{metrics[metric][3]}</p>
                <p>
                  A scoped aggregation API is required to display this metric.
                  No healthy value is inferred.
                </p>
              </div>
            </div>
          </div>
          <p className="an-footnote">
            Chart interaction and comparisons become available when a scoped
            series contract is supported.
          </p>
        </section>
      </section>
      <section className="an-panel" id="services">
        <div className="an-section-heading">
          <div>
            <span className="an-eyebrow">02 / Service breakdown</span>
            <h2>Find the affected service.</h2>
          </div>
        </div>
        <p>
          Registered service inventory. Health and request statistics are not
          reported by this endpoint.
        </p>
        {/* Scrollable table region is keyboard focusable for horizontal panning. */}
        <div
          className="an-table-scroll"
          // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex
          tabIndex={0}
          role="region"
          aria-label="Service analytics"
        >
          <table className="an-service-table">
            <thead>
              <tr>
                {[
                  "Service",
                  "Health now",
                  "Rate (req/s)",
                  "Error rate",
                  "p95",
                  "Last telemetry",
                  "Incidents",
                ].map((v) => (
                  <th key={v}>{v}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              <tr>
                <th>
                  <button
                    className="an-text-button"
                    onClick={() => setDrawer(true)}
                  >
                    {service.name} ↗
                  </button>
                  <small>{service.environment}</small>
                </th>
                <td>
                  <HealthStatus health="unknown" />
                </td>
                <td>—</td>
                <td>—</td>
                <td>—</td>
                <td>Not reported</td>
                <td>
                  {incidents ? `${rows.length} on latest page` : "Unavailable"}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
      <section className="an-panel" id="incidents">
        <div className="an-section-heading">
          <div>
            <span className="an-eyebrow">03 / Incident register</span>
            <h2>From signal to investigation.</h2>
          </div>
          <Link className="ws-button" href="/app/incidents">
            All incidents ↗
          </Link>
        </div>
        {error ? (
          <p role="alert">{error}</p>
        ) : rows.length ? (
          rows.map((i) => (
            <article className="an-incident-row" key={i.id}>
              <div>
                <StatusBadge value={i.severity} />
                <StatusBadge value={i.status} />
                <h3>{i.title}</h3>
                <p>Started {new Date(i.started_at).toISOString()} UTC</p>
                <span className="mono">{i.id}</span>
              </div>
              <Link
                className="ws-button ws-primary"
                href={`/app/incidents/${i.id}`}
              >
                Open investigation →
              </Link>
            </article>
          ))
        ) : (
          <p>
            No service incidents on the latest returned page. This is not a
            health measurement.
          </p>
        )}
      </section>
      <DetailDialog
        open={drawer}
        onClose={() => setDrawer(false)}
        title={service.name}
        drawer
      >
        <p>{service.description || "No description provided."}</p>
        <HealthStatus health="unknown" />
        <dl className="an-facts">
          <div>
            <dt>Service</dt>
            <dd>{service.id}</dd>
          </div>
          <div>
            <dt>Environment</dt>
            <dd>{service.environment}</dd>
          </div>
          <div>
            <dt>Registration</dt>
            <dd>{service.status}</dd>
          </div>
          <div>
            <dt>Connection freshness</dt>
            <dd>Not reported</dd>
          </div>
        </dl>
      </DetailDialog>
    </div>
  );
}
