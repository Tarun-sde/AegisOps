"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  createContext,
  useContext,
  useEffect,
  useRef,
  type ReactNode,
  type RefObject,
} from "react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { useGSAP } from "@gsap/react";
import Lenis from "lenis";
import { ServiceTopology, Mark } from "./artwork";

gsap.registerPlugin(ScrollTrigger, useGSAP);
const Navigation = createContext<(href: string) => void>(() => {});
const Scroll = createContext<(top: number) => void>(() => {});
export const useSiteNavigate = () => useContext(Navigation);
export const useSiteScroll = () => useContext(Scroll);
export function PageLink({
  href,
  children,
  className = "",
  label,
}: {
  href: string;
  children: ReactNode;
  className?: string;
  label?: string;
}) {
  const navigate = useContext(Navigation);
  return (
    <Link
      href={href}
      className={className}
      aria-label={label}
      onNavigate={(event) => {
        event.preventDefault();
        navigate(href);
      }}
    >
      {children}
    </Link>
  );
}
export function ArrowLink({
  href = "/app",
  children = "Discover more",
  external = false,
}: {
  href?: string;
  children?: ReactNode;
  external?: boolean;
}) {
  const content = (
    <>
      <span className="rolling-label">
        <span>{children}</span>
        <span aria-hidden="true">{children}</span>
      </span>
      <span aria-hidden="true">↗</span>
    </>
  );
  return external ? (
    <a className="arrow-link" href={href}>
      {content}
    </a>
  ) : (
    <PageLink className="arrow-link" href={href}>
      {content}
    </PageLink>
  );
}
function MotionClock({ lenisRef }: { lenisRef: RefObject<Lenis | null> }) {
  const path = usePathname();
  useEffect(() => {
    const media = gsap.matchMedia();
    media.add("(prefers-reduced-motion: no-preference)", () => {
      const lenis = new Lenis({ lerp: 0.1, smoothWheel: true, anchors: true });
      lenisRef.current = lenis;
      lenis.on("scroll", ScrollTrigger.update);
      const tick = (time: number) => lenis.raf(time * 1000);
      gsap.ticker.add(tick);
      gsap.ticker.lagSmoothing(0);
      return () => {
        gsap.ticker.remove(tick);
        lenis.destroy();
        lenisRef.current = null;
      };
    });
    const refresh = () => ScrollTrigger.refresh();
    document.fonts.ready.then(refresh);
    return () => media.revert();
  }, [path, lenisRef]);
  return null;
}
function Cursor() {
  const canvas = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const media = gsap.matchMedia();
    media.add(
      "(pointer: fine) and (prefers-reduced-motion: no-preference)",
      () => {
        const el = canvas.current!,
          ctx = el.getContext("2d");
        if (!ctx) return;
        let x = -100,
          y = -100,
          tx = -100,
          ty = -100,
          active = false,
          down = false;
        const trail: { x: number; y: number }[] = [];
        let color = "#282828";
        const size = () => {
          const dpr = Math.min(devicePixelRatio, 2);
          el.width = innerWidth * dpr;
          el.height = innerHeight * dpr;
          ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        };
        const tick = () => {
          const distance = Math.hypot(tx - x, ty - y);
          x += (tx - x) * 0.18;
          y += (ty - y) * 0.18;
          ctx.clearRect(0, 0, innerWidth, innerHeight);
          ctx.fillStyle = color;
          ctx.strokeStyle = color;
          if (distance > 2) trail.push({ x, y });
          else trail.shift();
          if (trail.length > 9) trail.shift();
          trail.forEach((point, index) => {
            ctx.globalAlpha = (index / trail.length) * 0.3;
            ctx.fillRect(point.x - 1, point.y - 1, 2, 2);
          });
          ctx.globalAlpha = 1;
          if (down) {
            ctx.strokeRect(x - 10, y - 10, 20, 20);
            ctx.beginPath();
            ctx.moveTo(x - 16, y);
            ctx.lineTo(x + 16, y);
            ctx.moveTo(x, y - 16);
            ctx.lineTo(x, y + 16);
            ctx.stroke();
          } else ctx.fillRect(x - 4.5, y - 4.5, 9, 9);
          if (distance < 0.05 && !trail.length) {
            gsap.ticker.remove(tick);
            active = false;
          }
        };
        const wake = () => {
          if (!active) {
            active = true;
            gsap.ticker.add(tick);
          }
        };
        const workspaceControl = (event: PointerEvent) =>
          location.pathname.startsWith("/app") &&
          (event.target as Element)?.closest("input, textarea, select, dialog");
        const move = (event: PointerEvent) => {
          if (workspaceControl(event)) {
            leave();
            return;
          }
          tx = event.clientX;
          ty = event.clientY;
          color = (event.target as Element)?.closest("[data-dark]")
            ? "#e0e0da"
            : "#282828";
          wake();
        };
        const press = (event: PointerEvent) => {
          if (workspaceControl(event)) return;
          down = true;
          wake();
        };
        const release = (event: PointerEvent) => {
          down = false;
          if (workspaceControl(event)) {
            leave();
            return;
          }
          wake();
        };
        const leave = () => {
          gsap.ticker.remove(tick);
          active = false;
          trail.length = 0;
          ctx.clearRect(0, 0, innerWidth, innerHeight);
        };
        size();
        window.addEventListener("resize", size);
        window.addEventListener("pointermove", move);
        window.addEventListener("pointerdown", press);
        window.addEventListener("pointerup", release);
        document.addEventListener("pointerleave", leave);
        return () => {
          leave();
          window.removeEventListener("resize", size);
          window.removeEventListener("pointermove", move);
          window.removeEventListener("pointerdown", press);
          window.removeEventListener("pointerup", release);
          document.removeEventListener("pointerleave", leave);
        };
      },
    );
    return () => media.revert();
  }, []);
  return <canvas className="custom-cursor" ref={canvas} aria-hidden="true" />;
}
function Preloader() {
  const ref = useRef<HTMLDivElement>(null);
  useGSAP(
    () => {
      let visited = false;
      try {
        visited = sessionStorage.getItem("aegisops-entered") === "1";
      } catch {
        /* Storage can be unavailable in private browser contexts. */
      }
      if (visited || matchMedia("(prefers-reduced-motion: reduce)").matches) {
        document.documentElement.dataset.aegisopsEntered = "true";
        gsap.set(ref.current, { display: "none" });
        return;
      }
      gsap.set(ref.current, { display: "flex" });
      const progress = { value: 0 },
        counter = ref.current!.querySelector("[data-counter]")!;
      const timeline = gsap.timeline({
        onComplete: () => {
          document.documentElement.classList.add("aegisops-skip-loader");
          try {
            sessionStorage.setItem("aegisops-entered", "1");
          } catch {
            /* Session storage is optional. */
          }
        },
      });
      timeline
        .to(
          progress,
          {
            value: 100,
            duration: 2.2,
            ease: "power1.inOut",
            onUpdate: () => {
              counter.textContent = `${Math.round(progress.value).toString().padStart(2, "0")}%`;
            },
          },
          0,
        )
        .fromTo(
          ".loader-line",
          { scaleX: 0 },
          { scaleX: 1, duration: 2.2, ease: "power1.inOut" },
          0,
        )
        .fromTo(
          ".loader-art path",
          { strokeDasharray: 1800, strokeDashoffset: 1800 },
          {
            strokeDashoffset: 0,
            duration: 1.6,
            stagger: { amount: 0.45 },
            ease: "power1.inOut",
          },
          0,
        )
        .call(() => {
          document.documentElement.dataset.aegisopsEntered = "true";
          window.dispatchEvent(new Event("aegisops:entrance"));
        })
        .to(ref.current, {
          clipPath: "inset(0 0 100% 0)",
          duration: 0.65,
          ease: "power3.inOut",
        })
        .set(ref.current, { display: "none" });
    },
    { scope: ref },
  );
  return (
    <div ref={ref} className="preloader" aria-hidden="true" data-dark>
      <div className="loader-meta mono">
        <span>AEGISOPS / VISUAL INTRO</span>
        <span>ILLUSTRATIVE / NO SYSTEM CONNECTION</span>
      </div>
      <ServiceTopology className="loader-art" />
      <div className="loader-progress">
        <span data-counter className="mono">
          00%
        </span>
        <div className="loader-line" />
      </div>
      <div className="loader-bottom">
        <h2>
          Evidence,
          <br />
          before action.
        </h2>
        <div className="ruler" />
        <span className="mono">
          EVIDENCE-LED SYSTEMS
          <br />
          EST. 2026 / REV 01
        </span>
      </div>
    </div>
  );
}
function Header() {
  const dialog = useRef<HTMLDialogElement>(null);
  const path = usePathname();
  const nav = (
    <>
      <PageLink
        href="/platform"
        className={`nav-link ${path === "/platform" ? "is-active" : ""}`}
      >
        Platform
      </PageLink>
      <a href="/#how-it-works" className="nav-link">
        How It Works
      </a>
      <a
        href="https://github.com/Tarun-sde/AegisOps"
        target="_blank"
        rel="noreferrer"
        className="nav-link nav-github"
      >
        GitHub <span aria-hidden="true">↗</span>
      </a>
      <a href="/login" className="nav-contact">
        Sign in <span aria-hidden="true">↗</span>
      </a>
      <PageLink href="/app" className="nav-workspace-cta" label="Workspace">
        Open Workspace <span aria-hidden="true">↗</span>
      </PageLink>
    </>
  );
  return (
    <>
      <header className="header">
        <PageLink href="/" className="wordmark" label="AegisOps home">
          <Mark />
          AEGISOPS
        </PageLink>
        <nav className="desktop-nav" aria-label="Main navigation">
          {nav}
        </nav>
        <button
          className="menu-toggle mono"
          onClick={() => dialog.current?.showModal()}
        >
          Menu <span>☰</span>
        </button>
      </header>
      <dialog
        className="mobile-menu"
        aria-label="Site navigation"
        ref={dialog}
        data-lenis-prevent
      >
        <div className="mobile-menu-top">
          <Mark />
          <span className="mono">NAVIGATION</span>
          <button
            aria-label="Close navigation"
            onClick={() => dialog.current?.close()}
          >
            ×
          </button>
        </div>
        {/* Link activation closes the native dialog for pointer and keyboard alike. */}
        {/* eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-noninteractive-element-interactions */}
        <nav
          aria-label="Mobile navigation"
          onClick={(event) => {
            if ((event.target as Element).closest("a")) dialog.current?.close();
          }}
        >
          <PageLink href="/">
            Home <span>↗</span>
          </PageLink>
          <PageLink href="/platform">
            Platform <span>↘</span>
          </PageLink>
          <a href="/#how-it-works">
            How It Works <span>↘</span>
          </a>
          <a
            href="https://github.com/Tarun-sde/AegisOps"
            target="_blank"
            rel="noreferrer"
          >
            GitHub <span>↗</span>
          </a>
          <a href="/login">
            Sign in <span>↗</span>
          </a>
          <PageLink href="/app">
            Open Workspace <span>↗</span>
          </PageLink>
        </nav>
        <ServiceTopology />
        <h2>An AI agent that works inside your operations</h2>
        <p>More time for the work that matters.</p>
      </dialog>
    </>
  );
}
export function SiteShell({ children }: { children: ReactNode }) {
  const router = useRouter(),
    path = usePathname(),
    curtain = useRef<HTMLDivElement>(null),
    busy = useRef(false);
  const workspace =
    path === "/app" || path.startsWith("/app/") || path === "/onboarding";
  const marketing = path === "/" || path === "/platform";
  const transition = useRef<gsap.core.Tween | null>(null);
  const lenisRef = useRef<Lenis | null>(null);
  const scrollTo = (top: number) => {
    if (lenisRef.current)
      lenisRef.current.scrollTo(top, { immediate: true, force: true });
    else window.scrollTo({ top, behavior: "instant" });
  };
  useGSAP(
    () => {
      busy.current = false;
      transition.current?.kill();
      if (curtain.current?.dataset.active === "true")
        transition.current = gsap.to(curtain.current, {
          scaleY: 0,
          transformOrigin: "top",
          duration: matchMedia("(prefers-reduced-motion: reduce)").matches
            ? 0
            : 0.55,
          ease: "power3.inOut",
          onComplete: () => {
            if (curtain.current) curtain.current.dataset.active = "false";
          },
        });
      return () => {
        transition.current?.kill();
      };
    },
    { dependencies: [path] },
  );
  const navigate = (href: string) => {
    if (href === path) {
      scrollTo(0);
      return;
    }
    if (new URL(href, location.origin).pathname === path) {
      router.push(href);
      return;
    }
    if (busy.current) return;
    busy.current = true;
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) {
      router.push(href);
      return;
    }
    curtain.current!.dataset.active = "true";
    transition.current = gsap.fromTo(
      curtain.current,
      { scaleY: 0, transformOrigin: "bottom" },
      {
        scaleY: 1,
        duration: 0.42,
        ease: "power3.inOut",
        onComplete: () => router.push(href),
      },
    );
  };
  return (
    <Navigation.Provider value={navigate}>
      <Scroll.Provider value={scrollTo}>
        {marketing && <MotionClock lenisRef={lenisRef} />}
        <a href="#main" className="skip-link">
          Skip to content
        </a>
        <div
          className={`site-frame ${marketing ? "marketing-surface" : workspace ? "operational-surface" : "auth-surface"}`}
        >
          {!workspace && <Header />}
          {children}
        </div>
        {marketing && <Cursor />}
        {marketing && <Preloader />}
        <div className="route-curtain" ref={curtain} aria-hidden="true">
          <Mark />
          <span className="mono">
            {workspace ? "AEGISOPS" : "AEGISOPS"} / CHANGING VIEW
          </span>
        </div>
      </Scroll.Provider>
    </Navigation.Provider>
  );
}
