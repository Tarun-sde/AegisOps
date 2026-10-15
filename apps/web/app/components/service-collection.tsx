"use client";
import { useState, useRef } from "react";
import Link from "next/link";
import { ServiceDrawing, HealthStatus } from "./project-visuals";
import { useFavorites } from "./app-shell";
import type { Service, IncidentListResponse } from "../lib/api";
export function ServiceCollection({
  services,
  incidents,
}: {
  services: Service[];
  incidents: IncidentListResponse | null;
}) {
  const { pinned, toggle } = useFavorites();
  const searchInput = useRef<HTMLInputElement>(null);
  const [search, setSearch] = useState("");
  const [environment, setEnvironment] = useState("");
  const [status, setStatus] = useState("");
  const [sort, setSort] = useState("name");
  const [view, setView] = useState("grid");
  const shown = services
    .filter(
      (s) =>
        `${s.name} ${s.description ?? ""} ${s.environment}`
          .toLowerCase()
          .includes(search.toLowerCase()) &&
        (!environment || s.environment === environment) &&
        (!status || s.status === status),
    )
    .sort(
      (a, b) =>
        (sort === "recent"
          ? b.created_at.localeCompare(a.created_at)
          : a.name.localeCompare(b.name)) || a.id.localeCompare(b.id),
    );
  return (
    <section aria-labelledby="services-title">
      <h2 id="services-title" className="sr-only">
        Registered services ({services.length})
      </h2>
      <div className="ws-controls">
        <div className="ws-search">
          <span aria-hidden="true">⌕</span>
          <input
            id="project-search"
            ref={searchInput}
            type="search"
            aria-label="Search services"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Escape") setSearch("");
            }}
            placeholder="Search services or environment…"
          />
          {search ? (
            <button
              aria-label="Clear search"
              onClick={() => {
                setSearch("");
                searchInput.current?.focus();
              }}
            >
              ×
            </button>
          ) : (
            <kbd>F</kbd>
          )}
        </div>
        <label>
          <span>Environment</span>
          <select
            aria-label="Environment"
            value={environment}
            onChange={(e) => setEnvironment(e.target.value)}
          >
            <option value="">All environments</option>
            {[...new Set(services.map((s) => s.environment))]
              .sort()
              .map((e) => (
                <option key={e}>{e}</option>
              ))}
          </select>
        </label>
        <label>
          <span>Registration</span>
          <select
            aria-label="Registration"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
          >
            <option value="">All statuses</option>
            {[...new Set(services.map((s) => s.status))].sort().map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
        </label>
        <label>
          <span>Sort services</span>
          <select
            aria-label="Sort services"
            value={sort}
            onChange={(e) => setSort(e.target.value)}
          >
            <option value="name">Name (A–Z)</option>
            <option value="recent">Recently registered</option>
          </select>
        </label>
        <div className="ws-view-toggle">
          <button
            aria-label="Grid view"
            aria-pressed={view === "grid"}
            onClick={() => setView("grid")}
          >
            ⊞
          </button>
          <button
            aria-label="List view"
            aria-pressed={view === "list"}
            onClick={() => setView("list")}
          >
            ☰
          </button>
        </div>
      </div>
      <div className="ws-register-label">
        <span role="status" className="mono">
          Showing {shown.length} of {services.length} services
        </span>
        {search || environment || status ? (
          <button
            onClick={() => {
              setSearch("");
              setEnvironment("");
              setStatus("");
              searchInput.current?.focus();
            }}
          >
            Reset all filters ↺
          </button>
        ) : (
          <span className="mono">
            {view === "grid"
              ? "01 / SERVICE INDEX"
              : "02 / ENVIRONMENT REGISTER"}
          </span>
        )}
      </div>
      {shown.some((s) => pinned.includes(s.id)) && (
        <details className="ws-favorites" open>
          <summary>
            Your Favorites{" "}
            <span className="mono">
              {shown.filter((s) => pinned.includes(s.id)).length}
            </span>
          </summary>
          <div>
            {shown
              .filter((s) => pinned.includes(s.id))
              .map((s) => (
                <Link key={s.id} href={`/app/services/${s.id}`}>
                  <span aria-hidden="true">★</span>
                  {s.name}
                  <span aria-hidden="true">↗</span>
                </Link>
              ))}
          </div>
        </details>
      )}
      <div
        className={`ws-collection service-collection ${view === "list" ? "list" : "grid-view"}`}
        data-view={view}
      >
        {view === "list" ? (
          <div className="ws-project-list">
            {[...new Set(shown.map((s) => s.environment))].sort().map((env) => (
              <section key={env} aria-label={`${env} services`}>
                <h2 className="mono">
                  {env}
                  <span>
                    {shown.filter((s) => s.environment === env).length}
                  </span>
                </h2>
                <ul>
                  {shown
                    .filter((s) => s.environment === env)
                    .map((s) => (
                      <li
                        className="ws-project-row"
                        key={s.id}
                        data-project={s.id}
                      >
                        <div className="ws-row-identity">
                          <Link
                            className="ws-card-link"
                            href={`/app/services/${s.id}`}
                          >
                            <strong>{s.name}</strong>
                            <span aria-hidden="true">↗</span>
                          </Link>
                          <p>{s.description || "No description provided."}</p>
                          <span className="mono">Registered service</span>
                        </div>
                        <div>
                          <small>Monitoring</small>
                          <span className="ws-connection">Not reported</span>
                        </div>
                        <div>
                          <small>Health</small>
                          <HealthStatus health="unknown" />
                        </div>
                        <div>
                          <small>Services / incidents</small>
                          <span className="mono">
                            1 /{" "}
                            {incidents
                              ? incidents.items.filter(
                                  (inc) => inc.service_id === s.id,
                                ).length
                              : "—"}
                          </span>
                          <small>Latest incident page</small>
                        </div>
                        <div>
                          <small>Registered</small>
                          <span className="mono">
                            {s.created_at.slice(0, 10)} UTC
                          </span>
                        </div>
                        <div className="ws-project-actions">
                          <button
                            className="ws-pin"
                            aria-label={`${pinned.includes(s.id) ? "Unpin" : "Pin"} ${s.name}`}
                            aria-pressed={pinned.includes(s.id)}
                            onClick={() => toggle(s.id)}
                          >
                            {pinned.includes(s.id) ? "★" : "☆"}
                          </button>
                          <Link
                            className="ws-pin"
                            aria-label={`Details for ${s.name}`}
                            href={`/app/services/${s.id}`}
                          >
                            ···
                          </Link>
                        </div>
                      </li>
                    ))}
                </ul>
              </section>
            ))}
          </div>
        ) : (
          <div className="ws-project-grid">
            {shown.map((s, i) => (
              <article
                className="ws-project-card"
                key={s.id}
                data-project={s.id}
              >
                <div className="ws-card-top">
                  <span className="ws-card-id mono">
                    [{String(i + 1).padStart(2, "0")}] / {s.id.slice(0, 8)}
                  </span>
                  <div className="ws-project-actions">
                    <button
                      className="ws-pin"
                      aria-label={`${pinned.includes(s.id) ? "Unpin" : "Pin"} ${s.name}`}
                      aria-pressed={pinned.includes(s.id)}
                      onClick={() => toggle(s.id)}
                    >
                      {pinned.includes(s.id) ? "★" : "☆"}
                    </button>
                    <Link
                      className="ws-pin"
                      aria-label={`Details for ${s.name}`}
                      href={`/app/services/${s.id}`}
                    >
                      ···
                    </Link>
                  </div>
                </div>
                <div className="ws-card-identity">
                  <h2>
                    <Link
                      className="ws-card-link"
                      href={`/app/services/${s.id}`}
                    >
                      {s.name}
                    </Link>
                  </h2>
                  <p>{s.description || "No description provided."}</p>
                  <span className="ws-tech mono">
                    {s.environment} / Registered service
                  </span>
                </div>
                {view === "grid" && (
                  <div className="ws-card-drawing">
                    <div className="ws-drawing-heading mono">
                      <span>SERVICE SCHEMATIC</span>
                      <span>{s.environment}</span>
                    </div>
                    <ServiceDrawing
                      project={{
                        name: s.name,
                        services: [
                          { id: s.id, name: s.name, health: "unknown" },
                        ],
                      }}
                    />
                  </div>
                )}
                <div className="ws-card-status">
                  <span className="ws-connection">
                    Connection: not reported
                  </span>
                  <HealthStatus health="unknown" />
                </div>
                <div className="ws-card-counts">
                  <span>
                    <b>01</b> service
                  </span>
                  <span>
                    {incidents
                      ? `${incidents.items.filter((inc) => inc.service_id === s.id).length} incidents on latest page`
                      : "Incident count unavailable"}
                  </span>
                  <span className="ws-open-arrow" aria-hidden="true">
                    ↗
                  </span>
                </div>
                <div className="ws-card-signal">
                  <span className="mono">REGISTRATION / {s.status}</span>
                  <p>Telemetry freshness is not reported.</p>
                  <span className="mono">
                    {new Date(s.created_at).toISOString().slice(0, 10)} UTC
                  </span>
                </div>
              </article>
            ))}
          </div>
        )}
      </div>
      {!shown.length && (
        <div className="ws-empty">
          <h3>
            {services.length
              ? "No matching services"
              : "No registered services"}
          </h3>
          <p>
            {services.length
              ? "Adjust your search or filters."
              : "Register a service to start connecting operational signals."}
          </p>
          <button
            onClick={() => {
              setSearch("");
              setEnvironment("");
              setStatus("");
            }}
          >
            Reset filters
          </button>
        </div>
      )}
    </section>
  );
}
