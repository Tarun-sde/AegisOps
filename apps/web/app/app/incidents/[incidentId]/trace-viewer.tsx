"use client";

import { useState } from "react";
import { TraceSummary, Span, getTrace } from "../../../lib/api";

interface TraceViewerProps {
  initialTraceId?: string;
}

export function TraceViewer({ initialTraceId = "" }: TraceViewerProps) {
  const [traceId, setTraceId] = useState(initialTraceId);
  const [loading, setLoading] = useState(false);
  const [trace, setTrace] = useState<TraceSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleFetchTrace = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const cleanId = traceId.trim();
    if (!cleanId) return;

    setLoading(true);
    setError(null);
    const res = await getTrace(cleanId);
    if (res.error || !res.data) {
      setError(res.error || "Trace not found or contains no spans.");
      setTrace(null);
    } else {
      setTrace(res.data);
    }
    setLoading(false);
  };

  const maxDuration = trace && trace.duration_ms > 0 ? trace.duration_ms : 1;

  return (
    <section
      aria-labelledby="trace-viewer-heading"
      className="panel"
      style={{ marginTop: "24px" }}
    >
      <p className="eyebrow">Distributed Tracing / Grafana Tempo</p>
      <div className="heading" style={{ marginBottom: "16px" }}>
        <h2 id="trace-viewer-heading" style={{ margin: 0 }}>
          Trace Inspection
        </h2>
        <span className="badge">OTel · W3C TraceContext</span>
      </div>

      <form
        onSubmit={handleFetchTrace}
        style={{ display: "flex", gap: "12px", marginBottom: "20px" }}
      >
        <input
          type="text"
          value={traceId}
          onChange={(e) => setTraceId(e.target.value)}
          placeholder="Enter 32-hex trace ID (e.g. 4bf92f3577b34da6a3ce929d0e0e4736)"
          style={{
            flex: 1,
            padding: "8px 12px",
            background: "#101416",
            border: "1px solid #343e40",
            borderRadius: "5px",
            color: "#edf1f2",
            fontFamily: "monospace",
            fontSize: "13px",
          }}
        />
        <button
          type="submit"
          disabled={loading || !traceId.trim()}
          className="button"
          style={{
            marginTop: 0,
            padding: "8px 16px",
            cursor: loading ? "not-allowed" : "pointer",
          }}
        >
          {loading ? "Loading..." : "Inspect Trace"}
        </button>
      </form>

      {error && (
        <div
          style={{
            background: "#2d1616",
            border: "1px solid #6b2828",
            color: "#f87171",
            padding: "10px 14px",
            borderRadius: "5px",
            fontSize: "13px",
            marginBottom: "16px",
          }}
        >
          {error}
        </div>
      )}

      {trace && (
        <div>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
              gap: "12px",
              padding: "12px 16px",
              background: "#101416",
              borderRadius: "6px",
              border: "1px solid #283032",
              marginBottom: "20px",
            }}
          >
            <div>
              <div
                style={{
                  fontSize: "11px",
                  color: "#9eaeb2",
                  textTransform: "uppercase",
                }}
              >
                Root Service
              </div>
              <div style={{ fontWeight: 600, color: "#c9e6a0" }}>
                {trace.service_name}
              </div>
            </div>
            <div>
              <div
                style={{
                  fontSize: "11px",
                  color: "#9eaeb2",
                  textTransform: "uppercase",
                }}
              >
                Root Operation
              </div>
              <div style={{ fontWeight: 600 }}>{trace.root_operation}</div>
            </div>
            <div>
              <div
                style={{
                  fontSize: "11px",
                  color: "#9eaeb2",
                  textTransform: "uppercase",
                }}
              >
                Duration
              </div>
              <div style={{ fontWeight: 600 }}>
                {trace.duration_ms.toFixed(2)} ms
              </div>
            </div>
            <div>
              <div
                style={{
                  fontSize: "11px",
                  color: "#9eaeb2",
                  textTransform: "uppercase",
                }}
              >
                Spans
              </div>
              <div style={{ fontWeight: 600 }}>
                {trace.span_count} ({trace.error_span_count} errors)
              </div>
            </div>
          </div>

          <h3
            style={{
              fontSize: "13px",
              textTransform: "uppercase",
              letterSpacing: "1px",
              color: "#9eaeb2",
              marginBottom: "12px",
            }}
          >
            Waterfall Timeline
          </h3>

          <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
            {trace.spans.map((span: Span) => {
              const isError =
                span.status_code === "STATUS_CODE_ERROR" ||
                span.status_code === "ERROR" ||
                (typeof span.attributes["http.status_code"] === "number" &&
                  span.attributes["http.status_code"] >= 500);

              const widthPercent = Math.max(
                5,
                Math.min(100, (span.duration_ms / maxDuration) * 100),
              );

              return (
                <div
                  key={span.span_id}
                  style={{
                    background: "#121719",
                    border: "1px solid #283032",
                    borderRadius: "4px",
                    padding: "8px 12px",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      marginBottom: "6px",
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        gap: "8px",
                        alignItems: "center",
                      }}
                    >
                      <span
                        style={{
                          fontSize: "11px",
                          fontFamily: "monospace",
                          color: "#9eaeb2",
                          background: "#1c2225",
                          padding: "2px 6px",
                          borderRadius: "3px",
                        }}
                      >
                        {span.service_name}
                      </span>
                      <strong style={{ fontSize: "13px" }}>{span.name}</strong>
                    </div>

                    <div
                      style={{
                        display: "flex",
                        gap: "10px",
                        alignItems: "center",
                      }}
                    >
                      <span style={{ fontSize: "12px", color: "#9eaeb2" }}>
                        {span.duration_ms.toFixed(2)} ms
                      </span>
                      <span
                        style={{
                          fontSize: "10px",
                          fontWeight: 700,
                          padding: "2px 6px",
                          borderRadius: "3px",
                          background: isError ? "#3d1414" : "#142d1e",
                          color: isError ? "#f87171" : "#a3d9b8",
                          border: `1px solid ${isError ? "#6b2828" : "#285e3a"}`,
                        }}
                      >
                        {isError ? "ERROR" : "OK"}
                      </span>
                    </div>
                  </div>

                  {/* Waterfall bar */}
                  <div
                    style={{
                      width: "100%",
                      height: "6px",
                      background: "#1c2225",
                      borderRadius: "3px",
                      overflow: "hidden",
                    }}
                  >
                    <div
                      style={{
                        width: `${widthPercent}%`,
                        height: "100%",
                        background: isError ? "#ef4444" : "#84cc16",
                        borderRadius: "3px",
                      }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </section>
  );
}
