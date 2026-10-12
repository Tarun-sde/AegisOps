"use client";

import { useEffect, useState, useTransition } from "react";
import {
  executeProposal,
  getProposals,
  getSimulationRunEvents,
  getSimulationRuns,
  getSimulationScenarios,
  resetSimulation,
  startSimulation,
  verifySimulationRecovery,
  type ActionExecution,
  type ActionProposal,
  type SimulationEvent,
  type SimulationRun,
  type SimulationScenario,
} from "../../lib/api";

export default function SimulationLabPage() {
  const [scenarios, setScenarios] = useState<SimulationScenario[]>([]);
  const [runs, setRuns] = useState<SimulationRun[]>([]);
  const [activeRun, setActiveRun] = useState<SimulationRun | null>(null);
  const [runEvents, setRunEvents] = useState<SimulationEvent[]>([]);
  const [proposals, setProposals] = useState<ActionProposal[]>([]);
  const [executions, setExecutions] = useState<Record<string, ActionExecution>>(
    {},
  );

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  async function loadData() {
    setLoading(true);
    setError(null);
    const [scRes, rRes, pRes] = await Promise.all([
      getSimulationScenarios(),
      getSimulationRuns(),
      getProposals(),
    ]);

    if (scRes.error) {
      setError(scRes.error);
    } else if (scRes.data) {
      setScenarios(scRes.data);
    }

    if (rRes.data) {
      setRuns(rRes.data.items);
      const active = rRes.data.items.find((r) => r.status === "ACTIVE") || null;
      setActiveRun(active);
      if (active) {
        const evRes = await getSimulationRunEvents(active.id);
        if (evRes.data) setRunEvents(evRes.data);
      } else {
        setRunEvents([]);
      }
    }

    if (pRes.data) {
      setProposals(pRes.data.items);
    }
    setLoading(false);
  }

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 10000);
    return () => clearInterval(interval);
  }, []);

  function handleStartScenario(scenarioId: string) {
    setActionMessage(null);
    setError(null);
    startTransition(async () => {
      const res = await startSimulation(scenarioId, { environment: "staging" });
      if (res.error) {
        setError(`Failed to activate scenario: ${res.error}`);
      } else if (res.data) {
        setActionMessage(
          `Scenario ${scenarioId} activated successfully. Run ID: ${res.data.id.slice(0, 8)}.`,
        );
        loadData();
      }
    });
  }

  function handleResetRun(runId: string) {
    setActionMessage(null);
    setError(null);
    startTransition(async () => {
      const res = await resetSimulation(runId, "Operator completed test run");
      if (res.error) {
        setError(`Reset failed: ${res.error}`);
      } else if (res.data) {
        setActionMessage(
          `Simulation run ${runId.slice(0, 8)} reset successfully.`,
        );
        loadData();
      }
    });
  }

  function handleVerifyRecovery(runId: string) {
    setActionMessage(null);
    setError(null);
    startTransition(async () => {
      const res = await verifySimulationRecovery(runId);
      if (res.error) {
        setError(`Recovery verification failed: ${res.error}`);
      } else if (res.data) {
        if (res.data.recovered) {
          setActionMessage(
            "Service recovery VERIFIED! Genuine health probe returned healthy and no active faults.",
          );
        } else {
          setError(
            "Service recovery NOT verified. Health probe or background fault still active.",
          );
        }
        loadData();
      }
    });
  }

  function handleExecuteProposal(proposalId: string) {
    setActionMessage(null);
    setError(null);
    startTransition(async () => {
      const res = await executeProposal(proposalId);
      if (res.error) {
        setError(`Remediation execution failed: ${res.error}`);
      } else if (res.data) {
        setActionMessage(
          `Action execution ${res.data.status}! Execution ID: ${res.data.id.slice(0, 8)}. Audit event created.`,
        );
        setExecutions((prev) => ({
          ...prev,
          [proposalId]: res.data as ActionExecution,
        }));
        loadData();
      }
    });
  }

  return (
    <main id="main">
      <div className="eyebrow">Phase 7 Reliability Engineering</div>
      <div className="heading">
        <h1>Incident Simulation Lab & Remediation</h1>
        <span className="badge">Isolated Staging Lab</span>
      </div>
      <p className="intro">
        Exercise genuine failure injection across six real operational
        scenarios. Review evidence-grounded remediation proposals and safely
        execute allowlisted actions in the isolated demo runtime.
      </p>

      {loading && (
        <div
          style={{ color: "#9ca3af", marginBottom: "16px", fontSize: "0.9rem" }}
        >
          Synchronizing simulation state with control plane...
        </div>
      )}

      {actionMessage && (
        <div
          role="status"
          style={{
            padding: "16px 20px",
            marginBottom: "24px",
            background: "#16281e",
            border: "1px solid #336940",
            borderRadius: "8px",
            color: "#a3e6b8",
            fontSize: "0.95rem",
          }}
        >
          {actionMessage}
        </div>
      )}

      {error && (
        <div
          role="alert"
          style={{
            padding: "16px 20px",
            marginBottom: "24px",
            background: "#331616",
            border: "1px solid #772b2b",
            borderRadius: "8px",
            color: "#fca5a5",
            fontSize: "0.95rem",
          }}
        >
          {error}
        </div>
      )}

      {/* ACTIVE SIMULATION BANNER */}
      {activeRun ? (
        <div
          className="panel"
          style={{
            borderColor: "#d97706",
            background: "#1f170a",
            marginBottom: "36px",
          }}
        >
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              flexWrap: "wrap",
              gap: "12px",
            }}
          >
            <div>
              <span
                className="badge"
                style={{ borderColor: "#b45309", color: "#fbbf24" }}
              >
                FAULT ACTIVE · {activeRun.scenario_id}
              </span>
              <h2 style={{ margin: "12px 0 6px 0", color: "#fef3c7" }}>
                Active Simulation Run: {activeRun.id.slice(0, 8)}
              </h2>
              <p style={{ margin: 0, fontSize: "0.9rem", color: "#d1d5db" }}>
                Target Service: <strong>shop-api</strong> (
                {activeRun.environment}) · Expected Cause:{" "}
                <strong>{activeRun.expected_cause}</strong>
              </p>
              <p
                style={{
                  margin: "6px 0 0 0",
                  fontSize: "0.85rem",
                  color: "#9ca3af",
                }}
              >
                Started: {new Date(activeRun.started_at).toLocaleTimeString()} ·
                Expires: {new Date(activeRun.expires_at).toLocaleTimeString()}
              </p>
            </div>
            <div style={{ display: "flex", gap: "12px", flexWrap: "wrap" }}>
              <button
                type="button"
                onClick={() => handleResetRun(activeRun.id)}
                disabled={isPending}
                style={{
                  background: "#dc2626",
                  color: "#fff",
                  border: "none",
                  padding: "10px 18px",
                  borderRadius: "6px",
                  fontWeight: 600,
                  cursor: isPending ? "not-allowed" : "pointer",
                }}
              >
                Reset Fault
              </button>
              <button
                type="button"
                onClick={() => handleVerifyRecovery(activeRun.id)}
                disabled={isPending}
                style={{
                  background: "#059669",
                  color: "#fff",
                  border: "none",
                  padding: "10px 18px",
                  borderRadius: "6px",
                  fontWeight: 600,
                  cursor: isPending ? "not-allowed" : "pointer",
                }}
              >
                Verify Recovery
              </button>
            </div>
          </div>

          {/* ACTIVE RUN TIMELINE */}
          {runEvents.length > 0 && (
            <div
              style={{
                marginTop: "20px",
                borderTop: "1px solid #3d2a0e",
                paddingTop: "16px",
              }}
            >
              <h3
                style={{
                  fontSize: "0.9rem",
                  textTransform: "uppercase",
                  letterSpacing: "1px",
                  color: "#d97706",
                  margin: "0 0 10px 0",
                }}
              >
                Event Timeline
              </h3>
              <div
                style={{ display: "flex", flexDirection: "column", gap: "8px" }}
              >
                {runEvents.map((ev) => (
                  <div
                    key={ev.id}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "12px",
                      fontSize: "0.85rem",
                      background: "#181408",
                      padding: "8px 12px",
                      borderRadius: "4px",
                    }}
                  >
                    <span style={{ color: "#fbbf24", fontFamily: "monospace" }}>
                      {new Date(ev.created_at).toLocaleTimeString()}
                    </span>
                    <span style={{ fontWeight: 600, color: "#fff" }}>
                      {ev.event_type}
                    </span>
                    <span style={{ color: "#9ca3af", marginLeft: "auto" }}>
                      actor: {ev.actor}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      ) : (
        <div
          className="panel"
          style={{
            marginBottom: "36px",
            borderColor: "#1e3a2b",
            background: "#0b1710",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
            <span
              style={{
                width: "10px",
                height: "10px",
                borderRadius: "50%",
                background: "#10b981",
              }}
            />
            <div>
              <h2 style={{ margin: 0, fontSize: "1.1rem", color: "#a7f3d0" }}>
                Simulation Environment Normal
              </h2>
              <p style={{ margin: 0, fontSize: "0.9rem", color: "#6ee7b7" }}>
                All background faults are cleared. Shop-API is operating
                normally on staging.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* SCENARIO CATALOG */}
      <h2>Failure Scenario Catalog (S01–S06)</h2>
      <p style={{ margin: "0 0 20px 0", fontSize: "0.95rem" }}>
        Select a bounded fault injection scenario. Only one scenario may be
        active simultaneously.
      </p>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(340px, 1fr))",
          gap: "20px",
          marginBottom: "48px",
        }}
      >
        {scenarios.map((sc) => {
          const isActive = activeRun?.scenario_id === sc.scenario_id;
          return (
            <div
              key={sc.scenario_id}
              className="panel"
              style={{
                marginTop: 0,
                borderColor: isActive ? "#d97706" : "#2d3739",
                background: isActive ? "#1c160c" : "#171d20",
                display: "flex",
                flexDirection: "column",
                justifyContent: "space-between",
              }}
            >
              <div>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "flex-start",
                    marginBottom: "8px",
                  }}
                >
                  <span className="eyebrow">{sc.scenario_id}</span>
                  <span
                    className="badge"
                    style={{
                      padding: "4px 8px",
                      fontSize: "10px",
                      borderColor:
                        sc.risk_level === "HIGH"
                          ? "#b91c1c"
                          : sc.risk_level === "MEDIUM"
                            ? "#d97706"
                            : "#059669",
                      color:
                        sc.risk_level === "HIGH"
                          ? "#fca5a5"
                          : sc.risk_level === "MEDIUM"
                            ? "#fcd34d"
                            : "#a7f3d0",
                    }}
                  >
                    Risk: {sc.risk_level}
                  </span>
                </div>
                <h3
                  style={{
                    margin: "6px 0 10px 0",
                    fontSize: "1.15rem",
                    color: "#fff",
                  }}
                >
                  {sc.name}
                </h3>
                <p
                  style={{
                    fontSize: "0.9rem",
                    color: "#9ca3af",
                    marginBottom: "14px",
                    lineHeight: "1.5",
                  }}
                >
                  {sc.description}
                </p>

                <div
                  style={{
                    fontSize: "0.8rem",
                    color: "#6b7280",
                    marginBottom: "16px",
                  }}
                >
                  <div>
                    Target: <strong>{sc.affected_service}</strong> (
                    {sc.allowed_environment})
                  </div>
                  <div>
                    Root Cause: <strong>{sc.expected_cause_category}</strong>
                  </div>
                  <div>
                    Signals: {sc.expected_signal_types.slice(0, 3).join(", ")}
                  </div>
                  <div>Max Duration: {sc.maximum_duration_seconds}s</div>
                </div>
              </div>

              <div>
                <button
                  type="button"
                  onClick={() => handleStartScenario(sc.scenario_id)}
                  disabled={isPending || (activeRun !== null && !isActive)}
                  style={{
                    width: "100%",
                    padding: "10px",
                    borderRadius: "6px",
                    border: "none",
                    fontWeight: 600,
                    cursor:
                      (activeRun !== null && !isActive) || isPending
                        ? "not-allowed"
                        : "pointer",
                    background: isActive ? "#f59e0b" : "#2563eb",
                    color: "#fff",
                    opacity: activeRun !== null && !isActive ? 0.4 : 1,
                  }}
                >
                  {isActive ? "Currently Active" : "Activate Scenario"}
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* HUMAN-APPROVED REMEDIATION SECTION */}
      <h2>Remediation Proposal & Sandboxed Execution</h2>
      <p style={{ margin: "0 0 20px 0", fontSize: "0.95rem" }}>
        Review remediation actions proposed by the Google ADK investigator or
        operators. Actions require administrator approval and execute only
        against verified staging targets.
      </p>

      {proposals.length === 0 ? (
        <div className="panel" style={{ textAlign: "center", padding: "36px" }}>
          <p style={{ margin: 0, color: "#6b7280" }}>
            No remediation proposals submitted yet.
          </p>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
          {proposals.map((prop) => {
            const exec = executions[prop.id];
            const isApproved = prop.status === "APPROVED";
            const isExecuting = prop.status === "EXECUTING";
            const isSucceeded = prop.status === "SUCCEEDED";

            return (
              <div
                key={prop.id}
                className="panel"
                style={{
                  marginTop: 0,
                  borderColor: isSucceeded
                    ? "#059669"
                    : isApproved
                      ? "#2563eb"
                      : "#374151",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "flex-start",
                    flexWrap: "wrap",
                    gap: "12px",
                  }}
                >
                  <div>
                    <div
                      style={{
                        display: "flex",
                        gap: "8px",
                        alignItems: "center",
                        marginBottom: "6px",
                      }}
                    >
                      <span className="eyebrow">{prop.action_catalog_id}</span>
                      <span
                        className="badge"
                        style={{
                          padding: "3px 8px",
                          fontSize: "11px",
                          color: isSucceeded
                            ? "#34d399"
                            : isApproved
                              ? "#60a5fa"
                              : "#fbbf24",
                        }}
                      >
                        Status: {prop.status}
                      </span>
                    </div>
                    <h3
                      style={{
                        margin: "4px 0 8px 0",
                        fontSize: "1.1rem",
                        color: "#fff",
                      }}
                    >
                      Target: shop-api ({prop.environment})
                    </h3>
                    <p
                      style={{
                        margin: "0 0 6px 0",
                        fontSize: "0.9rem",
                        color: "#d1d5db",
                      }}
                    >
                      Reason: {prop.reason}
                    </p>
                    <p
                      style={{
                        margin: 0,
                        fontSize: "0.85rem",
                        color: "#9ca3af",
                      }}
                    >
                      Expected Outcome: {prop.expected_outcome}
                    </p>
                  </div>

                  <div
                    style={{
                      display: "flex",
                      gap: "12px",
                      alignItems: "center",
                    }}
                  >
                    {isApproved && (
                      <button
                        type="button"
                        onClick={() => handleExecuteProposal(prop.id)}
                        disabled={isPending}
                        style={{
                          background: "#059669",
                          color: "#fff",
                          border: "none",
                          padding: "10px 18px",
                          borderRadius: "6px",
                          fontWeight: 600,
                          cursor: isPending ? "not-allowed" : "pointer",
                        }}
                      >
                        Execute Remediation
                      </button>
                    )}
                    {isExecuting && (
                      <span
                        className="badge"
                        style={{ borderColor: "#d97706", color: "#fbbf24" }}
                      >
                        Claimed & Executing...
                      </span>
                    )}
                    {isSucceeded && (
                      <span
                        className="badge"
                        style={{ borderColor: "#059669", color: "#34d399" }}
                      >
                        Execution Succeeded
                      </span>
                    )}
                  </div>
                </div>

                <div
                  style={{
                    marginTop: "16px",
                    padding: "12px",
                    background: "#111618",
                    borderRadius: "6px",
                    fontFamily: "monospace",
                    fontSize: "0.8rem",
                    color: "#9ca3af",
                  }}
                >
                  <div>Payload Hash: {prop.parameters_hash}</div>
                  <div>
                    Parameters: {JSON.stringify(prop.immutable_parameters)}
                  </div>
                  {exec && (
                    <div style={{ marginTop: "6px", color: "#34d399" }}>
                      Verified Post-State:{" "}
                      {JSON.stringify(exec.post_execution_state)}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* RECENT RUNS HISTORY */}
      {runs.length > 0 && (
        <div style={{ marginTop: "48px" }}>
          <h2>Recent Simulation History</h2>
          <div
            className="panel"
            style={{ marginTop: "16px", overflowX: "auto" }}
          >
            <table
              style={{
                width: "100%",
                borderCollapse: "collapse",
                fontSize: "0.85rem",
              }}
            >
              <thead>
                <tr
                  style={{
                    textAlign: "left",
                    color: "#9ca3af",
                    borderBottom: "1px solid #374151",
                  }}
                >
                  <th style={{ padding: "8px 12px" }}>Scenario</th>
                  <th style={{ padding: "8px 12px" }}>Run ID</th>
                  <th style={{ padding: "8px 12px" }}>Status</th>
                  <th style={{ padding: "8px 12px" }}>Cleanup</th>
                  <th style={{ padding: "8px 12px" }}>Started</th>
                </tr>
              </thead>
              <tbody>
                {runs.slice(0, 5).map((r) => (
                  <tr key={r.id} style={{ borderBottom: "1px solid #1f2937" }}>
                    <td
                      style={{
                        padding: "8px 12px",
                        fontFamily: "monospace",
                        color: "#fff",
                      }}
                    >
                      {r.scenario_id}
                    </td>
                    <td
                      style={{
                        padding: "8px 12px",
                        fontFamily: "monospace",
                        color: "#9ca3af",
                      }}
                    >
                      {r.id.slice(0, 8)}
                    </td>
                    <td style={{ padding: "8px 12px" }}>
                      <span
                        className="badge"
                        style={{ padding: "2px 6px", fontSize: "10px" }}
                      >
                        {r.status}
                      </span>
                    </td>
                    <td style={{ padding: "8px 12px", color: "#9ca3af" }}>
                      {r.cleanup_status}
                    </td>
                    <td style={{ padding: "8px 12px", color: "#9ca3af" }}>
                      {new Date(r.started_at).toLocaleTimeString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </main>
  );
}
