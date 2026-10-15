"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { updateIncidentStatus } from "../../../lib/api";

const VALID_TRANSITIONS: Record<string, string[]> = {
  open: ["acknowledged", "mitigating", "resolved"],
  acknowledged: ["mitigating", "resolved"],
  mitigating: ["resolved"],
  resolved: ["closed", "reopened"],
  closed: ["reopened"],
  reopened: ["acknowledged", "mitigating", "resolved"],
};

const ACTION_LABELS: Record<string, string> = {
  acknowledged: "Acknowledge",
  mitigating: "Mark Mitigating",
  resolved: "Resolve Incident",
  closed: "Close Incident",
  reopened: "Reopen Incident",
};

const STATUS_COLORS: Record<
  string,
  { bg: string; border: string; text: string }
> = {
  open: {
    bg: "var(--status-error-bg)",
    border: "var(--status-error-border)",
    text: "var(--status-error-text)",
  },
  acknowledged: {
    bg: "var(--status-info-bg)",
    border: "var(--status-info-border)",
    text: "var(--status-info-text)",
  },
  mitigating: {
    bg: "var(--status-warning-bg)",
    border: "var(--status-warning-border)",
    text: "var(--status-warning-text)",
  },
  resolved: {
    bg: "var(--bg-surface)",
    border: "var(--border-default)",
    text: "var(--status-success-text)",
  },
  closed: {
    bg: "var(--bg-surface)",
    border: "var(--border-default)",
    text: "var(--text-secondary)",
  },
  reopened: {
    bg: "var(--status-error-bg)",
    border: "var(--status-error-border)",
    text: "var(--status-error-text)",
  },
};

interface LifecycleControlsProps {
  incidentId: string;
  currentStatus: string;
  currentVersion: number;
}

export function LifecycleControls({
  incidentId,
  currentStatus,
  currentVersion,
}: LifecycleControlsProps) {
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const normalizedStatus = currentStatus.toLowerCase();
  const allowedNext = VALID_TRANSITIONS[normalizedStatus] || [];
  const statusTheme = STATUS_COLORS[normalizedStatus] || STATUS_COLORS.open;

  async function handleTransition(targetStatus: string) {
    setSubmitting(true);
    setError(null);
    setSuccessMsg(null);

    const res = await updateIncidentStatus(
      incidentId,
      targetStatus,
      currentVersion,
      reason.trim() || undefined,
    );

    setSubmitting(false);

    if (res.error) {
      setError(res.error);
    } else {
      setSuccessMsg(
        `Incident transitioned to ${targetStatus.toUpperCase()} (v${res.data?.version ?? currentVersion + 1})`,
      );
      setReason("");
      router.refresh();
    }
  }

  return (
    <div
      className="panel"
      style={{ marginTop: "24px", borderColor: statusTheme.border }}
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
          <p className="eyebrow" style={{ margin: 0 }}>
            Incident Lifecycle State Machine
          </p>
          <h2 style={{ margin: "4px 0" }}>
            Current Status:{" "}
            <span style={{ color: statusTheme.text }}>
              {currentStatus.toUpperCase()}
            </span>
          </h2>
          <span
            style={{ fontSize: "0.875rem", color: "var(--text-secondary)" }}
          >
            Optimistic Concurrency: <code>v{currentVersion}</code> &bull;
            Auditable state transitions enforced
          </span>
        </div>

        <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
          {allowedNext.map((target) => (
            <button
              key={target}
              type="button"
              className="button"
              disabled={submitting}
              onClick={() => handleTransition(target)}
              style={{
                fontSize: "0.875rem",
                padding: "8px 14px",
                background: STATUS_COLORS[target]?.bg || "var(--bg-surface)",
                borderColor:
                  STATUS_COLORS[target]?.border || "var(--border-default)",
                color: STATUS_COLORS[target]?.text || "var(--text-primary)",
              }}
            >
              {submitting ? "Updating..." : ACTION_LABELS[target] || target}
            </button>
          ))}
          {allowedNext.length === 0 && (
            <span
              style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}
            >
              Terminal state reached.
            </span>
          )}
        </div>
      </div>

      <div style={{ marginTop: "16px" }}>
        <label
          htmlFor="transition-reason"
          style={{
            display: "block",
            fontSize: "0.875rem",
            color: "var(--text-secondary)",
            marginBottom: "6px",
          }}
        >
          Optional transition justification / operational comment:
        </label>
        <input
          id="transition-reason"
          type="text"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="e.g. Switched payment processor to failover cluster; error rate subsiding."
          style={{
            width: "100%",
            padding: "8px 12px",
            background: "var(--status-info-bg)",
            border: "1px solid var(--border-default)",
            borderRadius: "6px",
            color: "var(--status-info-text)",
            fontSize: "0.9rem",
            boxSizing: "border-box",
          }}
          disabled={submitting}
        />
      </div>

      {error && (
        <div
          style={{
            marginTop: "12px",
            padding: "8px 12px",
            background: "var(--status-error-bg)",
            border: "1px solid var(--status-error-border)",
            borderRadius: "6px",
            color: "var(--status-error-text)",
            fontSize: "0.875rem",
          }}
        >
          <strong>Transition Error:</strong> {error}
        </div>
      )}

      {successMsg && (
        <div
          style={{
            marginTop: "12px",
            padding: "8px 12px",
            background: "var(--bg-surface)",
            border: "1px solid var(--border-default)",
            borderRadius: "6px",
            color: "var(--status-success-text)",
            fontSize: "0.875rem",
          }}
        >
          {successMsg}
        </div>
      )}
    </div>
  );
}
