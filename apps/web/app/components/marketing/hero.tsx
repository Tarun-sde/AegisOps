"use client";
import { useRef, useState, type PointerEvent } from "react";
import gsap from "gsap";
import { useGSAP } from "@gsap/react";
import { TopologyDrawing } from "./artwork";
import { ArrowLink } from "./site-shell";
import {
  drawingPoint,
  issues,
  overlaps,
  selectionBox,
  type Point,
} from "./geometry";

export function Hero() {
  const root = useRef<HTMLElement>(null);
  useGSAP(
    () => {
      const media = gsap.matchMedia();
      media.add("(prefers-reduced-motion: no-preference)", () => {
        const tl = gsap.timeline({
          paused: true,
          defaults: { ease: "power2.out" },
        });
        const paths = root.current!.querySelectorAll<SVGPathElement>(
          ".topology-structure > path",
        );
        paths.forEach((path) => {
          const length = path.getTotalLength();
          tl.fromTo(
            path,
            {
              strokeDasharray: length,
              strokeDashoffset: length,
              fillOpacity: 0,
            },
            { strokeDashoffset: 0, fillOpacity: 1, duration: 1.1 },
            0.18,
          );
        });
        tl.fromTo(
          ".topology-structure",
          { clipPath: "inset(0 100% 0 0)" },
          { clipPath: "inset(0 0% 0 0)", duration: 1.3 },
          0,
        )
          .fromTo(
            ".topology-guides",
            { scaleX: 0.15, transformOrigin: "50% 50%" },
            { scaleX: 1, duration: 1.1 },
            0.1,
          )
          .fromTo(
            ".topology-annotations text",
            { opacity: 0, y: 6 },
            { opacity: 1, y: 0, stagger: 0.07, duration: 0.45 },
            0.6,
          )
          .fromTo(
            ".hero-caption h1",
            { clipPath: "inset(0 0 100% 0)", y: 20 },
            { clipPath: "inset(0 0 0% 0)", y: 0, duration: 0.7 },
            0.4,
          )
          .fromTo(
            ".hero-metadata, .drawing-toolbar, .hero-description",
            { opacity: 0 },
            { opacity: 1, duration: 0.5, stagger: 0.1 },
            0.7,
          );
        let visited = false;
        try {
          visited = sessionStorage.getItem("aegisops-entered") === "1";
        } catch {
          /* Storage is optional. */
        }
        const play = () => {
          tl.play();
        };
        window.addEventListener("aegisops:entrance", play);
        if (
          visited ||
          document.documentElement.dataset.aegisopsEntered === "true"
        )
          tl.play();
        return () => window.removeEventListener("aegisops:entrance", play);
      });
      return () => media.revert();
    },
    { scope: root },
  );
  const svg = useRef<SVGSVGElement>(null),
    selection = useRef<SVGRectElement>(null),
    gradient = useRef<SVGLinearGradientElement>(null),
    coords = useRef<HTMLSpanElement>(null);
  const start = useRef<Point | null>(null),
    selected = useRef<number[]>([]);
  const [active, setActive] = useState<number[]>([]);
  const update = (next: number[]) => {
    if (selected.current.join() !== next.join()) {
      selected.current = next;
      setActive(next);
    }
  };
  const point = (event: PointerEvent<SVGSVGElement>) => {
    const rect = svg.current!.getBoundingClientRect();
    return drawingPoint(
      { x: event.clientX, y: event.clientY },
      { x: rect.x, y: rect.y, width: rect.width, height: rect.height },
    );
  };
  const move = (event: PointerEvent<SVGSVGElement>) => {
    const current = point(event);
    if (coords.current)
      coords.current.textContent = `X:${Math.round(current.x).toString().padStart(3, "0")} / Y:${Math.round(current.y).toString().padStart(3, "0")}`;
    if (!start.current) return;
    const box = selectionBox(start.current, current);
    for (const [key, value] of Object.entries(box))
      selection.current!.setAttribute(key, String(value));
    selection.current!.style.display = "block";
    gradient.current!.setAttribute(
      "x1",
      current.x >= start.current.x ? "0%" : "100%",
    );
    gradient.current!.setAttribute(
      "x2",
      current.x >= start.current.x ? "100%" : "0%",
    );
    gradient.current!.setAttribute(
      "y1",
      current.y >= start.current.y ? "0%" : "100%",
    );
    gradient.current!.setAttribute(
      "y2",
      current.y >= start.current.y ? "100%" : "0%",
    );
    update(
      issues.flatMap((issue, i) =>
        overlaps(box, {
          x: issue.x - 10,
          y: issue.y - 10,
          width: 20,
          height: 20,
        })
          ? [i]
          : [],
      ),
    );
  };
  const end = (event: PointerEvent<SVGSVGElement>) => {
    start.current = null;
    if (svg.current!.hasPointerCapture(event.pointerId))
      svg.current!.releasePointerCapture(event.pointerId);
    selection.current!.style.display = "none";
  };
  return (
    <section ref={root} className="hero" aria-labelledby="hero-title">
      <div className="hero-drawing technical-corners">
        <div className="hero-metadata mono">
          <span>
            FOCUS / EVIDENCE-LED INCIDENT INTELLIGENCE
            <br />
            ILLUSTRATIVE SAMPLE / NOT LIVE TELEMETRY
          </span>
          <span ref={coords}>X:000 / Y:000</span>
        </div>
        <svg
          ref={svg}
          className="interactive-elevation interactive-topology"
          viewBox="0 0 1000 620"
          aria-label="Illustrative Shop API request topology. Drag to inspect signals, or use Inspect scenario."
          onPointerDown={(event) => {
            if (
              event.pointerType === "touch" ||
              (event.target as Element).closest('[role="button"]')
            )
              return;
            start.current = point(event);
            svg.current!.setPointerCapture(event.pointerId);
            update([]);
          }}
          onPointerMove={move}
          onPointerUp={end}
          onPointerCancel={end}
        >
          <defs>
            <linearGradient ref={gradient} id="hero-selection">
              <stop stopColor="#b43e35" stopOpacity=".32" />
              <stop offset="1" stopColor="#b43e35" stopOpacity=".03" />
            </linearGradient>
          </defs>
          <TopologyDrawing inspected={active.length > 0} />
          <rect
            ref={selection}
            fill="url(#hero-selection)"
            stroke="#b43e35"
            strokeWidth=".8"
            style={{ display: "none" }}
            pointerEvents="none"
          />
          {issues.map((issue, i) => (
            <g
              key={issue.code}
              className={`issue-marker ${active.includes(i) ? "is-active" : ""}`}
              role="button"
              tabIndex={0}
              aria-label={`Inspect ${issue.title}`}
              aria-pressed={active.includes(i)}
              onClick={() =>
                update(
                  active.includes(i)
                    ? active.filter((n) => n !== i)
                    : [...active, i],
                )
              }
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  update(
                    active.includes(i)
                      ? active.filter((n) => n !== i)
                      : [...active, i],
                  );
                }
              }}
            >
              <rect
                className="marker-hit"
                x={issue.x - 20}
                y={issue.y - 20}
                width="40"
                height="40"
                fill="transparent"
              />
              <rect
                className="marker-pin"
                x={issue.x - 4}
                y={issue.y - 4}
                width="8"
                height="8"
              />
              <g className="issue-label" pointerEvents="none">
                <path
                  d={`M${issue.x} ${issue.y}v-24h35`}
                  fill="none"
                  stroke="#b43e35"
                />
                <rect
                  x={issue.x + 28}
                  y={issue.y - 59}
                  width="161"
                  height="37"
                  fill="#b43e35"
                />
                <text x={issue.x + 36} y={issue.y - 45}>
                  {issue.code}
                </text>
                <text x={issue.x + 36} y={issue.y - 31}>
                  {issue.short}
                </text>
              </g>
            </g>
          ))}
        </svg>
        <div className="drawing-toolbar mono">
          <span className="drag-instruction">
            ⌖ &nbsp; CLICK AND DRAG TO INSPECT SIGNALS
          </span>
          <button
            onClick={() =>
              update(active.length === issues.length ? [] : [0, 1, 2])
            }
          >
            {active.length === issues.length
              ? "Clear inspection"
              : "Inspect scenario"}{" "}
            <span>↗</span>
          </button>
          <span>INC-DEMO-042 / SAMPLE TOPOLOGY</span>
        </div>
      </div>
      {active.length > 0 && (
        <aside
          className="hero-inspection"
          aria-label="Sample incident inspection"
        >
          <h2>INC-DEMO-042 / Illustrative incident</h2>
          <p>
            Shop API · p95 840 ms · database span 720 ms. Hypothesis: a slow
            database dependency. Pool saturation is unconfirmed. No action
            executed.
          </p>
        </aside>
      )}
      <div className="hero-caption">
        <h1 id="hero-title">
          An AI agent that works <br />
          across your applications
        </h1>
        <div className="hero-description">
          <p>
            AegisOps connects telemetry, investigates incidents, and cites
            evidence. You review every proposal. Staging actions need explicit
            approval and separate recovery checks.
          </p>
          <div className="mono hero-benefits">
            <span>+ SCOPED EVIDENCE</span>
            <span>+ GOVERNED ACTIONS</span>
            <span>+ AUDITABLE HISTORY</span>
          </div>
        </div>
        <ArrowLink href="/platform">Explore the platform</ArrowLink>
      </div>
      <p className="sr-only" role="status">
        {active.length
          ? `${active.length} issues selected. ${active.map((i) => issues[i].title).join(". ")}`
          : "No issues selected."}
      </p>
    </section>
  );
}
