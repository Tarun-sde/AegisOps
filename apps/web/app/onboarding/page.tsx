"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { createService, verifyServiceConnection } from "../lib/api";

export default function OnboardingPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [environment, setEnvironment] = useState("");
  const [description, setDescription] = useState("");
  const [connectorUrl, setConnectorUrl] = useState("");
  const [serviceId, setServiceId] = useState<string | null>(null);

  const [savingService, setSavingService] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [verifyResult, setVerifyResult] = useState<{
    success: boolean;
    message: string;
    latency_ms?: number;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleCreateService = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSavingService(true);

    const res = await createService({ name, environment, description });
    if (res.error || !res.data) {
      setError(res.error || "Failed to create service");
      setSavingService(false);
      return;
    }
    setServiceId(res.data.id);
    setSavingService(false);
  };

  const handleVerifyConnector = async () => {
    if (!serviceId) return;
    setVerifying(true);
    setVerifyResult(null);
    setError(null);

    const res = await verifyServiceConnection(serviceId, connectorUrl);
    if (res.error) {
      setError(res.error);
      setVerifying(false);
      return;
    }
    if (res.data) {
      setVerifyResult({
        success: res.data.success,
        message: res.data.message,
        latency_ms: res.data.latency_ms,
      });
    }
    setVerifying(false);
  };

  return (
    <main id="main" style={{ maxWidth: "680px" }}>
      <p className="eyebrow">AegisOps / Workspace Onboarding</p>
      <div className="heading">
        <h1>Connect your first service</h1>
        <span className="badge">Service registration</span>
      </div>
      <p className="intro">
        Configure a monitored service to correlate alerts, distributed traces,
        and AI investigations.
      </p>

      {error && (
        <div
          role="alert"
          style={{
            background: "var(--status-error-bg)",
            border: "1px solid var(--status-error-border)",
            color: "var(--status-error-text)",
            padding: "10px 14px",
            borderRadius: "5px",
            fontSize: "0.875rem",
            marginBottom: "16px",
          }}
        >
          {error}
        </div>
      )}

      <div className="panel">
        <h2 style={{ marginTop: 0 }}>1. Register Service</h2>
        <form onSubmit={handleCreateService}>
          <div style={{ marginBottom: "16px" }}>
            <label
              htmlFor="service-name-input"
              style={{
                display: "block",
                fontSize: "0.875rem",
                marginBottom: "6px",
                color: "var(--text-secondary)",
              }}
            >
              Service Name
            </label>
            <input
              id="service-name-input"
              type="text"
              required
              disabled={!!serviceId}
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. payment-service"
              style={{
                width: "100%",
                padding: "10px 12px",
                background: "var(--bg-surface)",
                border: "1px solid var(--border-default)",
                borderRadius: "5px",
                color: "var(--text-primary)",
                fontSize: "14px",
              }}
            />
          </div>

          <div style={{ marginBottom: "16px" }}>
            <label
              htmlFor="env-select"
              style={{
                display: "block",
                fontSize: "0.875rem",
                marginBottom: "6px",
                color: "var(--text-secondary)",
              }}
            >
              Environment
            </label>
            <select
              id="env-select"
              required
              disabled={!!serviceId}
              value={environment}
              onChange={(e) => setEnvironment(e.target.value)}
              style={{
                width: "100%",
                padding: "10px 12px",
                background: "var(--bg-surface)",
                border: "1px solid var(--border-default)",
                borderRadius: "5px",
                color: "var(--text-primary)",
                fontSize: "14px",
              }}
            >
              <option value="" disabled>
                Select environment
              </option>
              <option value="production">Production</option>
              <option value="staging">Staging</option>
              <option value="development">Development</option>
            </select>
          </div>

          <div style={{ marginBottom: "16px" }}>
            <label
              htmlFor="service-desc-input"
              style={{
                display: "block",
                fontSize: "0.875rem",
                marginBottom: "6px",
                color: "var(--text-secondary)",
              }}
            >
              Description
            </label>
            <input
              id="service-desc-input"
              type="text"
              disabled={!!serviceId}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Operational description"
              style={{
                width: "100%",
                padding: "10px 12px",
                background: "var(--bg-surface)",
                border: "1px solid var(--border-default)",
                borderRadius: "5px",
                color: "var(--text-primary)",
                fontSize: "14px",
              }}
            />
          </div>

          {!serviceId ? (
            <button
              type="submit"
              disabled={savingService}
              className="button"
              style={{
                marginTop: "8px",
                cursor: savingService ? "not-allowed" : "pointer",
              }}
            >
              {savingService ? "Registering..." : "Save Service & Continue"}
            </button>
          ) : (
            <div
              style={{
                color: "var(--status-success-text)",
                fontSize: "0.875rem",
                marginTop: "8px",
              }}
            >
              ✓ Service registered successfully (ID: {serviceId})
            </div>
          )}
        </form>
      </div>

      {serviceId && (
        <div className="panel">
          <h2 style={{ marginTop: 0 }}>2. Verify Healthcheck Connector</h2>
          <p style={{ fontSize: "0.875rem" }}>
            Test endpoint connectivity with server-side SSRF validation
            (protects cloud metadata & private networks).
          </p>

          <div style={{ marginBottom: "16px" }}>
            <label
              htmlFor="connector-url-input"
              style={{
                display: "block",
                fontSize: "0.875rem",
                marginBottom: "6px",
                color: "var(--text-secondary)",
              }}
            >
              Healthcheck URL
            </label>
            <input
              id="connector-url-input"
              type="url"
              value={connectorUrl}
              onChange={(e) => setConnectorUrl(e.target.value)}
              placeholder="https://your-service.example/healthz"
              style={{
                width: "100%",
                padding: "10px 12px",
                background: "var(--bg-surface)",
                border: "1px solid var(--border-default)",
                borderRadius: "5px",
                color: "var(--text-primary)",
                fontSize: "14px",
              }}
            />
          </div>

          <div style={{ display: "flex", gap: "12px", alignItems: "center" }}>
            <button
              type="button"
              onClick={handleVerifyConnector}
              disabled={verifying}
              className="button"
              style={{
                marginTop: "0",
                cursor: verifying ? "not-allowed" : "pointer",
              }}
            >
              {verifying ? "Probing..." : "Test Connector"}
            </button>

            {verifyResult && (
              <span
                style={{
                  color: verifyResult.success
                    ? "var(--status-success-text)"
                    : "var(--status-error-text)",
                  fontSize: "0.875rem",
                }}
              >
                {verifyResult.success ? "✓" : "✗"} {verifyResult.message}
                {verifyResult.latency_ms && ` (${verifyResult.latency_ms}ms)`}
              </span>
            )}
          </div>
        </div>
      )}

      <div
        style={{
          marginTop: "24px",
          display: "flex",
          justifyContent: "flex-end",
        }}
      >
        <button
          type="button"
          onClick={() => router.push("/app")}
          className="button"
          style={{ cursor: "pointer" }}
        >
          Go to Workspace Overview &rarr;
        </button>
      </div>
    </main>
  );
}
