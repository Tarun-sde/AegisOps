"use client";
import { useState } from "react";
import { Mark } from "./artwork";
import {
  SystemElevation as Elevation,
  IncidentPlan as FloorPlan,
  TelemetryTerrain as Terrain,
} from "./system-artwork";

export const featureNames = [
  "Overview",
  "Human Approval",
  "Incident History",
  "Evidence Review",
  "Runbook Context",
];
export function ActivityPanel({ compact = false }: { compact?: boolean }) {
  return (
    <div className={`activity-panel ${compact ? "compact" : ""}`}>
      <div className="preview-stats">
        {[
          ["SCOPED", "8"],
          ["PENDING", "4"],
          ["p95 / SAMPLE", "840 ms"],
          ["DB SPAN", "720 ms"],
        ].map(([label, value], i) => (
          <div key={label}>
            <span>
              {label}
              <i className={`status-dot dot-${i}`} />
            </span>
            <strong>{value}</strong>
          </div>
        ))}
      </div>
      <div className="preview-heading">
        <span>ILLUSTRATIVE SAMPLE / INC-DEMO-042</span>
        <small>Shop API / not live telemetry</small>
      </div>
      <div className="activity-title">
        INCIDENT ACTIVITY <span>SAMPLE ↗</span>
      </div>
      {[
        "SHOP API / LATENCY",
        "TRACE / DATABASE SPAN",
        "STAGING / HUMAN REVIEW",
        "RIVERSIDE SHOP APIS / p95 / SAMPLE",
      ].map((title, i) => (
        <div className="activity-row" key={title}>
          <Mark />
          <div>
            <b>{title}</b>
            <p>
              {
                [
                  "Latency threshold exceeded",
                  "Reviewing scoped trace evidence",
                  "Exact proposal awaiting approval",
                  "Incident context retained",
                ][i]
              }
            </p>
            <small>{i + 2} minutes ago</small>
          </div>
          <span>{["REVIEW", "CHECKING", "PENDING", "COMPLETE"][i]}</span>
        </div>
      ))}
    </div>
  );
}
export function ApprovalCard() {
  const [decision, setDecision] = useState<"approved" | "rejected" | null>(
    null,
  );
  return (
    <div className="approval-card">
      <div className="preview-dark-title">
        STAGING PROPOSAL <span>SAMPLE</span>
      </div>
      <p>
        restart_demo_service · staging. Review the immutable sample payload
        below.
      </p>
      <div className="approval-detail mono">
        service_name: shop-api · reason: Sample incident review ·
        grace_period_seconds: 10. Approval does not execute.
      </div>
      {decision ? (
        <div className="decision" role="status">
          {decision === "approved"
            ? "Sample approved locally. Execution has not occurred."
            : "Sample rejected locally. No action taken."}
          <button onClick={() => setDecision(null)}>Reset preview</button>
        </div>
      ) : (
        <div className="approval-actions">
          <button onClick={() => setDecision("rejected")}>Reject sample</button>
          <button onClick={() => setDecision("approved")}>
            Approve sample <span>↗</span>
          </button>
        </div>
      )}
    </div>
  );
}
export function PendingPanel() {
  return (
    <div className="pending-panel">
      <div className="preview-dark-title">
        REVIEW BOUNDARY <span>SAMPLE ↗</span>
      </div>
      {["REVIEW EXACT PAYLOAD", "EXECUTE SEPARATELY", "VERIFY RECOVERY"].map(
        (title, i) => (
          <div key={title}>
            <b>{title}</b>
            <p>
              {
                [
                  "Shop API · staging only",
                  "Backend policy check required",
                  "Independent observation required",
                ][i]
              }
            </p>
            <span className="pending-tag">PENDING ↗</span>
          </div>
        ),
      )}
    </div>
  );
}
export function ProductPreview({
  variant = 0,
  hero = false,
}: {
  variant?: number;
  hero?: boolean;
}) {
  return (
    <div
      className={`product-preview preview-${variant} ${hero ? "preview-hero" : ""}`}
    >
      {hero ? (
        <>
          <div className="terrain" aria-hidden="true">
            <Terrain />
          </div>
          <ActivityPanel />
          <PendingPanel />
        </>
      ) : variant === 0 ? (
        <>
          <div className="window-stack" aria-hidden="true">
            {Array.from({ length: 7 }, (_, i) => (
              <div
                key={i}
                style={{ width: `${48 + i * 7}%`, top: `${10 + i * 6}%` }}
              >
                <div className="preview-dark-title">AEGISOPS / SAMPLE</div>
              </div>
            ))}
          </div>
          <div className="front-window">
            <ActivityPanel compact />
          </div>
        </>
      ) : variant === 1 ? (
        <>
          <FloorPlan highlight />
          <ApprovalCard />
        </>
      ) : variant === 2 ? (
        <>
          <FloorPlan />
          <div className="history-panel">
            <i className="history-spine" aria-hidden="true" />
            <div className="preview-dark-title">
              INCIDENT HISTORY <span>SAMPLE</span>
            </div>
            {[
              ["10:42", "Proposal awaiting approval", "No action executed"],
              ["10:36", "Database latency flagged", "E03 / 720 ms trace span"],
              [
                "10:28",
                "Evidence collection complete",
                "E01 metric / E02 log / E03 trace",
              ],
            ].map(([time, title, detail]) => (
              <div className="history-event" key={time}>
                <time>{time}</time>
                <div>
                  <b>{title}</b>
                  <p>{detail}</p>
                </div>
                <span>↗</span>
              </div>
            ))}
          </div>
        </>
      ) : variant === 3 ? (
        <>
          <Elevation />
          <div className="team-panel">
            <i className="team-spine" aria-hidden="true" />
            <div className="preview-dark-title">INC-DEMO-042 / EVIDENCE</div>
            <div className="team-project">SCOPED REVIEW / ILLUSTRATIVE</div>
            {["Metric E01", "Trace E03", "Log E02", "Runbook RB01"].map(
              (name, i) => (
                <div className="team-member" key={name}>
                  <span className="avatar">
                    {name
                      .split(" ")
                      .map((n) => n[0])
                      .join("")}
                  </span>
                  <b>{name}</b>
                  <span className={i < 2 ? "pending-tag" : ""}>
                    {i < 2 ? "REVIEW" : "SCOPED"}
                  </span>
                </div>
              ),
            )}
          </div>
        </>
      ) : (
        <>
          <FloorPlan standardized />
          <svg
            className="standard-links"
            viewBox="0 0 100 100"
            preserveAspectRatio="none"
            aria-hidden="true"
          >
            <path
              className="standard-connection"
              pathLength="1"
              d="M35 24H60V72H80M60 48H27V65"
              fill="none"
              stroke="currentColor"
              strokeWidth=".2"
            />
          </svg>
          <div className="standards-panel">
            <div className="preview-dark-title">RUNBOOK CONTEXT</div>
            <p>RB-PG-POOL-01 / SAMPLE</p>
            <div className="standards-field">
              <span>SERVICE</span>
              <b>SHOP API</b>
            </div>
            <div className="standards-field">
              <span>PROCEDURE</span>
              <b>DB POOL REVIEW</b>
            </div>
            <div className="standards-field">
              <span>REVISION</span>
              <b>02</b>
            </div>
            <div className="standard-saved">
              Context retrieved for human review
            </div>
          </div>
        </>
      )}
    </div>
  );
}
