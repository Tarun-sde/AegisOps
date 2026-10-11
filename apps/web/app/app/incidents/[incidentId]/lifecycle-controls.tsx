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

const STATUS_COLORS: Record<string, { bg: string; border: string; text: string }> = {
  open: { bg: "#471818", border: "#8a2f2f", text: "#f59e9e" },
  acknowledged: { bg: "#232b38", border: "#3b5270", text: "#a4c2e6" },
  mitigating: { bg: "#3d2c14", border: "#805c24", text: "#edd098" },
  resolved: { bg: "#1b2420", border: "#3a5746", text: "#a3d9b8" },
  closed: { bg: "#1f2328", border: "#3d444d", text: "#8b949e" },
  reopened: { bg: "#3b1e2b", border: "#7a2a4b", text: "#f29ec2" },
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
      reason.trim() || undefined
    );

    setSubmitting(false);

    if (res.error) {
      setError(res.error);
    } else {
      setSuccessMsg(`Incident transitioned to ${targetStatus.toUpperCase()} (v${res.data?.version ?? currentVersion + 1})`);
      setReason("");
      router.refresh();
    }
  }

  return (
    <div className="panel" style={{ marginTop: "24px", borderColor: statusTheme.border }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "12px" }}>
        <div>
          <p className="eyebrow" style={{ margin: 0 }}>Incident Lifecycle State Machine</p>
          <h2 style={{ margin: "4px 0" }}>Current Status: <span style={{ color: statusTheme.text }}>{currentStatus.toUpperCase()}</span></h2>
          <span style={{ fontSize: "0.85rem", color: "#8b949e" }}>
            Optimistic Concurrency: <code>v{currentVersion}</code> &bull; Auditable state transitions enforced
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
                fontSize: "0.85rem",
                padding: "8px 14px",
                borderColor: STATUS_COLORS[target]?.border || "#506047",
                color: STATUS_COLORS[target]?.text || "#e1e4ea",
              }}
            >
              {submitting ? "Updating..." : (ACTION_LABELS[target] || target)}
            </button>
          ))}
          {allowedNext.length === 0 && (
            <span style={{ color: "#8b949e", fontSize: "0.9rem" }}>Terminal state reached.</span>
          )}
        </div>
      </div>

      <div style={{ marginTop: "16px" }}>
        <label htmlFor="transition-reason" style={{ display: "block", fontSize: "0.85rem", color: "#8b949e", marginBottom: "6px" }}>
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
            background: "#0d1117",
            border: "1px solid #30363d",
            borderRadius: "6px",
            color: "#e6edf3",
            fontSize: "0.9rem",
            boxSizing: "border-box",
          }}
          disabled={submitting}
        />
      </div>

      {error && (
        <div style={{ marginTop: "12px", padding: "8px 12px", background: "#3b1e22", border: "1px solid #8a2f2f", borderRadius: "6px", color: "#f85149", fontSize: "0.85rem" }}>
          <strong>Transition Error:</strong> {error}
        </div>
      )}

      {successMsg && (
        <div style={{ marginTop: "12px", padding: "8px 12px", background: "#1b2a20", border: "1px solid #3a5746", borderRadius: "6px", color: "#7ee787", fontSize: "0.85rem" }}>
          {successMsg}
        </div>
      )}
    </div>
  );
}
