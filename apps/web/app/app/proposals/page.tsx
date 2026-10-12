"use client";

import { useEffect, useState, useTransition } from "react";
import {
  approveProposal,
  getOutboxDeliveries,
  getProposals,
  rejectProposal,
  triggerOutboxDispatch,
  type ActionProposal,
  type OutboxEvent,
} from "../../lib/api";

export default function ProposalsPage() {
  const [proposals, setProposals] = useState<ActionProposal[]>([]);
  const [deliveries, setDeliveries] = useState<OutboxEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  // Modal / Action state
  const [selectedProposal, setSelectedProposal] =
    useState<ActionProposal | null>(null);
  const [approvalComment, setApprovalComment] = useState("");
  const [isSubmitting, startTransition] = useTransition();
  const [modalMode, setModalMode] = useState<"approve" | "reject" | null>(null);

  async function loadData() {
    setLoading(true);
    setError(null);
    const [pRes, dRes] = await Promise.all([
      getProposals(),
      getOutboxDeliveries(),
    ]);

    if (pRes.error) {
      setError(pRes.error);
    } else if (pRes.data) {
      setProposals(pRes.data.items);
    }

    if (dRes.data) {
      setDeliveries(dRes.data.items);
    }
    setLoading(false);
  }

  useEffect(() => {
    loadData();
  }, []);

  function handleOpenApprove(proposal: ActionProposal) {
    setSelectedProposal(proposal);
    setApprovalComment("");
    setModalMode("approve");
    setActionMessage(null);
  }

  function handleOpenReject(proposal: ActionProposal) {
    setSelectedProposal(proposal);
    setApprovalComment("");
    setModalMode("reject");
    setActionMessage(null);
  }

  function handleConfirmAction() {
    if (!selectedProposal || !modalMode) return;

    startTransition(async () => {
      if (modalMode === "approve") {
        const res = await approveProposal(
          selectedProposal.id,
          selectedProposal.parameters_hash,
          approvalComment,
        );
        if (res.error) {
          setActionMessage(`Approval failed: ${res.error}`);
        } else {
          setActionMessage(
            `Proposal ${selectedProposal.id.slice(0, 8)} approved successfully. Immutable hash verified.`,
          );
          setModalMode(null);
          loadData();
        }
      } else {
        const res = await rejectProposal(selectedProposal.id, approvalComment);
        if (res.error) {
          setActionMessage(`Rejection failed: ${res.error}`);
        } else {
          setActionMessage(
            `Proposal ${selectedProposal.id.slice(0, 8)} rejected.`,
          );
          setModalMode(null);
          loadData();
        }
      }
    });
  }

  async function handleFlushOutbox() {
    setActionMessage("Triggering outbox event dispatch...");
    const res = await triggerOutboxDispatch();
    if (res.error) {
      setActionMessage(`Outbox dispatch failed: ${res.error}`);
    } else {
      setActionMessage(
        `Outbox dispatch completed: claimed=${res.data?.claimed ?? 0}, delivered=${res.data?.delivered ?? 0}, retried=${res.data?.retry_scheduled ?? 0}, dead-lettered=${res.data?.dead_lettered ?? 0}`,
      );
      loadData();
    }
  }

  return (
    <main
      id="main"
      style={{ padding: "2rem", maxWidth: "1200px", margin: "0 auto" }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "1.5rem",
        }}
      >
        <div>
          <h1
            style={{
              fontSize: "1.75rem",
              fontWeight: 700,
              margin: 0,
              color: "var(--foreground, #fff)",
            }}
          >
            Remediation Proposals & Outbox Automations
          </h1>
          <p
            style={{
              margin: "0.25rem 0 0",
              color: "#888",
              fontSize: "0.875rem",
            }}
          >
            Phase 6 human-governed remediation review, exact parameter hashing,
            and transactional outbox observability.
          </p>
        </div>
        <button
          onClick={handleFlushOutbox}
          style={{
            background: "rgba(255, 255, 255, 0.08)",
            border: "1px solid rgba(255, 255, 255, 0.2)",
            color: "#fff",
            padding: "0.5rem 1rem",
            borderRadius: "6px",
            fontSize: "0.875rem",
            cursor: "pointer",
            fontWeight: 500,
          }}
        >
          Flush Outbox Events
        </button>
      </div>

      {actionMessage && (
        <div
          style={{
            padding: "0.75rem 1rem",
            marginBottom: "1rem",
            borderRadius: "6px",
            background: actionMessage.includes("failed")
              ? "rgba(239, 68, 68, 0.15)"
              : "rgba(16, 185, 129, 0.15)",
            border: `1px solid ${actionMessage.includes("failed") ? "rgba(239, 68, 68, 0.4)" : "rgba(16, 185, 129, 0.4)"}`,
            color: actionMessage.includes("failed") ? "#fca5a5" : "#6ee7b7",
            fontSize: "0.875rem",
          }}
        >
          {actionMessage}
        </div>
      )}

      {/* Security Scope Banner */}
      <div
        style={{
          background: "rgba(245, 158, 11, 0.08)",
          border: "1px solid rgba(245, 158, 11, 0.3)",
          borderRadius: "8px",
          padding: "1rem",
          marginBottom: "2rem",
          display: "flex",
          gap: "1rem",
          alignItems: "flex-start",
        }}
      >
        <span style={{ fontSize: "1.25rem" }}>🛡️</span>
        <div>
          <strong
            style={{ color: "#fcd34d", display: "block", fontSize: "0.875rem" }}
          >
            Phase 6 Governance & Non-Execution Invariant
          </strong>
          <p
            style={{
              margin: "0.25rem 0 0",
              fontSize: "0.8125rem",
              color: "#d1d5db",
            }}
          >
            Proposals are created by deterministic backend policies or suggested
            by verified AI investigations. Approving an action cryptographically
            binds human authorization to the exact SHA-256 payload hash.
            <strong>
              {" "}
              In Phase 6, zero remediation actions are executed.
            </strong>{" "}
            Execution is deferred to the Phase 7 security gate.
          </p>
        </div>
      </div>

      {/* Proposals Section */}
      <section style={{ marginBottom: "3rem" }}>
        <h2
          style={{ fontSize: "1.25rem", fontWeight: 600, marginBottom: "1rem" }}
        >
          Action Proposals ({proposals.length})
        </h2>

        {loading ? (
          <p style={{ color: "#888" }}>Loading remediation proposals...</p>
        ) : error ? (
          <p style={{ color: "#f87171" }}>Error: {error}</p>
        ) : proposals.length === 0 ? (
          <div
            style={{
              padding: "2rem",
              textAlign: "center",
              background: "rgba(255, 255, 255, 0.02)",
              borderRadius: "8px",
              border: "1px dashed rgba(255, 255, 255, 0.1)",
              color: "#888",
            }}
          >
            No remediation proposals created yet. Proposals appear when an
            investigation suggests an allowed catalog action.
          </div>
        ) : (
          <div style={{ display: "grid", gap: "1rem" }}>
            {proposals.map((p) => {
              const isProposed = p.status === "PROPOSED";
              const isApproved = p.status === "APPROVED";
              const isRejected = p.status === "REJECTED";
              const isExpired = p.status === "EXPIRED";

              const statusColor = isApproved
                ? "#10b981"
                : isRejected
                  ? "#ef4444"
                  : isExpired
                    ? "#6b7280"
                    : "#f59e0b";

              return (
                <div
                  key={p.id}
                  style={{
                    background: "rgba(255, 255, 255, 0.03)",
                    border: "1px solid rgba(255, 255, 255, 0.08)",
                    borderRadius: "8px",
                    padding: "1.25rem",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "flex-start",
                      marginBottom: "0.75rem",
                    }}
                  >
                    <div>
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: "0.5rem",
                        }}
                      >
                        <span style={{ fontWeight: 600, fontSize: "1rem" }}>
                          {p.action_catalog_id}
                        </span>
                        <span
                          style={{
                            fontSize: "0.75rem",
                            padding: "0.15rem 0.5rem",
                            borderRadius: "4px",
                            background: "rgba(255, 255, 255, 0.08)",
                            color: "#9ca3af",
                          }}
                        >
                          {p.environment}
                        </span>
                        <span
                          style={{
                            fontSize: "0.75rem",
                            padding: "0.15rem 0.5rem",
                            borderRadius: "4px",
                            fontWeight: 600,
                            background: `${statusColor}22`,
                            color: statusColor,
                            border: `1px solid ${statusColor}44`,
                          }}
                        >
                          {p.status}
                        </span>
                      </div>
                      <p
                        style={{
                          margin: "0.25rem 0 0",
                          color: "#9ca3af",
                          fontSize: "0.8125rem",
                        }}
                      >
                        ID: <code style={{ fontSize: "0.75rem" }}>{p.id}</code>{" "}
                        · Expires: {new Date(p.expires_at).toLocaleString()}
                      </p>
                    </div>

                    {isProposed && (
                      <div style={{ display: "flex", gap: "0.5rem" }}>
                        <button
                          onClick={() => handleOpenApprove(p)}
                          style={{
                            background: "#059669",
                            color: "#fff",
                            border: "none",
                            padding: "0.4rem 0.8rem",
                            borderRadius: "4px",
                            fontSize: "0.8125rem",
                            fontWeight: 600,
                            cursor: "pointer",
                          }}
                        >
                          Approve
                        </button>
                        <button
                          onClick={() => handleOpenReject(p)}
                          style={{
                            background: "rgba(239, 68, 68, 0.2)",
                            border: "1px solid rgba(239, 68, 68, 0.4)",
                            color: "#fca5a5",
                            padding: "0.4rem 0.8rem",
                            borderRadius: "4px",
                            fontSize: "0.8125rem",
                            fontWeight: 500,
                            cursor: "pointer",
                          }}
                        >
                          Reject
                        </button>
                      </div>
                    )}
                  </div>

                  <div
                    style={{
                      display: "grid",
                      gridTemplateColumns: "1fr 1fr",
                      gap: "1rem",
                      margin: "0.75rem 0",
                      fontSize: "0.8125rem",
                    }}
                  >
                    <div>
                      <span style={{ color: "#6b7280" }}>Reason:</span>
                      <p style={{ margin: "0.25rem 0", color: "#e5e7eb" }}>
                        {p.reason}
                      </p>
                    </div>
                    <div>
                      <span style={{ color: "#6b7280" }}>
                        Expected Outcome:
                      </span>
                      <p style={{ margin: "0.25rem 0", color: "#e5e7eb" }}>
                        {p.expected_outcome}
                      </p>
                    </div>
                  </div>

                  <div
                    style={{
                      marginTop: "0.5rem",
                      fontSize: "0.75rem",
                      color: "#6b7280",
                    }}
                  >
                    <span>SHA-256 Hash: </span>
                    <code style={{ color: "#93c5fd" }}>
                      {p.parameters_hash}
                    </code>
                  </div>

                  <details
                    style={{ marginTop: "0.75rem", fontSize: "0.75rem" }}
                  >
                    <summary style={{ cursor: "pointer", color: "#9ca3af" }}>
                      View Immutable Parameters JSON
                    </summary>
                    <pre
                      style={{
                        background: "rgba(0, 0, 0, 0.3)",
                        padding: "0.75rem",
                        borderRadius: "4px",
                        overflowX: "auto",
                        marginTop: "0.5rem",
                        color: "#d1d5db",
                      }}
                    >
                      {JSON.stringify(p.immutable_parameters, null, 2)}
                    </pre>
                  </details>
                </div>
              );
            })}
          </div>
        )}
      </section>

      {/* Outbox Deliveries Observability Feed */}
      <section>
        <h2
          style={{ fontSize: "1.25rem", fontWeight: 600, marginBottom: "1rem" }}
        >
          Transactional Outbox Deliveries ({deliveries.length})
        </h2>

        {deliveries.length === 0 ? (
          <p style={{ color: "#888", fontSize: "0.875rem" }}>
            No outbound deliveries recorded yet.
          </p>
        ) : (
          <div
            style={{
              background: "rgba(255, 255, 255, 0.02)",
              border: "1px solid rgba(255, 255, 255, 0.08)",
              borderRadius: "8px",
              overflowX: "auto",
            }}
          >
            <table
              style={{
                width: "100%",
                borderCollapse: "collapse",
                fontSize: "0.8125rem",
                textAlign: "left",
              }}
            >
              <thead>
                <tr
                  style={{
                    borderBottom: "1px solid rgba(255, 255, 255, 0.1)",
                    background: "rgba(255, 255, 255, 0.03)",
                  }}
                >
                  <th style={{ padding: "0.75rem 1rem" }}>Event Type</th>
                  <th style={{ padding: "0.75rem 1rem" }}>Aggregate ID</th>
                  <th style={{ padding: "0.75rem 1rem" }}>Status</th>
                  <th style={{ padding: "0.75rem 1rem" }}>Attempts</th>
                  <th style={{ padding: "0.75rem 1rem" }}>
                    Next / Delivered At
                  </th>
                  <th style={{ padding: "0.75rem 1rem" }}>Last Error</th>
                </tr>
              </thead>
              <tbody>
                {deliveries.map((ev) => {
                  const isDelivered = ev.status === "DELIVERED";
                  const isDeadLetter = ev.status === "DEAD_LETTERED";
                  const statusBg = isDelivered
                    ? "#10b98122"
                    : isDeadLetter
                      ? "#ef444422"
                      : "#f59e0b22";
                  const statusFg = isDelivered
                    ? "#34d399"
                    : isDeadLetter
                      ? "#f87171"
                      : "#fbbf24";

                  return (
                    <tr
                      key={ev.id}
                      style={{
                        borderBottom: "1px solid rgba(255, 255, 255, 0.05)",
                      }}
                    >
                      <td style={{ padding: "0.75rem 1rem", fontWeight: 500 }}>
                        {ev.event_type}
                      </td>
                      <td style={{ padding: "0.75rem 1rem", color: "#9ca3af" }}>
                        <code>{ev.aggregate_id.slice(0, 12)}...</code>
                      </td>
                      <td style={{ padding: "0.75rem 1rem" }}>
                        <span
                          style={{
                            padding: "0.15rem 0.4rem",
                            borderRadius: "4px",
                            fontSize: "0.75rem",
                            fontWeight: 600,
                            background: statusBg,
                            color: statusFg,
                          }}
                        >
                          {ev.status}
                        </span>
                      </td>
                      <td style={{ padding: "0.75rem 1rem" }}>
                        {ev.attempt_count} / {ev.max_attempts}
                      </td>
                      <td style={{ padding: "0.75rem 1rem", color: "#9ca3af" }}>
                        {ev.delivered_at
                          ? new Date(ev.delivered_at).toLocaleTimeString()
                          : new Date(ev.next_attempt_at).toLocaleTimeString()}
                      </td>
                      <td
                        style={{
                          padding: "0.75rem 1rem",
                          color: ev.last_error_summary ? "#fca5a5" : "#6b7280",
                        }}
                      >
                        {ev.last_error_summary
                          ? ev.last_error_summary.slice(0, 50) + "..."
                          : "—"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Confirmation Modal */}
      {modalMode && selectedProposal && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0, 0, 0, 0.7)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 100,
          }}
        >
          <div
            style={{
              background: "#18181b",
              border: "1px solid rgba(255, 255, 255, 0.15)",
              borderRadius: "8px",
              padding: "1.5rem",
              width: "100%",
              maxWidth: "500px",
            }}
          >
            <h3 style={{ fontSize: "1.125rem", fontWeight: 600, marginTop: 0 }}>
              {modalMode === "approve"
                ? "Confirm Remediation Approval"
                : "Reject Remediation Proposal"}
            </h3>

            <p style={{ fontSize: "0.875rem", color: "#9ca3af" }}>
              Action: <strong>{selectedProposal.action_catalog_id}</strong> on{" "}
              <strong>{selectedProposal.environment}</strong>
            </p>

            <div
              style={{
                margin: "1rem 0",
                fontSize: "0.75rem",
                color: "#6b7280",
              }}
            >
              <span>Verified Hash: </span>
              <code style={{ color: "#93c5fd" }}>
                {selectedProposal.parameters_hash.slice(0, 32)}...
              </code>
            </div>

            <label
              htmlFor="approval-comment"
              style={{
                display: "block",
                fontSize: "0.8125rem",
                marginBottom: "0.25rem",
                color: "#d1d5db",
              }}
            >
              Review Comment (Optional):
            </label>
            <textarea
              id="approval-comment"
              value={approvalComment}
              onChange={(e) => setApprovalComment(e.target.value)}
              placeholder="e.g. Approved following pool metric verification"
              rows={3}

              style={{
                width: "100%",
                background: "rgba(255, 255, 255, 0.05)",
                border: "1px solid rgba(255, 255, 255, 0.2)",
                borderRadius: "4px",
                padding: "0.5rem",
                color: "#fff",
                fontSize: "0.875rem",
                marginBottom: "1.5rem",
              }}
            />

            <div
              style={{
                display: "flex",
                justifyContent: "flex-end",
                gap: "0.75rem",
              }}
            >
              <button
                onClick={() => setModalMode(null)}
                disabled={isSubmitting}
                style={{
                  background: "transparent",
                  border: "1px solid rgba(255, 255, 255, 0.2)",
                  color: "#d1d5db",
                  padding: "0.5rem 1rem",
                  borderRadius: "4px",
                  cursor: "pointer",
                }}
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmAction}
                disabled={isSubmitting}
                style={{
                  background: modalMode === "approve" ? "#059669" : "#dc2626",
                  border: "none",
                  color: "#fff",
                  padding: "0.5rem 1rem",
                  borderRadius: "4px",
                  fontWeight: 600,
                  cursor: "pointer",
                }}
              >
                {isSubmitting
                  ? "Submitting..."
                  : modalMode === "approve"
                    ? "Authorize Approval"
                    : "Confirm Rejection"}
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
