"use client";

import { useEffect, useState, useCallback } from "react";
import {
  InvestigationRun,
  InvestigationRunDetail,
  ToolExecution,
  startInvestigation,
  getInvestigation,
  getInvestigationEvents,
  listIncidentInvestigations,
  cancelInvestigation,
} from "../../../lib/api";

interface InvestigationPanelProps {
  incidentId: string;
}

export function InvestigationPanel({ incidentId }: InvestigationPanelProps) {
  const [runs, setRuns] = useState<InvestigationRun[]>([]);
  const [activeRun, setActiveRun] = useState<InvestigationRunDetail | null>(
    null,
  );
  const [events, setEvents] = useState<ToolExecution[]>([]);
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchRunDetail = useCallback(async (runId: string) => {
    const [detailRes, eventsRes] = await Promise.all([
      getInvestigation(runId),
      getInvestigationEvents(runId),
    ]);
    if (detailRes.data) {
      setActiveRun(detailRes.data);
    }
    if (eventsRes.data) {
      setEvents(eventsRes.data);
    }
  }, []);

  const refreshHistory = useCallback(async () => {
    const res = await listIncidentInvestigations(incidentId);
    if (res.data) {
      setRuns(res.data);
      if (res.data.length > 0) {
        await fetchRunDetail(res.data[0].id);
      } else {
        setActiveRun(null);
        setEvents([]);
      }
    }
    setLoading(false);
  }, [incidentId, fetchRunDetail]);

  useEffect(() => {
    refreshHistory();
  }, [refreshHistory]);

  // Polling loop when run is in progress
  useEffect(() => {
    if (!activeRun) return;
    const isRunning = [
      "QUEUED",
      "COLLECTING_CONTEXT",
      "INVESTIGATING",
      "VALIDATING",
    ].includes(activeRun.status);

    if (!isRunning) return;

    const interval = setInterval(async () => {
      await fetchRunDetail(activeRun.id);
    }, 2000);

    return () => clearInterval(interval);
  }, [activeRun, fetchRunDetail]);

  const handleStart = async () => {
    setStarting(true);
    setError(null);
    const res = await startInvestigation(incidentId);
    if (res.error) {
      setError(res.error);
    } else if (res.data) {
      await refreshHistory();
    }
    setStarting(false);
  };

  const handleCancel = async () => {
    if (!activeRun) return;
    setCancelling(true);
    await cancelInvestigation(activeRun.id);
    await fetchRunDetail(activeRun.id);
    setCancelling(false);
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "COMPLETE":
        return { bg: "#1b2420", border: "#3a5746", text: "#a3d9b8" };
      case "INCONCLUSIVE":
        return { bg: "#3d2c14", border: "#805c24", text: "#edd098" };
      case "FAILED":
        return { bg: "#471818", border: "#8a2f2f", text: "#f59e9e" };
      case "CANCELLED":
        return { bg: "#22272b", border: "#3a4247", text: "#9eaeb2" };
      default:
        return { bg: "#172733", border: "#2f5c80", text: "#8ec4f5" };
    }
  };

  if (loading) {
    return (
      <div className="panel" style={{ marginTop: "24px" }}>
        <p className="eyebrow">Investigation State</p>
        <h2>AI Incident Investigator</h2>
        <p style={{ color: "#9eaeb2" }}>Loading investigation status...</p>
      </div>
    );
  }

  const statusStyle = activeRun ? getStatusColor(activeRun.status) : null;
  const isRunning = Boolean(
    activeRun &&
    ["QUEUED", "COLLECTING_CONTEXT", "INVESTIGATING", "VALIDATING"].includes(
      activeRun.status,
    ),
  );

  return (
    <div
      style={{
        marginTop: "24px",
        display: "flex",
        flexDirection: "column",
        gap: "24px",
      }}
    >
      {/* Header & Controls Panel */}
      <section aria-labelledby="ai-investigation-title" className="panel">
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-start",
            flexWrap: "wrap",
            gap: "16px",
          }}
        >
          <div>
            <p className="eyebrow">Google ADK Agent &bull; Pinned 2.11.0</p>
            <h2 id="ai-investigation-title" style={{ margin: "4px 0" }}>
              AI Incident Investigator
            </h2>
            <p
              style={{ color: "#9eaeb2", fontSize: "0.9rem", margin: "4px 0" }}
            >
              Deterministic read-only tool gateway querying real Prometheus
              metrics and Loki logs with strict evidence validation.
            </p>
          </div>

          <div style={{ display: "flex", gap: "12px", alignItems: "center" }}>
            {isRunning && (
              <button
                type="button"
                onClick={handleCancel}
                disabled={cancelling}
                className="button"
                style={{
                  background: "#471818",
                  borderColor: "#8a2f2f",
                  color: "#f59e9e",
                  fontSize: "0.85rem",
                  padding: "6px 12px",
                }}
              >
                {cancelling ? "Cancelling..." : "Cancel Run"}
              </button>
            )}

            <button
              type="button"
              onClick={handleStart}
              disabled={starting || isRunning}
              className="button"
              id="start-investigation-btn"
              style={{
                background: isRunning ? "#22272b" : "#214227",
                borderColor: isRunning ? "#3a4247" : "#427d4c",
                color: isRunning ? "#9eaeb2" : "#a9e3b4",
                fontWeight: 600,
                padding: "8px 16px",
              }}
            >
              {starting
                ? "Dispatching..."
                : isRunning
                  ? "Investigation Running..."
                  : "Start AI Investigation"}
            </button>
          </div>
        </div>

        {error && (
          <div
            style={{
              marginTop: "12px",
              padding: "10px 14px",
              background: "#381717",
              border: "1px solid #732a2a",
              borderRadius: "4px",
              color: "#f59e9e",
              fontSize: "0.85rem",
            }}
          >
            {error}
          </div>
        )}

        {/* Active Run Status & Metadata */}
        {activeRun ? (
          <div
            style={{
              marginTop: "16px",
              borderTop: "1px solid #2a3338",
              paddingTop: "16px",
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "12px",
                flexWrap: "wrap",
              }}
            >
              <span
                className="badge"
                id="investigation-status-badge"
                style={{
                  background: statusStyle?.bg,
                  borderColor: statusStyle?.border,
                  color: statusStyle?.text,
                  fontWeight: 600,
                  fontSize: "0.85rem",
                  padding: "4px 10px",
                }}
              >
                STATUS: {activeRun.status}
              </span>

              <span style={{ fontSize: "0.85rem", color: "#9eaeb2" }}>
                Model: <code>{activeRun.model}</code> &bull; Prompt:{" "}
                <code>{activeRun.prompt_version}</code> &bull; Tool Calls:{" "}
                <strong>{activeRun.tool_call_count} / 12</strong>
              </span>

              {runs.length > 1 && (
                <div
                  style={{
                    marginLeft: "auto",
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                  }}
                >
                  <label
                    htmlFor="run-select"
                    style={{ fontSize: "0.8rem", color: "#9eaeb2" }}
                  >
                    Run:
                  </label>
                  <select
                    id="run-select"
                    value={activeRun.id}
                    onChange={(e) => fetchRunDetail(e.target.value)}
                    style={{
                      background: "#12171a",
                      color: "#d0dade",
                      border: "1px solid #36444a",
                      padding: "4px 8px",
                      borderRadius: "4px",
                      fontSize: "0.8rem",
                    }}
                  >
                    {runs.map((r) => (
                      <option key={r.id} value={r.id}>
                        {new Date(r.created_at).toLocaleTimeString()} (
                        {r.status})
                      </option>
                    ))}
                  </select>
                </div>
              )}
            </div>

            {/* Inconclusive or Error Alert */}
            {activeRun.status === "INCONCLUSIVE" && (
              <div
                style={{
                  marginTop: "16px",
                  background: "#261d10",
                  border: "1px solid #63451d",
                  borderRadius: "6px",
                  padding: "14px 18px",
                  color: "#edd098",
                }}
              >
                <h4 style={{ margin: "0 0 6px 0", fontSize: "0.95rem" }}>
                  Inconclusive Result &bull; Missing or Ambiguous Telemetry
                </h4>
                <p
                  style={{
                    margin: "0 0 8px 0",
                    fontSize: "0.85rem",
                    color: "#d6c196",
                  }}
                >
                  The agent did not observe sufficient telemetry signals
                  (elevated 5xx error rate or error logs) to confirm root cause.
                  Per non-negotiable safety rules, hallucinated diagnoses are
                  strictly rejected.
                </p>
                {activeRun.missing_evidence &&
                  activeRun.missing_evidence.length > 0 && (
                    <ul
                      style={{
                        margin: "4px 0",
                        paddingLeft: "20px",
                        fontSize: "0.85rem",
                      }}
                    >
                      {activeRun.missing_evidence.map((item, idx) => (
                        <li key={idx}>{item}</li>
                      ))}
                    </ul>
                  )}
              </div>
            )}

            {/* Diagnosis / Hypotheses */}
            {activeRun.summary && (
              <div style={{ marginTop: "16px" }}>
                <h3
                  style={{
                    fontSize: "1rem",
                    color: "#dce6e8",
                    margin: "0 0 8px 0",
                  }}
                >
                  Summary Diagnosis
                </h3>
                <p
                  style={{
                    margin: 0,
                    color: "#b7c5c9",
                    fontSize: "0.9rem",
                    lineHeight: 1.6,
                  }}
                >
                  {activeRun.summary}
                </p>
              </div>
            )}

            {activeRun.hypotheses && activeRun.hypotheses.length > 0 && (
              <div style={{ marginTop: "16px" }}>
                <h3
                  style={{
                    fontSize: "1rem",
                    color: "#dce6e8",
                    margin: "0 0 10px 0",
                  }}
                >
                  Qualified Hypotheses
                </h3>
                <div
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: "12px",
                  }}
                >
                  {activeRun.hypotheses.map((h) => (
                    <div
                      key={h.id}
                      style={{
                        background: "#141a1d",
                        border: "1px solid #28363b",
                        borderRadius: "6px",
                        padding: "14px",
                      }}
                    >
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: "10px",
                          marginBottom: "8px",
                        }}
                      >
                        <span
                          className="badge"
                          style={{
                            background:
                              h.confidence === "high"
                                ? "#1e3321"
                                : h.confidence === "medium"
                                  ? "#332a18"
                                  : "#22272b",
                            borderColor:
                              h.confidence === "high"
                                ? "#3e6e44"
                                : h.confidence === "medium"
                                  ? "#705c2a"
                                  : "#3b444a",
                            color:
                              h.confidence === "high"
                                ? "#a9e3b4"
                                : h.confidence === "medium"
                                  ? "#ebd29b"
                                  : "#9eaeb2",
                            fontSize: "0.75rem",
                          }}
                        >
                          CONFIDENCE: {h.confidence.toUpperCase()}
                        </span>
                        <strong
                          style={{ color: "#e1eaec", fontSize: "0.95rem" }}
                        >
                          {h.cause}
                        </strong>
                      </div>

                      {h.next_check && (
                        <p
                          style={{
                            margin: "4px 0 8px 0",
                            fontSize: "0.85rem",
                            color: "#9eaeb2",
                          }}
                        >
                          <strong>Next verification:</strong> {h.next_check}
                        </p>
                      )}

                      {/* Supporting Evidence Chips */}
                      {h.supporting_evidence &&
                        h.supporting_evidence.length > 0 && (
                          <div style={{ marginTop: "8px" }}>
                            <span
                              style={{
                                fontSize: "0.8rem",
                                color: "#7f9499",
                                textTransform: "uppercase",
                              }}
                            >
                              Supporting Evidence:
                            </span>
                            <div
                              style={{
                                display: "flex",
                                flexWrap: "wrap",
                                gap: "8px",
                                marginTop: "6px",
                              }}
                            >
                              {h.supporting_evidence.map((ev, i) => (
                                <span
                                  key={i}
                                  style={{
                                    background: "#1b2529",
                                    border: "1px solid #374a52",
                                    borderRadius: "4px",
                                    padding: "4px 8px",
                                    fontSize: "0.8rem",
                                    color: "#a4d4de",
                                  }}
                                >
                                  <code>{ev.evidence_id}</code>: {ev.supports}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div
            style={{ marginTop: "16px", color: "#8a9aa0", fontSize: "0.9rem" }}
          >
            No investigation run exists for this incident yet. Click &quot;Start
            AI Investigation&quot; to execute the Google ADK investigation
            agent.
          </div>
        )}
      </section>

      {/* Evidence Explorer Panel */}
      {activeRun &&
        activeRun.evidence_items &&
        activeRun.evidence_items.length > 0 && (
          <section aria-labelledby="evidence-title" className="panel">
            <p className="eyebrow">Audit &bull; Grounded Citations</p>
            <h2 id="evidence-title">
              Evidence Explorer ({activeRun.evidence_items.length})
            </h2>
            <p
              style={{
                color: "#9eaeb2",
                fontSize: "0.85rem",
                margin: "4px 0 16px 0",
              }}
            >
              Every citation cited by hypotheses resolves to durably persisted
              telemetry captured via the authorized tool gateway.
            </p>

            <div
              style={{ display: "flex", flexDirection: "column", gap: "12px" }}
            >
              {activeRun.evidence_items.map((ev) => (
                <div
                  key={ev.id}
                  id={`evidence-${ev.evidence_id}`}
                  style={{
                    background: "#12181b",
                    border: "1px solid #253338",
                    borderRadius: "6px",
                    padding: "12px 16px",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      flexWrap: "wrap",
                      gap: "8px",
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
                        className="badge"
                        style={{
                          background:
                            ev.source === "metrics"
                              ? "#152a38"
                              : ev.source === "logs"
                                ? "#281e36"
                                : "#262214",
                          borderColor:
                            ev.source === "metrics"
                              ? "#285675"
                              : ev.source === "logs"
                                ? "#593d78"
                                : "#594d28",
                          color:
                            ev.source === "metrics"
                              ? "#8ecbf5"
                              : ev.source === "logs"
                                ? "#c8a5f0"
                                : "#edd28a",
                          padding: "2px 6px",
                          fontSize: "0.75rem",
                        }}
                      >
                        {ev.source.toUpperCase()}
                      </span>
                      <code style={{ color: "#74d795", fontWeight: 600 }}>
                        {ev.evidence_id}
                      </code>
                    </div>
                    <span style={{ fontSize: "0.8rem", color: "#7d9096" }}>
                      Observed: {new Date(ev.observed_at).toLocaleString()}{" "}
                      &bull; Locator: <code>{ev.locator}</code>
                    </span>
                  </div>

                  <pre
                    style={{
                      background: "#0c1012",
                      border: "1px solid #1c272b",
                      padding: "8px 12px",
                      borderRadius: "4px",
                      marginTop: "8px",
                      fontSize: "0.8rem",
                      color: "#c2d2d6",
                      overflowX: "auto",
                      whiteSpace: "pre-wrap",
                    }}
                  >
                    {ev.redacted_snippet}
                  </pre>
                </div>
              ))}
            </div>
          </section>
        )}

      {/* Tool Execution Audit Timeline */}
      {events && events.length > 0 && (
        <section aria-labelledby="tools-title" className="panel">
          <p className="eyebrow">Deterministic Gateway</p>
          <h2 id="tools-title">Tool Execution Audit Log ({events.length})</h2>
          <p
            style={{
              color: "#9eaeb2",
              fontSize: "0.85rem",
              margin: "4px 0 16px 0",
            }}
          >
            Read-only queries executed by the Google ADK runtime within
            authorized scopes and budget bounds.
          </p>

          <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
            {events.map((t) => (
              <div
                key={t.id}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  background: "#12181b",
                  border: "1px solid #232f33",
                  padding: "8px 14px",
                  borderRadius: "4px",
                  fontSize: "0.85rem",
                }}
              >
                <div>
                  <code style={{ color: "#8ecbf5", fontWeight: 600 }}>
                    {t.tool_name}
                  </code>
                  <span
                    style={{
                      color: "#7d9096",
                      marginLeft: "12px",
                      fontSize: "0.8rem",
                    }}
                  >
                    Args: {JSON.stringify(t.arguments)}
                  </span>
                </div>
                <div
                  style={{ display: "flex", gap: "10px", alignItems: "center" }}
                >
                  <span style={{ color: "#7d9096", fontSize: "0.8rem" }}>
                    {t.latency_ms.toFixed(1)} ms
                  </span>
                  <span
                    className="badge"
                    style={{
                      background:
                        t.status === "success" ? "#19261c" : "#361c1c",
                      borderColor:
                        t.status === "success" ? "#315438" : "#6e3333",
                      color: t.status === "success" ? "#8fe39d" : "#f09999",
                      fontSize: "0.75rem",
                      padding: "2px 6px",
                    }}
                  >
                    {t.status.toUpperCase()}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
