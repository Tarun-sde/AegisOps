"use client";
import { useEffect, useState, type CSSProperties } from "react";
import {
  getServiceMetrics,
  type MetricSeries,
  type Service,
  type ServiceMetricsResponse,
} from "../lib/api";
import { HealthStatus } from "./project-visuals";

const METRIC_CONFIG = [
  {
    key: "request_rate",
    label: "Request rate",
    unit: "req/s",
    color: "#1d4ed8",
    context: "Requests per second across measured window.",
  },
  {
    key: "error_rate",
    label: "Error rate",
    unit: "%",
    color: "#b91c1c",
    context: "Failed requests (5xx) as a share of measured request volume.",
  },
  {
    key: "p95_latency",
    label: "p95 latency",
    unit: "ms",
    color: "#6d28d9",
    context: "95th percentile of the measured request latency distribution.",
  },
] as const;

export function ServiceAnalytics({ service }: { service: Service }) {
  const [selectedMetricIndex, setSelectedMetricIndex] = useState(0);
  const [window, setWindow] = useState<"15m" | "1h" | "6h" | "24h">("1h");
  const [loading, setLoading] = useState(true);
  const [metricsData, setMetricsData] = useState<ServiceMetricsResponse | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);

    getServiceMetrics(service.id, window).then(({ data, error }) => {
      if (!active) return;
      if (error) {
        setError(error);
        setMetricsData(null);
      } else {
        setMetricsData(data);
      }
      setLoading(false);
    });

    return () => {
      active = false;
    };
  }, [service.id, window]);

  const currentConfig = METRIC_CONFIG[selectedMetricIndex];
  const currentSeries: MetricSeries | undefined =
    metricsData?.metrics?.[currentConfig.key];
  const points = currentSeries?.points ?? [];

  // SVG Chart Geometry
  const svgWidth = 640;
  const svgHeight = 220;
  const padding = { top: 20, right: 30, bottom: 35, left: 55 };
  const chartWidth = svgWidth - padding.left - padding.right;
  const chartHeight = svgHeight - padding.top - padding.bottom;

  let pathD = "";
  let minVal = 0;
  let maxVal = 10;
  let startTime = "";
  let endTime = "";

  if (points.length > 0) {
    const values = points.map((p) => p.value);
    minVal = Math.min(0, ...values);
    maxVal = Math.max(1, ...values) * 1.1; // 10% headroom
    const timestamps = points.map((p) => p.timestamp);
    const minTs = timestamps[0];
    const maxTs = timestamps[timestamps.length - 1];
    const tsRange = maxTs - minTs || 1;
    const valRange = maxVal - minVal || 1;

    startTime = new Date(minTs * 1000).toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });
    endTime = new Date(maxTs * 1000).toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });

    const coords = points.map((p) => {
      const x = padding.left + ((p.timestamp - minTs) / tsRange) * chartWidth;
      const y =
        padding.top +
        chartHeight -
        ((p.value - minVal) / valRange) * chartHeight;
      return [x, y];
    });

    pathD = coords.reduce(
      (acc, [x, y], i) => (i === 0 ? `M ${x} ${y}` : `${acc} L ${x} ${y}`),
      "",
    );
  }

  return (
    <section
      className="an-dashboard application-analytics"
      aria-labelledby="analytics-title"
    >
      <div className="an-section-heading">
        <div>
          <span className="an-eyebrow">Performance & Telemetry</span>
          <h2 id="analytics-title">Application Telemetry</h2>
        </div>
        <HealthStatus health={service.monitoring_status || "unknown"} />
      </div>

      {error && (
        <div
          role="alert"
          style={{
            padding: "10px 14px",
            background: "#fef2f2",
            border: "1px solid #fecaca",
            borderRadius: 6,
            color: "#991b1b",
            fontSize: 13,
            marginBottom: 16,
          }}
        >
          {error}
        </div>
      )}

      <div className="an-toolbar">
        <label>
          Metric
          <select
            aria-label="Performance metric"
            value={selectedMetricIndex}
            onChange={(e) => setSelectedMetricIndex(Number(e.target.value))}
          >
            {METRIC_CONFIG.map((cfg, i) => (
              <option key={cfg.key} value={i}>
                {cfg.label}
              </option>
            ))}
          </select>
        </label>

        <label>
          Time Window
          <select
            aria-label="Time window"
            value={window}
            onChange={(e) =>
              setWindow(e.target.value as "15m" | "1h" | "6h" | "24h")
            }
          >
            <option value="15m">Last 15 minutes</option>
            <option value="1h">Last 1 hour</option>
            <option value="6h">Last 6 hours</option>
            <option value="24h">Last 24 hours</option>
          </select>
        </label>

        <div
          style={{
            marginLeft: "auto",
            display: "flex",
            alignItems: "center",
            gap: 12,
          }}
        >
          {loading && <span className="an-eyebrow">Loading telemetry...</span>}
          {metricsData?.is_instrumented ? (
            <span
              className="ws-tag ws-health-reachable"
              style={{ fontSize: 13 }}
            >
              ● Prometheus Scraped
            </span>
          ) : (
            <span
              className="ws-tag"
              style={{ fontSize: 13, background: "#f1f5f9" }}
            >
              ○ Uninstrumented
            </span>
          )}
        </div>
      </div>

      <div className="an-metrics">
        {METRIC_CONFIG.map((cfg, index) => {
          const s = metricsData?.metrics?.[cfg.key];
          const hasVal = s?.current_value != null;
          return (
            <button
              key={cfg.key}
              className="an-metric"
              aria-pressed={index === selectedMetricIndex}
              onClick={() => setSelectedMetricIndex(index)}
              style={{ "--series": cfg.color } as CSSProperties}
            >
              <span className="an-metric-label">
                {cfg.label}
                <span aria-hidden="true">
                  {index === selectedMetricIndex ? "●" : "↗"}
                </span>
              </span>
              <strong>
                {hasVal ? s.current_value?.toFixed(1) : "—"}{" "}
                <small>{cfg.unit}</small>
              </strong>
              <span className="an-delta">
                {hasVal ? "Live Telemetry" : "Unavailable"}
              </span>
              <span className="an-metric-context">{cfg.context}</span>
            </button>
          );
        })}

        <div className="an-metric application-incident-metric">
          <span className="an-metric-label">Active incidents</span>
          <strong>{service.active_incident_count ?? "0"}</strong>
          <span className="an-delta">Open or Reopened</span>
          <span className="an-metric-context">
            Deduplicated operational incidents in active workspace.
          </span>
        </div>
      </div>

      <section
        className="an-panel an-primary-chart"
        aria-labelledby="chart-title"
      >
        <div className="an-section-heading">
          <div>
            <span className="an-eyebrow">Timeseries Analysis</span>
            <h3 id="chart-title">{currentConfig.label}</h3>
          </div>
          <span className="mono" style={{ fontSize: 13 }}>
            {service.name} · {window}
          </span>
        </div>

        <div className="an-chart">
          <div className="an-chart-legend">
            <span>
              <i style={{ background: currentConfig.color }} />
              {currentConfig.label} ({currentConfig.unit})
            </span>
            <span>
              {points.length > 0
                ? `${points.length} measurements recorded`
                : "No values plotted"}
            </span>
          </div>

          {points.length > 0 ? (
            <svg
              className="an-chart-svg"
              viewBox={`0 0 ${svgWidth} ${svgHeight}`}
              aria-label={`Time series chart for ${currentConfig.label}`}
              style={{ maxHeight: 260 }}
            >
              {/* Horizontal gridlines */}
              <line
                x1={padding.left}
                y1={padding.top}
                x2={svgWidth - padding.right}
                y2={padding.top}
                className="an-gridline"
              />
              <text x={padding.left - 8} y={padding.top + 4} textAnchor="end">
                {maxVal.toFixed(1)}
              </text>

              <line
                x1={padding.left}
                y1={padding.top + chartHeight / 2}
                x2={svgWidth - padding.right}
                y2={padding.top + chartHeight / 2}
                className="an-gridline"
              />
              <text
                x={padding.left - 8}
                y={padding.top + chartHeight / 2 + 4}
                textAnchor="end"
              >
                {((maxVal + minVal) / 2).toFixed(1)}
              </text>

              <line
                x1={padding.left}
                y1={padding.top + chartHeight}
                x2={svgWidth - padding.right}
                y2={padding.top + chartHeight}
                className="an-gridline"
              />
              <text
                x={padding.left - 8}
                y={padding.top + chartHeight + 4}
                textAnchor="end"
              >
                {minVal.toFixed(1)}
              </text>

              {/* Data Path */}
              <path
                d={pathD}
                className="an-series"
                style={{ stroke: currentConfig.color }}
              />

              {/* Start & End Timestamps */}
              <text
                x={padding.left}
                y={svgHeight - 10}
                textAnchor="start"
                className="mono"
              >
                {startTime}
              </text>
              <text
                x={svgWidth - padding.right}
                y={svgHeight - 10}
                textAnchor="end"
                className="mono"
              >
                {endTime}
              </text>
            </svg>
          ) : (
            <div className="an-empty-chart" role="status">
              <div>
                <span className="mono">TELEMETRY UNINSTRUMENTED</span>
                <h3>No performance data available yet.</h3>
                <p className="an-empty-subtitle">
                  No performance data scraped for {service.name} yet.
                </p>
                <p>{currentConfig.context}</p>
                <p>
                  This application does not yet have Prometheus metrics scraped.
                  To export request rates, error rates, and p95 latency curves,
                  follow the safe instrumentation guide in{" "}
                  <code>docs/EXTERNAL_APPLICATION_INSTRUMENTATION.md</code>.
                </p>
              </div>
            </div>
          )}
        </div>

        <p className="an-footnote">
          AegisOps strictly isolates telemetry per authenticated service.
          Missing telemetry does not imply zero traffic or operational failure.
        </p>
      </section>
    </section>
  );
}
