"use client";
import { useRef, useState, type ReactNode } from "react";
import type { InvestigationRunDetail } from "../lib/api";
export function EvidenceExplorer({
  run,
  timeline,
}: {
  run: InvestigationRunDetail;
  timeline?: ReactNode;
}) {
  const records = run.evidence_items.filter(
    (e) =>
      e.run_id === run.id &&
      e.organization_id === run.organization_id &&
      e.service_id === run.service_id,
  );
  const [selected, setSelected] = useState<string | null>(null);
  const explorer = useRef<HTMLElement>(null);
  const current = records.find((e) => e.evidence_id === selected) ?? records[0];
  const citation = (id: string) =>
    records.some((e) => e.evidence_id === id) ? (
      <button
        key={id}
        onClick={() => {
          setSelected(id);
          explorer.current?.focus();
        }}
      >
        {id} ↗
      </button>
    ) : (
      <span key={id} className="badge badge-warning">
        Unresolved citation: {id}
      </span>
    );
  return (
    <div className="an-investigation-grid evidence-layout">
      <section className="an-hypotheses" aria-labelledby="hypotheses-title">
        <p className="an-eyebrow">Qualified hypotheses</p>
        <h2 className="an-region-title" id="hypotheses-title">
          What may explain this?
        </h2>
        {!run.hypotheses.length && <p>No hypotheses available for this run.</p>}
        {run.hypotheses.map((h) => (
          <article key={h.id} className="an-panel an-hypothesis an-leading">
            <span className="badge badge-info">
              Confidence: {h.confidence} · qualitative
            </span>
            <h3>{h.cause}</h3>
            <h4>Supporting evidence</h4>
            {h.supporting_evidence.map((e, i) => (
              <div key={`${e.evidence_id}-${i}`}>
                <div className="an-citations">{citation(e.evidence_id)}</div>
                <p>{e.supports}</p>
              </div>
            ))}
            <h4>Contradicting evidence</h4>
            <div className="an-citations">
              {h.contradicting_evidence_ids.length ? (
                h.contradicting_evidence_ids.map(citation)
              ) : (
                <p>None cited. This does not establish certainty.</p>
              )}
            </div>
            {h.unverified_assumptions?.length ? (
              <>
                <h4>Unverified assumptions</h4>
                <ul>
                  {h.unverified_assumptions.map((a, i) => (
                    <li key={i}>{a}</li>
                  ))}
                </ul>
              </>
            ) : null}
            {h.next_check && (
              <p>
                <strong>Next check:</strong> {h.next_check}
              </p>
            )}
          </article>
        ))}
      </section>
      {timeline ?? (
        <aside className="an-panel an-timeline">
          <h2>Investigation context</h2>
          <p>Run: {run.id}</p>
          <p>
            Review missing evidence and limitations before deciding on any
            action.
          </p>
        </aside>
      )}
      <section
        ref={explorer}
        tabIndex={-1}
        className="an-panel an-evidence evidence-explorer"
        aria-labelledby="evidence-title"
      >
        <p className="an-eyebrow">
          Evidence explorer / {records.length} records
        </p>
        <h2 className="an-region-title" id="evidence-title">
          Inspect the source.
        </h2>
        <p>
          Authorized records from this run. A resolved citation establishes
          provenance, not causation.
        </p>
        {records.length ? (
          <>
            <div
              className="an-evidence-tabs"
              role="tablist"
              aria-label="Evidence records"
            >
              {records.map((e, i) => (
                <button
                  key={e.id}
                  id={`tab-${e.id}`}
                  role="tab"
                  aria-selected={current.id === e.id}
                  aria-controls={`record-${run.id}`}
                  tabIndex={current.id === e.id ? 0 : -1}
                  onClick={() => setSelected(e.evidence_id)}
                  onKeyDown={(event) => {
                    const next =
                      event.key === "ArrowRight"
                        ? (i + 1) % records.length
                        : event.key === "ArrowLeft"
                          ? (i + records.length - 1) % records.length
                          : event.key === "Home"
                            ? 0
                            : event.key === "End"
                              ? records.length - 1
                              : -1;
                    if (next >= 0) {
                      event.preventDefault();
                      setSelected(records[next].evidence_id);
                      document
                        .getElementById(`tab-${records[next].id}`)
                        ?.focus();
                    }
                  }}
                >
                  {e.source} · {i + 1}
                </button>
              ))}
            </div>
            <div
              className="an-evidence-record"
              role="tabpanel"
              id={`record-${run.id}`}
              aria-labelledby={`tab-${current.id}`}
              tabIndex={0}
            >
              <h3>{current.evidence_id}</h3>
              <dl>
                <dt>Observed</dt>
                <dd>{new Date(current.observed_at).toISOString()} (UTC)</dd>
                <dt>Source locator</dt>
                <dd>{current.locator}</dd>
                <dt>Content hash</dt>
                <dd>
                  <code>{current.content_hash}</code>
                </dd>
              </dl>
              <pre>{current.redacted_snippet}</pre>
              <details>
                <summary>Query metadata</summary>
                <pre>{JSON.stringify(current.query_metadata, null, 2)}</pre>
              </details>
            </div>
          </>
        ) : (
          <p>No authorized evidence records available.</p>
        )}
      </section>
    </div>
  );
}
