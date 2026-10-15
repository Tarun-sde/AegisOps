"use client";

import { useEffect, useState, useTransition } from "react";
import { ReviewDialog } from "../../components/review-dialog";
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

    if (dRes.error) setError(dRes.error);
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
      className="ws-content proposals-page"
      id="main"
      style={{ padding: "2rem" }}
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
              color: "var(--foreground, var(--text-primary))",
            }}
          >
            Remediation Proposals & Outbox Automations
          </h1>
          <p
            style={{
              margin: "0.25rem 0 0",
              color: "var(--text-secondary)",
              fontSize: "0.875rem",
            }}
          >
            Human-governed remediation review, exact parameter hashing, and
            transactional outbox observability.
          </p>
        </div>
        <button
          onClick={handleFlushOutbox}
          style={{
            background: "var(--bg-surface-hover)",
            border: "1px solid var(--bg-surface-hover)",
            color: "var(--text-primary)",
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
            color: actionMessage.includes("failed")
              ? "var(--status-error-text)"
              : "var(--status-success-text)",
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
          borderRadius: "var(--radius-lg)",
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
            style={{
              color: "var(--status-warning-text)",
              display: "block",
              fontSize: "0.875rem",
            }}
          >
            Human approval / Separate staging execution
          </strong>
          <p
            style={{
              margin: "0.25rem 0 0",
              fontSize: "0.875rem",
              color: "var(--text-primary)",
            }}
          >
            Proposals are created by deterministic backend policies or suggested
            by verified AI investigations. Approving an action cryptographically
            binds human authorization to the exact SHA-256 payload hash.
            <strong> Approval does not execute an action.</strong> Review and
            execute approved staging actions in the Simulation Lab. Production
            execution is disabled.
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
          <p style={{ color: "var(--text-secondary)" }}>
            Loading remediation proposals...
          </p>
        ) : error ? (
          <p style={{ color: "var(--status-error-text)" }}>Error: {error}</p>
        ) : proposals.length === 0 ? (
          <div
            style={{
              padding: "2rem",
              textAlign: "center",
              background: "var(--bg-surface-hover)",
              borderRadius: "var(--radius-lg)",
              border: "1px dashed var(--bg-surface-hover)",
              color: "var(--text-secondary)",
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
                ? "var(--status-success-text)"
                : isRejected
                  ? "var(--status-error-text)"
                  : isExpired
                    ? "var(--text-secondary)"
                    : "var(--status-warning-text)";

              return (
                <div
                  key={p.id}
                  className="proposal-card"
                  style={{
                    background: "var(--bg-surface-hover)",
                    border: "1px solid var(--bg-surface-hover)",
                    borderRadius: "var(--radius-lg)",
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
                            fontSize: "0.875rem",
                            padding: "0.15rem 0.5rem",
                            borderRadius: "var(--radius-sm)",
                            background: "var(--bg-surface-hover)",
                            color: "var(--text-secondary)",
                          }}
                        >
                          {p.environment}
                        </span>
                        <span
                          style={{
                            fontSize: "0.875rem",
                            padding: "0.15rem 0.5rem",
                            borderRadius: "var(--radius-sm)",
                            fontWeight: 600,
                            background: "var(--bg-surface)",
                            color: statusColor,
                            border: `1px solid ${statusColor}`,
                          }}
                        >
                          {p.status}
                        </span>
                      </div>
                      <p
                        style={{
                          margin: "0.25rem 0 0",
                          color: "var(--text-secondary)",
                          fontSize: "0.875rem",
                        }}
                      >
                        ID: <code style={{ fontSize: "0.875rem" }}>{p.id}</code>{" "}
                        · Expires: {new Date(p.expires_at).toLocaleString()}
                      </p>
                    </div>

                    {isProposed && (
                      <div style={{ display: "flex", gap: "0.5rem" }}>
                        <button
                          onClick={() => handleOpenApprove(p)}
                          style={{
                            background: "var(--status-success-bg)",
                            color: "var(--text-primary)",
                            border: "none",
                            padding: "0.4rem 0.8rem",
                            borderRadius: "var(--radius-sm)",
                            fontSize: "0.875rem",
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
                            color: "var(--status-error-text)",
                            padding: "0.4rem 0.8rem",
                            borderRadius: "var(--radius-sm)",
                            fontSize: "0.875rem",
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
                      gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
                      gap: "1rem",
                      margin: "0.75rem 0",
                      fontSize: "0.875rem",
                    }}
                  >
                    <div>
                      <span style={{ color: "var(--text-secondary)" }}>
                        Reason:
                      </span>
                      <p
                        style={{
                          margin: "0.25rem 0",
                          color: "var(--text-primary)",
                        }}
                      >
                        {p.reason}
                      </p>
                    </div>
                    <div>
                      <span style={{ color: "var(--text-secondary)" }}>
                        Expected Outcome:
                      </span>
                      <p
                        style={{
                          margin: "0.25rem 0",
                          color: "var(--text-primary)",
                        }}
                      >
                        {p.expected_outcome}
                      </p>
                    </div>
                  </div>

                  <div
                    style={{
                      marginTop: "0.5rem",
                      fontSize: "0.875rem",
                      color: "var(--text-secondary)",
                    }}
                  >
                    <span>SHA-256 Hash: </span>
                    <code style={{ color: "var(--status-info-text)" }}>
                      {p.parameters_hash}
                    </code>
                  </div>

                  <details
                    style={{ marginTop: "0.75rem", fontSize: "0.875rem" }}
                  >
                    <summary
                      style={{
                        cursor: "pointer",
                        color: "var(--text-secondary)",
                      }}
                    >
                      View Immutable Parameters JSON
                    </summary>
                    <pre
                      style={{
                        background: "rgba(0, 0, 0, 0.3)",
                        padding: "0.75rem",
                        borderRadius: "var(--radius-sm)",
                        overflowX: "auto",
                        marginTop: "0.5rem",
                        color: "var(--text-primary)",
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
          <p style={{ color: "var(--text-secondary)", fontSize: "0.875rem" }}>
            No outbound deliveries recorded yet.
          </p>
        ) : (
          <div
            style={{
              background: "var(--bg-surface-hover)",
              border: "1px solid var(--bg-surface-hover)",
              borderRadius: "var(--radius-lg)",
              overflowX: "auto",
            }}
          >
            <table
              style={{
                width: "100%",
                borderCollapse: "collapse",
                fontSize: "0.875rem",
                textAlign: "left",
              }}
            >
              <thead>
                <tr
                  style={{
                    borderBottom: "1px solid var(--bg-surface-hover)",
                    background: "var(--bg-surface-hover)",
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
                    ? "var(--status-success-bg)"
                    : isDeadLetter
                      ? "var(--status-error-bg)"
                      : "var(--status-warning-bg)";
                  const statusFg = isDelivered
                    ? "var(--status-success-text)"
                    : isDeadLetter
                      ? "var(--status-error-text)"
                      : "var(--status-warning-text)";

                  return (
                    <tr
                      key={ev.id}
                      style={{
                        borderBottom: "1px solid var(--bg-surface-hover)",
                      }}
                    >
                      <td style={{ padding: "0.75rem 1rem", fontWeight: 500 }}>
                        {ev.event_type}
                      </td>
                      <td
                        style={{
                          padding: "0.75rem 1rem",
                          color: "var(--text-secondary)",
                        }}
                      >
                        <code>{ev.aggregate_id.slice(0, 12)}...</code>
                      </td>
                      <td style={{ padding: "0.75rem 1rem" }}>
                        <span
                          style={{
                            padding: "0.15rem 0.4rem",
                            borderRadius: "var(--radius-sm)",
                            fontSize: "0.875rem",
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
                      <td
                        style={{
                          padding: "0.75rem 1rem",
                          color: "var(--text-secondary)",
                        }}
                      >
                        {ev.delivered_at
                          ? new Date(ev.delivered_at).toLocaleTimeString()
                          : new Date(ev.next_attempt_at).toLocaleTimeString()}
                      </td>
                      <td
                        style={{
                          padding: "0.75rem 1rem",
                          color: ev.last_error_summary
                            ? "var(--status-error-text)"
                            : "var(--text-secondary)",
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
        <ReviewDialog onClose={() => setModalMode(null)} busy={isSubmitting}>
          <div
            style={{
              background: "var(--bg-surface)",
              border: "1px solid var(--bg-surface-hover)",
              borderRadius: "var(--radius-lg)",
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

            <p style={{ fontSize: "0.875rem", color: "var(--text-secondary)" }}>
              Action: <strong>{selectedProposal.action_catalog_id}</strong> on{" "}
              <strong>{selectedProposal.environment}</strong>
            </p>

            <div
              style={{
                margin: "1rem 0",
                fontSize: "0.875rem",
                color: "var(--text-secondary)",
              }}
            >
              <span>Parameters hash: </span>
              <code style={{ color: "var(--status-info-text)" }}>
                {selectedProposal.parameters_hash}
              </code>
            </div>

            <pre>
              {JSON.stringify(selectedProposal.immutable_parameters, null, 2)}
            </pre>
            {actionMessage && <p role="alert">{actionMessage}</p>}
            <label
              htmlFor="approval-comment"
              style={{
                display: "block",
                fontSize: "0.875rem",
                marginBottom: "0.25rem",
                color: "var(--text-primary)",
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
                background: "var(--bg-surface-hover)",
                border: "1px solid var(--bg-surface-hover)",
                borderRadius: "var(--radius-sm)",
                padding: "0.5rem",
                color: "var(--text-primary)",
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
                  border: "1px solid var(--bg-surface-hover)",
                  color: "var(--text-primary)",
                  padding: "0.5rem 1rem",
                  borderRadius: "var(--radius-sm)",
                  cursor: "pointer",
                }}
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmAction}
                disabled={isSubmitting}
                style={{
                  background:
                    modalMode === "approve"
                      ? "var(--status-success-bg)"
                      : "var(--status-error-bg)",
                  border: "none",
                  color: "var(--text-primary)",
                  padding: "0.5rem 1rem",
                  borderRadius: "var(--radius-sm)",
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
        </ReviewDialog>
      )}
    </main>
  );
}
