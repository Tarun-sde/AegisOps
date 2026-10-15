"use client";

import Link from "next/link";
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
    setName(res.data.name);
    setServiceId(res.data.id);
    router.refresh();
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
    <main id="main" className="ws-content application-connect">
      <div className="ws-project-context">
        <Link href="/app">← All applications</Link>
        <span className="mono">APPLICATION SETUP</span>
      </div>
      <div className="ws-page-heading">
        <div>
          <span className="mono ws-eyebrow">Your workspace</span>
          <h1>
            {serviceId ? "Application registered" : "Connect an application"}
          </h1>
          <p>
            Register your application, then verify an optional HTTP healthcheck.
          </p>
        </div>
      </div>
      {error && (
        <p role="alert" className="application-error">
          {error}
        </p>
      )}
      <div className="application-connect-grid">
        <section className="an-panel">
          <span className="an-eyebrow">01 / Application identity</span>
          <h2>Register your application</h2>
          <form onSubmit={handleCreateService} className="application-form">
            <label htmlFor="service-name-input">
              Application name
              <input
                id="service-name-input"
                required
                maxLength={120}
                disabled={!!serviceId || savingService}
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Your application’s name"
              />
            </label>
            <label htmlFor="env-select">
              Environment
              <select
                id="env-select"
                aria-label="Environment"
                required
                disabled={!!serviceId || savingService}
                value={environment}
                onChange={(e) => setEnvironment(e.target.value)}
              >
                <option value="" disabled>
                  Select environment
                </option>
                <option value="production">Production</option>
                <option value="staging">Staging</option>
                <option value="development">Development</option>
              </select>
            </label>
            <label htmlFor="service-desc-input">
              Description <span>(optional)</span>
              <textarea
                id="service-desc-input"
                rows={3}
                disabled={!!serviceId || savingService}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="What does this application do?"
              />
            </label>
            {!serviceId ? (
              <button
                type="submit"
                disabled={savingService}
                className="ws-button ws-primary"
              >
                {savingService ? "Registering…" : "Register application →"}
              </button>
            ) : (
              <div role="status">
                <strong>{name} is registered.</strong>
                <p className="application-uuid">Service ID: {serviceId}</p>
                <div className="application-incident-picker">
                  <Link className="ws-button ws-primary" href="/app">
                    View applications →
                  </Link>
                  <Link
                    className="ws-button"
                    href={`/app/services/${serviceId}`}
                  >
                    Open application ↗
                  </Link>
                </div>
              </div>
            )}
          </form>
        </section>
        <aside className="application-connect-note">
          <span className="an-eyebrow">What happens next</span>
          <h2>A home for your operational context.</h2>
          <ol>
            <li>Register the application in your organization.</li>
            <li>Optionally test its HTTP healthcheck.</li>
            <li>
              Open its dashboard to review incidents, investigations and
              evidence.
            </li>
          </ol>
          <p>
            Registration does not configure telemetry. Monitoring remains
            unknown until verified signals are available.
          </p>
        </aside>
      </div>
      {serviceId && (
        <section className="an-panel application-section">
          <span className="an-eyebrow">02 / Optional verification</span>
          <h2>Verify healthcheck connector</h2>
          <p>
            A successful HTTP probe confirms endpoint reachability only. It does
            not establish a metrics, logs or traces pipeline.
          </p>
          <form
            className="application-form"
            onSubmit={(e) => {
              e.preventDefault();
              void handleVerifyConnector();
            }}
          >
            <label htmlFor="connector-url-input">
              Healthcheck URL
              <input
                id="connector-url-input"
                type="url"
                required
                value={connectorUrl}
                onChange={(e) => setConnectorUrl(e.target.value)}
                placeholder="https://your-service.example/healthz"
              />
            </label>
            <button type="submit" disabled={verifying} className="ws-button">
              {verifying ? "Probing…" : "Test Connector"}
            </button>
            {verifyResult && (
              <p role="status">
                {verifyResult.success
                  ? "HTTP probe succeeded"
                  : "HTTP probe failed"}
                : {verifyResult.message}
                {verifyResult.latency_ms != null &&
                  ` (${verifyResult.latency_ms} ms)`}
              </p>
            )}
          </form>
        </section>
      )}
    </main>
  );
}
