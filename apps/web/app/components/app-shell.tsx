"use client";
import {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import gsap from "gsap";
import { useGSAP } from "@gsap/react";
import { AuthProvider, useAuth } from "../lib/auth-context";
import { getServices, type Service } from "../lib/api";
import { AegisMark } from "./project-visuals";
import { Selector } from "./selector";
import { keepDialogFocus } from "./dialog-focus";
import { SiteShell, PageLink } from "./marketing/site-shell";
import "../workspace-redesign.css";
const Favorites = createContext({
  pinned: [] as string[],
  toggle: (_id: string) => {
    void _id;
  },
});
export const useFavorites = () => useContext(Favorites);
const links = [
  ["/app", "Applications", "⊞"],
  ["/app/incidents", "Incidents", "△"],
  ["/app/runbooks", "Runbooks", "≋"],
  ["/app/proposals", "Proposals", "⋈"],
  ["/app/simulation-lab", "Simulation Lab", "⌖"],
];
function WorkspaceShell({ children }: { children: ReactNode }) {
  const path = usePathname(),
    router = useRouter();
  const { activeOrg, role, user, organizations, loading, logout } = useAuth();
  const [error, setError] = useState<string | null>(null),
    [collapsed, setCollapsed] = useState(false),
    [pinned, setPinned] = useState<string[]>([]),
    [services, setServices] = useState<Service[]>([]);
  const preferenceKey =
    user && activeOrg ? `aegisops:${user.id}:${activeOrg.id}:favorites` : null;
  useEffect(() => {
    try {
      const saved: unknown = preferenceKey
        ? JSON.parse(localStorage.getItem(preferenceKey) ?? "[]")
        : [];
      setPinned(
        Array.isArray(saved)
          ? saved.filter((id): id is string => typeof id === "string")
          : [],
      );
    } catch {
      setPinned([]);
    }
  }, [preferenceKey]);
  const drawer = useRef<HTMLDialogElement>(null),
    root = useRef<HTMLDivElement>(null);
  useEffect(() => {
    let active = true;
    getServices().then((r) => {
      if (active) setServices(r.data ?? []);
    });
    return () => {
      active = false;
    };
  }, [activeOrg?.id, path]);
  useEffect(() => {
    drawer.current?.close();
  }, [path]);
  const search = () => {
    drawer.current?.close();
    const input = document.querySelector<HTMLInputElement>("#project-search");
    if (input) {
      input.focus();
      input.select();
    } else router.push("/app#project-search");
  };
  useEffect(() => {
    const shortcut = (event: KeyboardEvent) => {
      if (
        event.key.toLowerCase() !== "f" ||
        event.ctrlKey ||
        event.metaKey ||
        event.altKey ||
        event.shiftKey ||
        (event.target as Element)?.closest(
          "input,textarea,select,[contenteditable],[role=combobox]",
        ) ||
        document.querySelector("dialog[open]")
      )
        return;
      event.preventDefault();
      const input = document.querySelector<HTMLInputElement>("#project-search");
      if (input) {
        input.focus();
        input.select();
      } else router.push("/app#project-search");
    };
    document.addEventListener("keydown", shortcut);
    return () => document.removeEventListener("keydown", shortcut);
  }, [router]);
  useGSAP(
    () => {
      const media = gsap.matchMedia();
      media.add("(prefers-reduced-motion: no-preference)", () => {
        const targets = root.current?.querySelectorAll(
          ".ws-page-heading h1, .ws-project-card",
        );
        if (!targets?.length) return;
        gsap.fromTo(targets, { y: 6 }, { y: 0, duration: 0.22, stagger: 0.02 });
      });
      return () => media.revert();
    },
    { scope: root, dependencies: [path], revertOnUpdate: true },
  );
  const current = services.find((s) => path === `/app/services/${s.id}`);
  const navigation = (
    <>
      <Selector
        label="Workspace"
        value={
          loading
            ? "Loading organization…"
            : (activeOrg?.name ?? "Session required")
        }
        options={
          organizations && organizations.length > 0
            ? organizations.map((org) => ({
                id: org.id,
                label: org.name,
                description:
                  org.id === activeOrg?.id
                    ? `${role} · Active organization`
                    : "Switch to this organization",
                selected: org.id === activeOrg?.id,
                action: () => {
                  if (org.id !== activeOrg?.id) {
                    if (typeof window !== "undefined") {
                      localStorage.setItem("aegisops_active_org", org.id);
                      document.cookie = `aegisops_active_org=${org.id}; path=/; max-age=31536000; SameSite=Lax`;
                      window.location.reload();
                    }
                  }
                },
              }))
            : activeOrg
              ? [
                  {
                    id: activeOrg.id,
                    label: activeOrg.name,
                    description: `${role} · Active authenticated organization`,
                    selected: true,
                    action: () => {},
                  },
                ]
              : [
                  {
                    id: "login",
                    label: "Sign in",
                    action: () => router.push("/login"),
                  },
                ]
        }
      />
      <button className="ws-find" onClick={search} title="Find applications">
        <span aria-hidden="true">⌕</span>
        <span className="ws-rail-label">Find applications</span>
        <kbd className="ws-rail-label">F</kbd>
      </button>
      <div className="ws-nav-caption mono ws-rail-label">
        WORKSPACE / {role ?? "NO SESSION"}
      </div>
      <nav className="ws-nav" aria-label="Workspace navigation">
        {links.map(([href, label, icon]) => (
          <Link
            key={href}
            href={href}
            title={label}
            aria-current={
              href === "/app"
                ? path === "/app" || path.startsWith("/app/services")
                  ? "page"
                  : undefined
                : path === href || path.startsWith(`${href}/`)
                  ? "page"
                  : undefined
            }
          >
            <span aria-hidden="true">{icon}</span>
            <span className="ws-rail-label">{label}</span>
            {href === "/app" && (
              <small className="ws-rail-label">
                {String(services.length).padStart(2, "0")}
              </small>
            )}
          </Link>
        ))}
      </nav>
      <div className="ws-sidebar-favorites ws-rail-label">
        <span className="mono">
          YOUR FAVORITES / {pinned.length.toString().padStart(2, "0")}
        </span>
        {pinned.length ? (
          services
            .filter((s) => pinned.includes(s.id))
            .map((s) => (
              <Link key={s.id} href={`/app/services/${s.id}`}>
                {s.name}
                <span>↗</span>
              </Link>
            ))
        ) : (
          <p>Favorite applications to keep them close.</p>
        )}
      </div>
    </>
  );
  const account = (
    <>
      {error && <p role="alert">{error}</p>}
      {user ? (
        <>
          <small className="ws-account-email">{user.email}</small>
          <button
            className="ws-button"
            onClick={async () => {
              try {
                await logout();
                window.location.assign("/login");
              } catch (e) {
                setError(e instanceof Error ? e.message : "Sign out failed");
              }
            }}
          >
            Sign out
          </button>
        </>
      ) : (
        <Link href="/login">Sign in</Link>
      )}
    </>
  );
  return (
    <Favorites.Provider
      value={{
        pinned,
        toggle: (id) =>
          setPinned((p) => {
            const next = p.includes(id)
              ? p.filter((v) => v !== id)
              : [...p, id];
            try {
              if (preferenceKey)
                localStorage.setItem(preferenceKey, JSON.stringify(next));
            } catch {
              /* Preferences remain usable without storage. */
            }
            return next;
          }),
      }}
    >
      <div
        ref={root}
        className={`workspace ${collapsed ? "ws-collapsed" : ""}`}
      >
        <aside className="ws-sidebar" data-lenis-prevent>
          <PageLink
            className="ws-brand"
            href="/"
            label="AegisOps — back to homepage"
          >
            <AegisMark />
            <span className="ws-rail-label">
              AEGISOPS<small>INCIDENT INTELLIGENCE</small>
            </span>
          </PageLink>
          <div className="ws-sidebar-content">{navigation}</div>
          <div className="ws-sidebar-bottom">
            <div className="ws-tenant-status ws-rail-label">
              <span className="mono">AEGISOPS STAGING</span>
              <p>
                Governed operational controls.
                <br />
                Production execution disabled.
              </p>
            </div>
            <div className="ws-rail-label">{account}</div>
            <button
              className="ws-collapse"
              aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
              aria-expanded={!collapsed}
              onClick={() => setCollapsed(!collapsed)}
            >
              <span aria-hidden="true">{collapsed ? "→" : "←"}</span>
              <span className="ws-rail-label">Collapse sidebar</span>
            </button>
          </div>
        </aside>
        <div className="ws-main-column">
          <header className="ws-context">
            <nav aria-label="Breadcrumb">
              <PageLink href="/">AegisOps</PageLink>
              <span>/</span>
              <PageLink href="/app">{activeOrg?.name ?? "Workspace"}</PageLink>
              {path === "/app" && (
                <>
                  <span>/</span>
                  <span aria-current="page">Applications</span>
                </>
              )}
              {path.startsWith("/app/services") && (
                <>
                  <span>/</span>
                  {current ? (
                    <>
                      <PageLink href="/app">Applications</PageLink>
                      <span>/</span>
                      <span aria-current="page">{current.name}</span>
                    </>
                  ) : (
                    <span aria-current="page">Applications</span>
                  )}
                </>
              )}
              {path.startsWith("/app/incidents") && (
                <>
                  <span>/</span>
                  <span aria-current="page">Incidents</span>
                </>
              )}
              {path.startsWith("/app/runbooks") && (
                <>
                  <span>/</span>
                  <span aria-current="page">Runbooks</span>
                </>
              )}
              {path.startsWith("/app/proposals") && (
                <>
                  <span>/</span>
                  <span aria-current="page">Proposals</span>
                </>
              )}
              {path.startsWith("/app/simulation-lab") && (
                <>
                  <span>/</span>
                  <span aria-current="page">Simulation Lab</span>
                </>
              )}
            </nav>
            <span className="ws-demo-label mono">
              {role ? `${role} / AUTHORIZED DATA` : "SESSION REQUIRED"}
            </span>
          </header>
          {children}
          <div className="ws-sheet-footer mono">
            <span>AEGISOPS / APPLICATION REGISTER</span>
            <span>PRODUCTION EXECUTION DISABLED</span>
          </div>
        </div>
        <nav className="ws-mobile-bar" aria-label="Mobile workspace actions">
          <button
            onClick={() => drawer.current?.showModal()}
            aria-label="Open workspace navigation"
          >
            ☰<span>Menu</span>
          </button>
          <Link href="/app">
            ⊞<span>Applications</span>
          </Link>
          <Link href="/app/incidents">
            △<span>Incidents</span>
          </Link>
          <Link href="/onboarding">
            ＋<span>Connect</span>
          </Link>
        </nav>
        {/* Native modal traps keyboard focus and delegates link activation. */}
        {/* eslint-disable-next-line jsx-a11y/no-noninteractive-element-interactions */}
        <dialog
          ref={drawer}
          className="ws-mobile-drawer"
          aria-label="Workspace navigation"
          onKeyDown={keepDialogFocus}
          data-lenis-prevent
          onClick={(e) => {
            if ((e.target as Element).closest("a")) drawer.current?.close();
          }}
        >
          <div className="ws-drawer-top">
            <span className="ws-brand">
              <AegisMark />
              AEGISOPS
            </span>
            <button
              aria-label="Close workspace navigation"
              onClick={() => drawer.current?.close()}
            >
              ×
            </button>
          </div>
          {navigation}
          {account}
        </dialog>
      </div>
    </Favorites.Provider>
  );
}
export function AppShell({ children }: { children: ReactNode }) {
  const path = usePathname();
  const operational = path.startsWith("/app") || path === "/onboarding";
  return (
    <SiteShell>
      {operational ? (
        <AuthProvider>
          <WorkspaceShell>{children}</WorkspaceShell>
        </AuthProvider>
      ) : (
        children
      )}
    </SiteShell>
  );
}
