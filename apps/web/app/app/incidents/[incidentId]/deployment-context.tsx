"use client";

import { useEffect, useState } from "react";
import { DeploymentRecord, getServiceDeployments } from "../../../lib/api";

interface DeploymentContextProps {
  serviceId: string;
  incidentEnvironment?: string;
}

export function DeploymentContext({
  serviceId,
  incidentEnvironment,
}: DeploymentContextProps) {
  const [deployments, setDeployments] = useState<DeploymentRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    async function load() {
      setLoading(true);
      setError(null);
      const res = await getServiceDeployments(serviceId, 3);
      if (!active) return;
      if (res.error) {
        setError(res.error);
      } else if (res.data) {
        setDeployments(res.data);
      }
      setLoading(false);
    }
    load();
    return () => {
      active = false;
    };
  }, [serviceId]);

  return (
    <section
      aria-labelledby="deployment-context-title"
      className="panel"
      style={{ marginTop: "24px" }}
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
            Scoped GitHub Read-Only Integration
          </p>
          <h2 id="deployment-context-title" style={{ margin: "4px 0" }}>
            Deployment Context
          </h2>
        </div>
        <span
          className="badge"
          style={{
            background: "var(--bg-surface)",
            borderColor: "var(--border-default)",
            color: "var(--text-secondary)",
            fontSize: "0.875rem",
          }}
        >
          Environment: {incidentEnvironment || "Not reported"}
        </span>
      </div>

      <p
        style={{
          color: "var(--text-secondary)",
          fontSize: "0.875rem",
          marginTop: "6px",
          lineHeight: 1.5,
        }}
      >
        Server-scoped repository metadata retrieved via least-privilege GitHub
        read adapter.
        <em style={{ color: "var(--status-warning-text)", marginLeft: "6px" }}>
          Note: Deployment timing is correlation context, not automated root
          cause proof.
        </em>
      </p>

      {loading && (
        <p
          style={{
            color: "var(--text-secondary)",
            fontSize: "0.9rem",
            marginTop: "12px",
          }}
        >
          Querying authorized GitHub repository deployments...
        </p>
      )}

      {error && (
        <div
          style={{
            marginTop: "12px",
            padding: "8px 12px",
            background: "var(--bg-surface)",
            border: "1px solid var(--status-error-border)",
            borderRadius: "6px",
            color: "var(--status-error-text)",
            fontSize: "0.875rem",
          }}
        >
          <strong>GitHub Integration Warning:</strong> {error} (investigator
          will fall back to local telemetry).
        </div>
      )}

      {!loading && !error && deployments.length === 0 && (
        <div
          style={{
            marginTop: "12px",
            padding: "12px",
            background: "var(--status-info-bg)",
            border: "1px dashed var(--border-default)",
            borderRadius: "6px",
            color: "var(--text-secondary)",
            fontSize: "0.875rem",
          }}
        >
          No deployments or recent commits recorded for this service.
          Telemetry-only investigation active.
        </div>
      )}

      {!loading && deployments.length > 0 && (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: "10px",
            marginTop: "16px",
          }}
        >
          {deployments.map((dep) => (
            <div
              key={dep.deployment_id}
              style={{
                background: "var(--status-info-bg)",
                border: "1px solid var(--border-default)",
                borderRadius: "6px",
                padding: "10px 14px",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                flexWrap: "wrap",
                gap: "10px",
              }}
            >
              <div>
                <div
                  style={{ display: "flex", alignItems: "center", gap: "8px" }}
                >
                  <span
                    className="badge"
                    style={{
                      background: dep.is_deployment
                        ? "var(--bg-surface)"
                        : "var(--border-default)",
                      borderColor: dep.is_deployment
                        ? "var(--border-default)"
                        : "var(--status-info-border)",
                      color: dep.is_deployment
                        ? "var(--status-success-text)"
                        : "var(--status-info-text)",
                      fontSize: "0.875rem",
                    }}
                  >
                    {dep.is_deployment ? "DEPLOYMENT" : "COMMIT"}
                  </span>
                  <strong
                    style={{
                      color: "var(--status-info-text)",
                      fontSize: "0.9rem",
                    }}
                  >
                    {dep.repository}
                  </strong>
                  {dep.version && (
                    <span
                      style={{
                        color: "var(--status-info-text)",
                        fontSize: "0.875rem",
                        fontWeight: 600,
                      }}
                    >
                      v{dep.version}
                    </span>
                  )}
                  <code
                    style={{
                      fontSize: "0.875rem",
                      color: "var(--status-info-text)",
                      background: "var(--bg-surface)",
                      padding: "2px 6px",
                      borderRadius: "4px",
                    }}
                  >
                    {dep.commit_sha.substring(0, 7)}
                  </code>
                </div>
                {dep.message && (
                  <p
                    style={{
                      margin: "4px 0 0 0",
                      color: "var(--text-secondary)",
                      fontSize: "0.875rem",
                    }}
                  >
                    {dep.message}
                  </p>
                )}
              </div>

              <div
                style={{
                  textAlign: "right",
                  fontSize: "0.875rem",
                  color: "var(--text-secondary)",
                }}
              >
                <div>{new Date(dep.deployed_at).toLocaleString()}</div>
                <div
                  style={{
                    fontSize: "0.875rem",
                    color: "var(--status-info-text)",
                  }}
                >
                  via {dep.source}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
