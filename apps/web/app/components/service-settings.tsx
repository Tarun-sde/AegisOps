"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import {
  type Service,
  type ServiceHealthObservation,
  updateService,
  verifyServiceConnection,
  getServiceHealthObservations,
} from "../lib/api";
import { HealthStatus } from "./project-visuals";

const utc = (value?: string | null) => {
  if (!value) return "Never";
  try {
    return (
      new Date(value).toISOString().replace("T", " ").slice(0, 19) + " UTC"
    );
  } catch {
    return value;
  }
};

export function ServiceSettings({ service }: { service: Service }) {
  const router = useRouter();

  // Connection and monitoring fields
  const [healthcheckUrl, setHealthcheckUrl] = useState(
    service.healthcheck_url || "",
  );
  const [isMonitored, setIsMonitored] = useState(
    service.is_monitored !== false,
  );
  const [intervalSeconds, setIntervalSeconds] = useState(
    service.monitoring_interval_seconds || 60,
  );

  // Metadata fields
  const [name, setName] = useState(service.name);
  const [environment, setEnvironment] = useState(service.environment);
  const [description, setDescription] = useState(service.description || "");
  const [githubRepo, setGithubRepo] = useState(service.github_repo || "");
  const [currentVersion, setCurrentVersion] = useState(
    service.current_version || "",
  );

  // Operation states
  const [saving, setSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState<{
    success: boolean;
    text: string;
  } | null>(null);

  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{
    success: boolean;
    message: string;
    status_code?: number;
    latency_ms?: number;
  } | null>(null);

  // Historical observations
  const [observations, setObservations] = useState<ServiceHealthObservation[]>(
    [],
  );
  const [loadingObservations, setLoadingObservations] = useState(true);

  const refreshObservations = async () => {
    setLoadingObservations(true);
    const res = await getServiceHealthObservations(service.id, 15);
    if (res.data) {
      setObservations(res.data);
    }
    setLoadingObservations(false);
  };

  useEffect(() => {
    void refreshObservations();
  }, [service.id]);

  const handleTestConnection = async () => {
    if (!healthcheckUrl.trim()) {
      setTestResult({
        success: false,
        message: "Please enter a valid HTTP/HTTPS URL before testing.",
      });
      return;
    }
    setTesting(true);
    setTestResult(null);
    setSaveMessage(null);

    const res = await verifyServiceConnection(
      service.id,
      healthcheckUrl.trim(),
    );
    setTesting(false);

    if (res.error) {
      setTestResult({
        success: false,
        message: res.error,
      });
    } else if (res.data) {
      setTestResult({
        success: res.data.success,
        message: res.data.message,
        status_code: res.data.status_code,
        latency_ms: res.data.latency_ms,
      });
      // Refresh observations and parent page context
      void refreshObservations();
      router.refresh();
    }
  };

  const handleSaveSettings = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setSaveMessage(null);

    const res = await updateService(service.id, {
      name: name.trim(),
      environment,
      description: description.trim() ? description.trim() : null,
      github_repo: githubRepo.trim() ? githubRepo.trim() : null,
      current_version: currentVersion.trim() ? currentVersion.trim() : null,
      healthcheck_url: healthcheckUrl.trim() ? healthcheckUrl.trim() : null,
      is_monitored: isMonitored,
      monitoring_interval_seconds: Number(intervalSeconds),
    });

    setSaving(false);
    if (res.error) {
      setSaveMessage({
        success: false,
        text: res.error,
      });
    } else {
      setSaveMessage({
        success: true,
        text: "Application settings updated successfully.",
      });
      router.refresh();
      void refreshObservations();
    }
  };

  return (
    <div className="application-settings-grid">
      {saveMessage && (
        <div
          role="status"
          className={`an-alert ${saveMessage.success ? "an-alert-success" : "an-alert-error"}`}
          style={{ marginBottom: "1.5rem" }}
        >
          <strong>{saveMessage.success ? "Saved" : "Error"}</strong>
          <p>{saveMessage.text}</p>
        </div>
      )}

      {/* 1. Connection & Continuous Monitoring Panel */}
      <section
        className="an-panel application-section"
        aria-labelledby="conn-settings-title"
      >
        <div className="an-section-heading">
          <div>
            <span className="an-eyebrow">Connection & Probing</span>
            <h2 id="conn-settings-title">Healthcheck Endpoint & Monitoring</h2>
            <p>
              Configure the external application URL for scheduled probing and
              real-time connectivity testing.
            </p>
          </div>
          <div>
            <HealthStatus health={service.monitoring_status || "unknown"} />
          </div>
        </div>

        <form onSubmit={handleSaveSettings} className="application-form">
          <label htmlFor="service-healthcheck-input">
            Healthcheck URL
            <span>(Public HTTP/HTTPS endpoint probed by AegisOps)</span>
            <input
              id="service-healthcheck-input"
              type="url"
              value={healthcheckUrl}
              onChange={(e) => setHealthcheckUrl(e.target.value)}
              placeholder="https://ironlog-backend-jrqs.onrender.com/api/health"
            />
          </label>

          <div
            style={{
              display: "flex",
              gap: "1rem",
              alignItems: "center",
              marginTop: "0.5rem",
            }}
          >
            <button
              type="button"
              className="ws-button"
              disabled={testing || !healthcheckUrl.trim()}
              onClick={handleTestConnection}
            >
              {testing ? "Testing Probe…" : "Test Connection Now"}
            </button>
            {service.healthcheck_url && (
              <a
                href={service.healthcheck_url}
                target="_blank"
                rel="noopener noreferrer"
                className="ws-button"
              >
                Open in Browser ↗
              </a>
            )}
          </div>

          {testResult && (
            <div
              role="status"
              className="an-alert"
              style={{
                marginTop: "1rem",
                borderColor: testResult.success
                  ? "var(--ws-green)"
                  : "var(--red)",
              }}
            >
              <div>
                <strong>
                  {testResult.success ? "Probe Succeeded" : "Probe Failed"}
                  {testResult.status_code
                    ? ` (HTTP ${testResult.status_code})`
                    : ""}
                </strong>
                <p>
                  {testResult.message}
                  {testResult.latency_ms != null
                    ? ` — Latency: ${testResult.latency_ms} ms`
                    : ""}
                </p>
              </div>
            </div>
          )}

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
              gap: "1.5rem",
              marginTop: "1.5rem",
              paddingTop: "1.5rem",
              borderTop: "1px solid var(--ws-border, rgba(255,255,255,0.08))",
            }}
          >
            <label
              style={{
                display: "flex",
                alignItems: "center",
                gap: "0.75rem",
                cursor: "pointer",
              }}
            >
              <input
                type="checkbox"
                checked={isMonitored}
                onChange={(e) => setIsMonitored(e.target.checked)}
                style={{ width: "18px", height: "18px" }}
              />
              <span>Enable Scheduled Continuous Probing</span>
            </label>

            <label htmlFor="service-interval-select">
              Probe Interval
              <select
                id="service-interval-select"
                value={intervalSeconds}
                onChange={(e) => setIntervalSeconds(Number(e.target.value))}
              >
                <option value={15}>Every 15 seconds (High frequency)</option>
                <option value={30}>Every 30 seconds</option>
                <option value={60}>Every 60 seconds (Standard)</option>
                <option value={120}>Every 2 minutes</option>
                <option value={300}>Every 5 minutes</option>
              </select>
            </label>
          </div>

          {/* Diagnostic status readout */}
          <div
            className="application-connect-note"
            style={{
              marginTop: "1.5rem",
              background: "rgba(255,255,255,0.02)",
            }}
          >
            <span className="an-eyebrow">Observed Connection State</span>
            <ul
              style={{
                listStyle: "none",
                padding: 0,
                margin: "0.5rem 0 0 0",
                fontSize: "14px",
              }}
            >
              <li>
                <strong>Monitoring status: </strong>
                <span className="mono">
                  {service.monitoring_status || "unknown"}
                </span>
              </li>
              <li>
                <strong>Last verified at: </strong>
                <span>{utc(service.last_verified_at)}</span>
              </li>
              <li>
                <strong>Last successful probe: </strong>
                <span>{utc(service.last_success_at)}</span>
              </li>
              <li>
                <strong>Last probe latency: </strong>
                <span>
                  {service.last_probe_latency_ms
                    ? `${service.last_probe_latency_ms} ms`
                    : "None"}
                </span>
              </li>
              <li>
                <strong>Last probe status: </strong>
                <span>
                  {service.last_probe_status_code
                    ? `HTTP ${service.last_probe_status_code}`
                    : "None"}
                </span>
              </li>
              {service.last_probe_error && (
                <li>
                  <strong style={{ color: "var(--red)" }}>
                    Last probe error:{" "}
                  </strong>
                  <span style={{ color: "var(--red)" }}>
                    {service.last_probe_error}
                  </span>
                </li>
              )}
            </ul>
          </div>

          <div style={{ marginTop: "1.5rem" }}>
            <button
              type="submit"
              disabled={saving}
              className="ws-button ws-primary"
            >
              {saving ? "Saving Changes…" : "Save Connection Settings"}
            </button>
          </div>
        </form>
      </section>

      {/* 2. Recent Health Observations */}
      <section
        className="an-panel application-section"
        aria-labelledby="obs-table-title"
        style={{ marginTop: "2rem" }}
      >
        <div className="an-section-heading">
          <div>
            <span className="an-eyebrow">Historical Health Probes</span>
            <h2 id="obs-table-title">Recent Health Observations</h2>
            <p>
              Direct record of outbound health checks performed by AegisOps.
            </p>
          </div>
          <button
            type="button"
            className="ws-button"
            onClick={refreshObservations}
            disabled={loadingObservations}
          >
            Refresh ↺
          </button>
        </div>

        {loadingObservations ? (
          <p>Loading observations…</p>
        ) : observations.length === 0 ? (
          <div className="application-empty">
            <h3>No health observations recorded yet.</h3>
            <p>
              Click <strong>Test Connection Now</strong> above or enable
              continuous monitoring to record health probes.
            </p>
          </div>
        ) : (
          <div
            className="an-table-scroll"
            role="region"
            aria-label="Health observations"
          >
            <table className="an-service-table">
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>Status</th>
                  <th>HTTP Code</th>
                  <th>Latency</th>
                  <th>Details</th>
                </tr>
              </thead>
              <tbody>
                {observations.map((obs) => (
                  <tr key={obs.id}>
                    <td>
                      <time dateTime={obs.observed_at}>
                        {utc(obs.observed_at)}
                      </time>
                    </td>
                    <td>
                      <HealthStatus health={obs.status} />
                    </td>
                    <td>
                      <span className="mono">
                        {obs.status_code != null ? obs.status_code : "—"}
                      </span>
                    </td>
                    <td>
                      <span className="mono">
                        {obs.latency_ms != null ? `${obs.latency_ms} ms` : "—"}
                      </span>
                    </td>
                    <td>{obs.error_message || "Probe responded normally"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* 3. General Service Metadata Panel */}
      <section
        className="an-panel application-section"
        aria-labelledby="meta-settings-title"
        style={{ marginTop: "2rem" }}
      >
        <div className="an-section-heading">
          <div>
            <span className="an-eyebrow">Application Metadata</span>
            <h2 id="meta-settings-title">Identity & Source Repository</h2>
            <p>
              Update application environment, description, and source repository
              binding.
            </p>
          </div>
        </div>

        <form onSubmit={handleSaveSettings} className="application-form">
          <label htmlFor="service-name-edit">
            Application Name
            <input
              id="service-name-edit"
              required
              maxLength={120}
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </label>

          <label htmlFor="service-env-edit">
            Environment
            <select
              id="service-env-edit"
              value={environment}
              onChange={(e) => setEnvironment(e.target.value)}
            >
              <option value="production">Production</option>
              <option value="staging">Staging</option>
              <option value="development">Development</option>
            </select>
          </label>

          <label htmlFor="service-desc-edit">
            Description
            <textarea
              id="service-desc-edit"
              rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="What does this application do?"
            />
          </label>

          <label htmlFor="service-github-edit">
            GitHub Repository <span>(owner/repo)</span>
            <input
              id="service-github-edit"
              value={githubRepo}
              onChange={(e) => setGithubRepo(e.target.value)}
              placeholder="e.g. ironlog-app/ironlog-backend"
            />
          </label>

          <label htmlFor="service-version-edit">
            Current Version / Release Tag
            <input
              id="service-version-edit"
              value={currentVersion}
              onChange={(e) => setCurrentVersion(e.target.value)}
              placeholder="e.g. v1.4.0"
            />
          </label>

          <div style={{ marginTop: "1rem" }}>
            <button
              type="submit"
              disabled={saving}
              className="ws-button ws-primary"
            >
              {saving ? "Saving Metadata…" : "Save Metadata"}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
