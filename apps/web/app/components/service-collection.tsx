"use client";
import { useState, useRef, useEffect } from "react";
import Link from "next/link";
import { ServiceDrawing, HealthStatus, type Health } from "./project-visuals";
import { ApplicationActions } from "./application-actions";
import { useAuth } from "../lib/auth-context";
import { useFavorites } from "./app-shell";
import type { Service } from "../lib/api";
export function ServiceCollection({ services }: { services: Service[] }) {
  const { pinned } = useFavorites();
  const searchInput = useRef<HTMLInputElement>(null);
  const [search, setSearch] = useState("");
  const [environment, setEnvironment] = useState("");
  const [favoritesOnly, setFavoritesOnly] = useState(false);
  const [sort, setSort] = useState("name");
  const [view, setView] = useState("grid");
  const { user, activeOrg } = useAuth();
  const viewKey =
    user && activeOrg ? `aegisops:${user.id}:${activeOrg.id}:view` : null;
  useEffect(() => {
    try {
      setView(
        viewKey && localStorage.getItem(viewKey) === "list" ? "list" : "grid",
      );
    } catch {
      /* Grid is the default without storage. */
    }
  }, [viewKey]);
  const chooseView = (next: string) => {
    setView(next);
    try {
      if (viewKey) localStorage.setItem(viewKey, next);
    } catch {
      /* In-memory preference still works. */
    }
  };
  const activity = (s: Service) =>
    [s.updated_at, s.last_incident_at ?? ""].sort().at(-1)!;
  const shown = services
    .filter(
      (s) =>
        s.name.toLowerCase().includes(search.toLowerCase()) &&
        (!environment || s.environment === environment) &&
        (!favoritesOnly || pinned.includes(s.id)),
    )
    .sort(
      (a, b) =>
        (sort === "recent"
          ? activity(b).localeCompare(activity(a))
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
            placeholder="Search applications…"
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
        <button
          className="ws-button"
          aria-pressed={favoritesOnly}
          onClick={() => setFavoritesOnly(!favoritesOnly)}
        >
          ★ Favorites
        </button>
        <label>
          <span>Sort services</span>
          <select
            aria-label="Sort services"
            value={sort}
            onChange={(e) => setSort(e.target.value)}
          >
            <option value="name">Name (A–Z)</option>
            <option value="recent">Recent activity</option>
          </select>
        </label>
        <div className="ws-view-toggle">
          <button
            aria-label="Grid view"
            aria-pressed={view === "grid"}
            onClick={() => chooseView("grid")}
          >
            ⊞
          </button>
          <button
            aria-label="List view"
            aria-pressed={view === "list"}
            onClick={() => chooseView("list")}
          >
            ☰
          </button>
        </div>
      </div>
      <div className="ws-register-label">
        <span role="status" className="mono">
          Showing {shown.length} of {services.length} services
        </span>
        {search || environment || favoritesOnly ? (
          <button
            onClick={() => {
              setSearch("");
              setEnvironment("");
              setFavoritesOnly(false);
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
                          <span className="ws-connection">
                            {s.healthcheck_url
                              ? s.is_monitored !== false
                                ? "Monitored"
                                : "Paused"
                              : "Not configured"}
                          </span>
                        </div>
                        <div>
                          <small>Health</small>
                          <HealthStatus
                            health={s.monitoring_status || "unknown"}
                          />
                        </div>
                        <div>
                          <small>Active incidents</small>
                          <span className="mono">
                            {s.active_incident_count ?? "—"}
                          </span>
                          <small>Across all incident records</small>
                        </div>
                        <div>
                          <small>Registered</small>
                          <span className="mono">
                            {s.created_at.slice(0, 10)} UTC
                          </span>
                        </div>
                        <ApplicationActions service={s} />
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
                  <ApplicationActions service={s} />
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
                          {
                            id: s.id,
                            name: s.name,
                            health:
                              (s.monitoring_status as Health) || "unknown",
                          },
                        ],
                      }}
                    />
                  </div>
                )}
                <div className="ws-card-status">
                  <span className="ws-connection">
                    {s.healthcheck_url
                      ? `Connection: ${s.monitoring_status || "configured"}`
                      : "Connection: not configured"}
                  </span>
                  <HealthStatus health={s.monitoring_status || "unknown"} />
                </div>
                <div className="ws-card-counts">
                  <span>
                    <b>01</b> service
                  </span>
                  <span>
                    {s.active_incident_count == null
                      ? "Incident count unavailable"
                      : `${s.active_incident_count} active incidents`}
                  </span>
                  <span className="ws-open-arrow" aria-hidden="true">
                    ↗
                  </span>
                </div>
                <div className="ws-card-signal">
                  <span className="mono">REGISTRATION / {s.status}</span>
                  <p>
                    {s.current_version
                      ? `Version ${s.current_version}`
                      : "Telemetry freshness is not reported."}
                  </p>
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
              ? "No matching applications"
              : "No applications connected yet."}
          </h3>
          <p>
            {services.length
              ? "Adjust your search or filters."
              : "Connect your first application to begin organizing its operational data and incident investigations."}
          </p>
          {services.length ? (
            <button
              onClick={() => {
                setSearch("");
                setEnvironment("");
                setFavoritesOnly(false);
              }}
            >
              Clear filters
            </button>
          ) : (
            <Link className="ws-button ws-primary" href="/onboarding">
              Connect Your First Application →
            </Link>
          )}
        </div>
      )}
    </section>
  );
}
