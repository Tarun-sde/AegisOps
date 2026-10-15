"use client";
import { useCallback, useEffect, useState, type ReactNode } from "react";
import {
  type InvestigationRun,
  type InvestigationRunDetail,
  type ToolExecution,
  startInvestigation,
  getInvestigation,
  getInvestigationEvents,
  listIncidentInvestigations,
  cancelInvestigation,
} from "../../../lib/api";
import { EvidenceExplorer } from "../../../components/evidence-explorer";
import { StatusBadge } from "../../../components/status-badge";
const running = (status: string) =>
  ["QUEUED", "COLLECTING_CONTEXT", "INVESTIGATING", "VALIDATING"].includes(
    status,
  );
export function InvestigationPanel({
  incidentId,
  timeline,
}: {
  incidentId: string;
  timeline?: ReactNode;
}) {
  const [runs, setRuns] = useState<InvestigationRun[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [activeRun, setActiveRun] = useState<InvestigationRunDetail | null>(
    null,
  );
  const [events, setEvents] = useState<ToolExecution[]>([]);
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reload, setReload] = useState(0);
  const refreshHistory = useCallback(async () => {
    const res = await listIncidentInvestigations(incidentId);
    if (res.error) setError(res.error);
    if (res.data) {
      setRuns(res.data);
      setSelected(res.data[0]?.id ?? null);
    }
    setLoading(false);
  }, [incidentId]);
  useEffect(() => {
    refreshHistory();
  }, [refreshHistory]);
  useEffect(() => {
    if (!selected) return;
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    setActiveRun(null);
    setEvents([]);
    async function load() {
      const [detail, tools] = await Promise.all([
        getInvestigation(selected!),
        getInvestigationEvents(selected!),
      ]);
      if (!active) return;
      if (detail.error || tools.error) setError(detail.error || tools.error);
      else setError(null);
      if (detail.data) {
        setActiveRun(detail.data);
        setRuns((previous) =>
          previous.map((r) =>
            r.id === detail.data!.id
              ? { ...r, status: detail.data!.status }
              : r,
          ),
        );
      }
      if (tools.data) setEvents(tools.data);
      if (!detail.data || running(detail.data.status))
        timer = setTimeout(load, 2000);
    }
    load();
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [selected, reload]);
  async function start() {
    setStarting(true);
    setError(null);
    const res = await startInvestigation(incidentId);
    if (res.error) setError(res.error);
    else if (res.data) {
      setRuns((previous) => [res.data!, ...previous]);
      setSelected(res.data.id);
    }
    setStarting(false);
  }
  async function cancel() {
    if (!selected) return;
    setCancelling(true);
    const res = await cancelInvestigation(selected);
    if (res.error) setError(res.error);
    else setReload((n) => n + 1);
    setCancelling(false);
  }
  const inProgress = runs.some((r) => running(r.status));
  const mode = runs.find((r) => r.id === selected)?.execution_mode;
  return (
    <div id="investigation">
      <section className="an-panel" aria-labelledby="ai-investigation-title">
        <div className="an-section-heading">
          <div>
            <p className="an-eyebrow">Investigation / Persisted runs</p>
            <h2 id="ai-investigation-title">AI Incident Investigator</h2>
          </div>
          <div className="citations">
            {activeRun && running(activeRun.status) && (
              <button disabled={cancelling} onClick={cancel}>
                {cancelling ? "Cancelling…" : "Cancel Run"}
              </button>
            )}
            <button
              id="start-investigation-btn"
              disabled={starting || inProgress || loading}
              onClick={start}
            >
              {starting
                ? "Dispatching…"
                : inProgress
                  ? "Investigation Running…"
                  : "Start AI Investigation"}
            </button>
          </div>
        </div>
        <p>
          Bounded read-only investigation. Review hypotheses and their evidence
          before deciding on an action.
        </p>
        {error && (
          <p role="alert" className="error-message">
            {error}
          </p>
        )}
        {loading ? (
          <p role="status">Loading investigation history…</p>
        ) : !runs.length ? (
          <p>No investigation runs recorded for this incident.</p>
        ) : (
          <label className="run-selector">
            Run history
            <select
              value={selected ?? ""}
              onChange={(e) => {
                setError(null);
                setSelected(e.target.value);
              }}
            >
              {runs.map((r) => (
                <option value={r.id} key={r.id}>
                  {new Date(r.created_at).toISOString()} · {r.status} ·{" "}
                  {r.id.slice(0, 8)}
                </option>
              ))}
            </select>
          </label>
        )}
        {activeRun ? (
          <>
            <div className="citations">
              <span
                className="badge badge-info"
                id="investigation-status-badge"
                data-run-id={activeRun.id}
              >
                STATUS: {activeRun.status}
              </span>
              <span className="badge badge-neutral">
                MODE:{" "}
                {mode === "live"
                  ? "LIVE"
                  : mode === "offline"
                    ? "OFFLINE (TEST DOUBLE)"
                    : "NOT REPORTED"}
              </span>
            </div>
            <p>
              Model: <code>{activeRun.model}</code> · Prompt:{" "}
              <code>{activeRun.prompt_version}</code> · Tool calls:{" "}
              {activeRun.tool_call_count}
            </p>
            {mode === "offline" && (
              <p>
                Deterministic demonstration output. This run is not a live model
                diagnosis.
              </p>
            )}
            {activeRun.status === "INCONCLUSIVE" && (
              <div className="an-review-note">
                <h3>Inconclusive result</h3>
                <p>
                  The run did not establish a supported diagnosis. Review
                  missing evidence and limitations.
                </p>
              </div>
            )}
            {activeRun.error_message && (
              <p role="alert">{activeRun.error_message}</p>
            )}
            {running(activeRun.status) ? (
              <p role="status">
                Investigation in progress. No final diagnosis is available yet.
              </p>
            ) : (
              <>
                {activeRun.summary && (
                  <>
                    <h3>Investigation summary</h3>
                    <p>{activeRun.summary}</p>
                  </>
                )}
                {activeRun.missing_evidence.length > 0 && (
                  <>
                    <h3>Missing evidence</h3>
                    <ul>
                      {activeRun.missing_evidence.map((e, i) => (
                        <li key={i}>{e}</li>
                      ))}
                    </ul>
                  </>
                )}
                {activeRun.limitations.length > 0 && (
                  <>
                    <h3>Limitations</h3>
                    <ul>
                      {activeRun.limitations.map((e, i) => (
                        <li key={i}>{e}</li>
                      ))}
                    </ul>
                  </>
                )}
              </>
            )}
          </>
        ) : (
          selected && <p role="status">Loading selected run…</p>
        )}
      </section>
      {activeRun && !running(activeRun.status) && (
        <EvidenceExplorer
          key={activeRun.id}
          run={activeRun}
          timeline={timeline}
        />
      )}
      <section className="an-panel" aria-labelledby="tools-title">
        <p className="an-eyebrow">Deterministic gateway</p>
        <h2 id="tools-title">Tool Execution Audit Log ({events.length})</h2>
        {!events.length ? (
          <p>No tool executions available for the selected run.</p>
        ) : (
          events.map((t) => (
            <details key={t.id} className="timeline-event">
              <summary>
                <strong>{t.tool_name}</strong> <StatusBadge value={t.status} />{" "}
                · {t.latency_ms.toFixed(1)} ms
              </summary>
              <pre>{JSON.stringify(t.arguments, null, 2)}</pre>
              {t.error_category && <p>Error: {t.error_category}</p>}
              <p>{new Date(t.created_at).toISOString()} UTC</p>
            </details>
          ))
        )}
      </section>
      {(!activeRun || running(activeRun.status)) && timeline}
    </div>
  );
}
