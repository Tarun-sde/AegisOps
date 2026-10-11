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
    <section aria-labelledby="deployment-context-title" className="panel" style={{ marginTop: "24px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "12px" }}>
        <div>
          <p className="eyebrow" style={{ margin: 0 }}>Scoped GitHub Read-Only Integration</p>
          <h2 id="deployment-context-title" style={{ margin: "4px 0" }}>Verified Deployment Context</h2>
        </div>
        <span
          className="badge"
          style={{
            background: "#161b22",
            borderColor: "#30363d",
            color: "#8b949e",
            fontSize: "0.8rem",
          }}
        >
          Environment: {incidentEnvironment || "staging"}
        </span>
      </div>

      <p style={{ color: "#8b949e", fontSize: "0.85rem", marginTop: "6px", lineHeight: 1.5 }}>
        Server-scoped repository metadata retrieved via least-privilege GitHub read adapter.
        <em style={{ color: "#d29922", marginLeft: "6px" }}>
          Note: Deployment timing is correlation context, not automated root cause proof.
        </em>
      </p>

      {loading && (
        <p style={{ color: "#8b949e", fontSize: "0.9rem", marginTop: "12px" }}>
          Querying authorized GitHub repository deployments...
        </p>
      )}

      {error && (
        <div style={{ marginTop: "12px", padding: "8px 12px", background: "#211a1d", border: "1px solid #63333e", borderRadius: "6px", color: "#f85149", fontSize: "0.85rem" }}>
          <strong>GitHub Integration Warning:</strong> {error} (investigator will fall back to local telemetry).
        </div>
      )}

      {!loading && !error && deployments.length === 0 && (
        <div style={{ marginTop: "12px", padding: "12px", background: "#0d1117", border: "1px dashed #30363d", borderRadius: "6px", color: "#8b949e", fontSize: "0.85rem" }}>
          No deployments or recent commits recorded for this service. Telemetry-only investigation active.
        </div>
      )}

      {!loading && deployments.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: "10px", marginTop: "16px" }}>
          {deployments.map((dep) => (
            <div
              key={dep.deployment_id}
              style={{
                background: "#0d1117",
                border: "1px solid #30363d",
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
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <span
                    className="badge"
                    style={{
                      background: dep.is_deployment ? "#1b2a20" : "#232b38",
                      borderColor: dep.is_deployment ? "#3a5746" : "#3b5270",
                      color: dep.is_deployment ? "#7ee787" : "#a4c2e6",
                      fontSize: "0.75rem",
                    }}
                  >
                    {dep.is_deployment ? "DEPLOYMENT" : "COMMIT"}
                  </span>
                  <strong style={{ color: "#e6edf3", fontSize: "0.9rem" }}>
                    {dep.repository}
                  </strong>
                  {dep.version && (
                    <span style={{ color: "#d2a8ff", fontSize: "0.85rem", fontWeight: 600 }}>
                      v{dep.version}
                    </span>
                  )}
                  <code style={{ fontSize: "0.8rem", color: "#79c0ff", background: "#161b22", padding: "2px 6px", borderRadius: "4px" }}>
                    {dep.commit_sha.substring(0, 7)}
                  </code>
                </div>
                {dep.message && (
                  <p style={{ margin: "4px 0 0 0", color: "#8b949e", fontSize: "0.8rem" }}>
                    {dep.message}
                  </p>
                )}
              </div>

              <div style={{ textAlign: "right", fontSize: "0.8rem", color: "#8b949e" }}>
                <div>{new Date(dep.deployed_at).toLocaleString()}</div>
                <div style={{ fontSize: "0.75rem", color: "#58a6ff" }}>via {dep.source}</div>
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
