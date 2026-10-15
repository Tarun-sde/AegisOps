"use client";
import { useRef, useState } from "react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { useGSAP } from "@gsap/react";
import { useSceneEntrances } from "./scene-entrances";
import { workflowScene } from "./motion-scenes";
import { Hero } from "./hero";
import { Mark } from "./artwork";
import {
  SystemElevation as Elevation,
  ServiceFabric as Pavilion,
  IncidentPlan as FloorPlan,
} from "./system-artwork";
import { ArrowLink, PageLink, useSiteScroll } from "./site-shell";
import { ProductPreview } from "./product-preview";
import { FinalCTA, Footer } from "./footer";

gsap.registerPlugin(ScrollTrigger, useGSAP);
export function SectionLabel({
  children,
  number,
}: {
  children: React.ReactNode;
  number: string;
}) {
  return (
    <div className="section-label mono">
      <span>{children}</span>
      <span>[{number}]</span>
    </div>
  );
}
const technologies = [
  {
    name: "OpenTelemetry",
    icon: (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <circle cx="7" cy="12" r="2.5" />
        <circle cx="17" cy="12" r="2.5" />
        <path d="M9.5 12h5" />
        <path d="M4.5 7.5a9 9 0 0 1 15 0M4.5 16.5a9 9 0 0 0 15 0" />
      </svg>
    ),
  },
  {
    name: "Prometheus",
    icon: (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <path d="M12 2C9.5 5 7.5 7.5 7.5 11a4.5 4.5 0 0 0 9 0c0-1.8-.8-3.2-1.8-4.5-.4 1.2-1.2 2-2.2 2 .5-2 1-3.5-.5-6.5z" />
        <path d="M5 17h14M7 21h10" />
      </svg>
    ),
  },
  {
    name: "Loki",
    icon: (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <path d="M4 6h16M4 12h10M4 18h16" />
        <circle cx="17.5" cy="12" r="2.5" />
        <path d="M19.5 14l2 2" />
      </svg>
    ),
  },
  {
    name: "Tempo",
    icon: (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <path d="M3 7h8M7 12h10M11 17h10" />
        <circle cx="3" cy="7" r="1.5" fill="currentColor" />
        <circle cx="7" cy="12" r="1.5" fill="currentColor" />
        <circle cx="11" cy="17" r="1.5" fill="currentColor" />
      </svg>
    ),
  },
  {
    name: "Google ADK",
    icon: (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <path d="M12 2C12 7.5 7.5 12 2 12C7.5 12 12 16.5 12 22C12 16.5 16.5 12 22 12C16.5 12 12 7.5 12 2Z" />
        <circle cx="12" cy="12" r="2" fill="currentColor" />
      </svg>
    ),
  },
  {
    name: "PostgreSQL",
    icon: (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <ellipse cx="12" cy="6" rx="8" ry="3" />
        <path d="M4 6v6c0 1.66 3.58 3 8 3s8-1.34 8-3V6" />
        <path d="M4 12v6c0 1.66 3.58 3 8 3s8-1.34 8-3v-6" />
      </svg>
    ),
  },
];

export function PracticeStrip() {
  return (
    <div
      className="practice-strip"
      aria-label="Technologies used in the AegisOps telemetry and investigation stack"
    >
      {technologies.map((tech, i) => (
        <div key={tech.name}>
          <span className={`practice-glyph glyph-${i}`} aria-hidden="true">
            {tech.icon}
          </span>
          <span>{tech.name}</span>
        </div>
      ))}
    </div>
  );
}
const phases = [
  {
    name: "Observe",
    title: "A second pair of eyes.<br/>Across your applications.",
    body: "Connect application metrics, logs and traces. Deterministic monitoring detects anomalies while investigation gathers scoped telemetry context.",
    tag: "OBSERVE / TELEMETRY CONTEXT",
    code: "ILLUSTRATIVE SIGNAL",
    detail: "Metrics · Logs · Traces · Incident history",
  },
  {
    name: "Advise",
    title: "From alert to evidence.<br/>Across your stack.",
    body: "AegisOps uses scoped investigation tools to examine relevant metrics, logs, traces and operational context. Missing evidence stays visible; inconclusive is a valid result.",
    tag: "ADVISE / EVIDENCE BEFORE ACTION",
    code: "SCOPED EVIDENCE",
    detail: "Inspect citations / Review limitations",
  },
  {
    name: "Act",
    title: "Intelligence suggests.<br/>Operators decide.",
    body: "AegisOps separates AI-generated proposals from authorized remediation execution. Approval, staging execution and recovery verification are separate backend-controlled steps.",
    tag: "EXACT PAYLOAD / HUMAN REVIEW",
    code: "STAGING ACTION",
    detail: "Approval does not execute / Verify recovery separately",
  },
  {
    name: "Learn",
    title: "Turn incident history<br/>into useful context.",
    body: "Retain persisted investigation results, auditable human decisions and runbook retrieval for future operational clarity. No automatic model retraining is claimed.",
    tag: "LEARN / RETAIN CONTEXT",
    code: "RUNBOOK CONTEXT",
    detail: "Incident history · Runbooks · Evaluation feedback",
  },
];
function ModelWorkflow() {
  const scrollTo = useSiteScroll();
  const ref = useRef<HTMLElement>(null),
    trigger = useRef<ScrollTrigger | null>(null),
    lastPhase = useRef(0),
    mobileScene = useRef<gsap.core.Timeline | null>(null),
    mobileTween = useRef<gsap.core.Tween | null>(null);
  const [active, setActive] = useState(0);
  useGSAP(
    () => {
      const media = gsap.matchMedia();
      media.add(
        "(min-width: 992px) and (prefers-reduced-motion: no-preference)",
        () => {
          const cards = gsap.utils.toArray<HTMLElement>(".workflow-copy");
          gsap.set(cards.slice(1), { autoAlpha: 0, y: 24 });
          const tl = gsap.timeline({
            scrollTrigger: {
              trigger: ref.current,
              start: () =>
                `top top+=${document.querySelector("header")!.offsetHeight + 8}`,
              end: () => `+=${innerHeight * 6}`,
              pin: true,
              pinSpacing: false,
              scrub: 1,
              invalidateOnRefresh: true,
              onUpdate: (self) => {
                const phase = Math.min(3, Math.floor(self.progress * 4));
                if (lastPhase.current !== phase) {
                  lastPhase.current = phase;
                  setActive(phase);
                }
              },
            },
          });
          trigger.current = tl.scrollTrigger!;
          tl.add(workflowScene(ref.current!), 0);
          for (let i = 1; i < 4; i++) {
            tl.to(cards[i - 1], { autoAlpha: 0, y: -24, duration: 0.15 }, i).to(
              cards[i],
              { autoAlpha: 1, y: 0, duration: 0.2 },
              i + 0.02,
            );
          }
          return () => {
            trigger.current = null;
          };
        },
      );
      media.add("(max-width: 991px), (prefers-reduced-motion: reduce)", () => {
        mobileScene.current = workflowScene(ref.current!).pause(0.8);
        return () => {
          mobileTween.current?.kill();
          mobileScene.current = null;
        };
      });
      return () => media.revert();
    },
    { scope: ref },
  );
  const goTo = (index: number) => {
    if (trigger.current) {
      scrollTo(
        trigger.current.start +
          ((index + 0.85) / 4) * (trigger.current.end - trigger.current.start),
      );
    } else if (mobileScene.current) {
      mobileTween.current?.kill();
      setActive(index);
      if (matchMedia("(prefers-reduced-motion: reduce)").matches)
        mobileScene.current.time(index + 0.85);
      else
        mobileTween.current = mobileScene.current.tweenTo(index + 0.85, {
          duration: 0.85,
          ease: "power2.inOut",
        });
    }
  };
  return (
    <div className="workflow-track">
      <section
        ref={ref}
        className="model-workflow technical-corners"
        id="how-it-works"
      >
        <div id="workflow" className="sr-only" aria-hidden="true" />
        <div className="workflow-heading">
          <SectionLabel number="03">
            RIGHT THERE WITH YOU / THROUGH THE INCIDENT
          </SectionLabel>
          <h2>
            Investigate incidents
            <br />
            with evidence
          </h2>
        </div>
        <div className="workflow-body">
          <div className="workflow-drawing drafting-grid">
            <FloorPlan narrative />
            <div className="scan-line" />
            <div className="workflow-alert mono">
              <b>01 / EVIDENCE SIGNAL</b>
              <span>
                TRACE-DEMO-042
                <br />
                DB LATENCY / 720ms
              </span>
            </div>
            <div className="geometry-fix mono">
              PROPOSED RESTART / AWAITING APPROVAL
            </div>
            <div className="learned-standard mono">
              INCIDENT / EVIDENCE / RUNBOOK LINKED
            </div>
            <span className="drawing-index mono">
              INC-DEMO-042 / ILLUSTRATIVE / NO ACTION EXECUTED
            </span>
          </div>
          <div className="workflow-copy-stack">
            {phases.map((phase, i) => (
              <article
                className="workflow-copy"
                key={phase.name}
                aria-label={`${phase.name} phase`}
              >
                <span className="eyebrow">
                  [0{i + 1}] {phase.name}
                </span>
                <h3>
                  {phase.title.split("<br/>").map((text, n) => (
                    <span key={text}>
                      {n > 0 && <br />}
                      {text}
                    </span>
                  ))}
                </h3>
                <p>{phase.body}</p>
                <div className={`workflow-status ${i === 1 ? "warning" : ""}`}>
                  <span className="mono">{phase.tag}</span>
                  <strong>{phase.code}</strong>
                  <p>{phase.detail}</p>
                </div>
                <span className="mono scroll-hint">[SCROLL TO CONTINUE] ↓</span>
              </article>
            ))}
          </div>
        </div>
        <div className="phase-nav">
          {phases.map((phase, i) => (
            <button
              key={phase.name}
              onClick={() => goTo(i)}
              aria-pressed={active === i}
            >
              <span className="mono">[0{i + 1}]</span>
              {phase.name}
              <span>↗</span>
            </button>
          ))}
        </div>
      </section>
    </div>
  );
}
function Platforms() {
  const [tool, setTool] = useState("Metrics");
  const ref = useRef<HTMLElement>(null);
  useGSAP(
    () => {
      const media = gsap.matchMedia();
      media.add("(prefers-reduced-motion: no-preference)", () => {
        const tl = gsap.timeline();
        tl.fromTo(
          ".platform-plan .plan-dimensions",
          { scaleX: 0.7, opacity: 0.2, transformOrigin: "center" },
          { scaleX: 1, opacity: 1, duration: 0.55 },
        )
          .fromTo(
            ".platform-plan .plan-labels text",
            { y: 7, opacity: 0 },
            { y: 0, opacity: 1, stagger: 0.025, duration: 0.3 },
            0.15,
          )
          .fromTo(
            ".platform-plan .plan-alert",
            { scaleY: 0, transformOrigin: "top" },
            {
              scaleY: tool === "Metrics" || tool === "Traces" ? 1 : 0,
              duration: 0.5,
            },
            0,
          );
      });
      return () => media.revert();
    },
    { scope: ref, dependencies: [tool], revertOnUpdate: true },
  );
  return (
    <section ref={ref} id="platforms" className="platform-section">
      <div className="platform-main">
        <div
          className={`platform-plan tool-${tool.toLowerCase()} drafting-grid`}
          role="tabpanel"
          id="platform-panel"
          aria-labelledby={`tool-${tool}`}
        >
          <FloorPlan highlight />
          <span className="viewport-badge mono">
            {tool.toUpperCase()} /{" "}
            {tool === "Logs"
              ? "REDACTED EVENTS"
              : tool === "Context"
                ? "RUNBOOK CONTEXT"
                : "INC-DEMO-042 · SAMPLE"}
          </span>
        </div>
        <div className="platform-copy">
          <span className="eyebrow">
            YOUR SIGNALS. YOUR CONTEXT. CONNECTED.
          </span>
          <h2>
            Intelligence across
            <br />
            the tools you know.
          </h2>
          <p>
            AegisOps reads scoped telemetry. It connects metrics, logs and
            traces to incidents, with evidence and limitations shown alongside
            every hypothesis.
          </p>
          <div
            className="platform-tabs"
            role="tablist"
            aria-label="Telemetry signal"
          >
            {["Metrics", "Logs", "Traces", "Context"].map((name, i) => (
              <button
                id={`tool-${name}`}
                key={name}
                role="tab"
                aria-selected={tool === name}
                aria-controls="platform-panel"
                tabIndex={tool === name ? 0 : -1}
                onClick={() => setTool(name)}
                onKeyDown={(e) => {
                  const names = ["Metrics", "Logs", "Traces", "Context"];
                  if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
                    e.preventDefault();
                    const next =
                      names[(i + (e.key === "ArrowRight" ? 1 : 3)) % 4];
                    setTool(next);
                    document.getElementById(`tool-${next}`)?.focus();
                  }
                }}
              >
                {name}
              </button>
            ))}
          </div>
          <ul className="capabilities">
            <li>
              Connects telemetry and incident context.<span>⌖</span>
            </li>
            <li>
              Cites evidence for review.<span>✳</span>
            </li>
            <li>
              Staging actions require approval.<span>⊕</span>
            </li>
          </ul>
        </div>
      </div>
      <div className="product-row">
        <div>
          <span className="eyebrow">[01]</span>
          <h3>Investigation Review</h3>
        </div>
        <ProductPreview variant={1} />
        <div>
          <p>
            An investigation grounded in your service context. Inspect the
            evidence, review a proposal, and decide the next step.
          </p>
          <ArrowLink href="/platform#features" external>
            Learn more
          </ArrowLink>
        </div>
      </div>
      <div className="product-row">
        <div>
          <span className="eyebrow">[02]</span>
          <h3>AegisOps Platform</h3>
        </div>
        <ProductPreview hero />
        <div>
          <p>
            Every service, persisted incident, and proposed action in one place.
            Review the evidence without losing the context.
          </p>
          <ArrowLink>Learn more</ArrowLink>
        </div>
      </div>
    </section>
  );
}
function WhyAegisOps() {
  const [active, setActive] = useState(0);
  const ref = useRef<HTMLElement>(null);
  useGSAP(
    () => {
      const duration = matchMedia("(prefers-reduced-motion: reduce)").matches
        ? 0
        : 0.65;
      gsap.to(".why-elevation", {
        opacity: active === 0 ? 1 : 0,
        duration,
        overwrite: true,
      });
      gsap.to(".why-plan", {
        opacity: active === 0 ? 0 : 1,
        duration,
        overwrite: true,
      });
      gsap.to(".why-plan .plan-alert, .why-plan .plan-issue-pins", {
        opacity: active === 1 ? 0.75 : 0,
        duration,
        overwrite: true,
      });
      gsap.to(".why-plan .editable-door", {
        attr: {
          d: active >= 2 ? "M423 191h54v54h-54" : "M423 191h-54v54h54",
        },
        duration,
        overwrite: true,
      });
      gsap.to(".why-plan .plan-labels", {
        opacity: active === 3 ? 1 : 0.4,
        duration,
        overwrite: true,
      });
    },
    { scope: ref, dependencies: [active] },
  );
  return (
    <section ref={ref} className="why-section" id="why">
      <div className="split-heading">
        <div>
          <span className="eyebrow">WHY US</span>
          <h2>
            Built to work
            <br />
            the way you do
          </h2>
        </div>
        <div>
          <p>
            AegisOps connects your monitoring to a reviewable investigation.
            Evidence stays visible, uncertainty stays explicit, and staging
            actions wait for authorized operators.
          </p>
          <span className="mono">[YOU STAY IN CONTROL]</span>
        </div>
      </div>
      <div className="why-content">
        <div className="drafting-grid why-art">
          <Elevation className="why-elevation" />
          <FloorPlan className="why-plan" highlight />
          <span className="why-art-label mono">{phases[active].tag}</span>
        </div>
        <div className="why-steps">
          {phases.map((phase, i) => (
            <div className={active === i ? "active" : ""} key={phase.name}>
              <button
                aria-expanded={active === i}
                aria-controls={`why-${i}`}
                onClick={() => setActive(i)}
              >
                <span>0{i + 1}</span>
                {phase.name}
                <span>↗</span>
              </button>
              <div id={`why-${i}`} hidden={active !== i}>
                <p>{phase.body}</p>
                <span className="mono">{phase.detail}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
const useCases = [
  [
    "On-call engineers",
    "Connect incident signals and keep your attention on the evidence.",
  ],
  [
    "Backend developers",
    "Inspect requests, dependencies and errors in service context.",
  ],
  [
    "Platform engineers",
    "Connect monitored services with scoped operational context.",
  ],
  ["SRE teams", "Review evidence-backed hypotheses with explicit limitations."],
  [
    "Service owners",
    "Keep investigation records linked to their service and evidence.",
  ],
  [
    "Incident reviewers",
    "Review the exact proposal before authorizing staging changes.",
  ],
  [
    "Engineering leads",
    "Retain auditable decisions and relevant operational runbooks.",
  ],
  [
    "Small teams",
    "Use a bounded investigation workflow without losing human control.",
  ],
];
function UseCases() {
  const [active, setActive] = useState<number | null>(0);
  return (
    <section className="use-cases" id="use-cases">
      <div className="use-case-art">
        <Pavilion />
      </div>
      <div className="use-case-copy">
        <span className="eyebrow">USE CASES</span>
        <h2>
          Made for
          <br />
          the people on
          <br />
          the call
        </h2>
        <div className="use-case-list">
          {useCases.map(([title, body], i) => (
            <div key={title}>
              <button
                aria-expanded={active === i}
                aria-controls={`persona-${i}`}
                onClick={() => setActive(active === i ? null : i)}
              >
                {title}
                <span>{active === i ? "−" : "+"}</span>
              </button>
              <p id={`persona-${i}`} hidden={active !== i}>
                {body}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
export function HomePage() {
  const root = useRef<HTMLElement>(null);
  useSceneEntrances(root);
  return (
    <main id="main" ref={root}>
      <Hero />
      <section className="intro" id="about">
        <SectionLabel number="01">MORE CONTEXT. LESS GUESSWORK.</SectionLabel>
        <div className="intro-statement">
          <Mark />
          <h2>
            Incident triage shouldn’t scatter your attention.{" "}
            <span>
              AegisOps connects the signals and cites the evidence so you can
              understand failures and make informed decisions.
            </span>
          </h2>
          <ArrowLink>Explore incident intelligence</ArrowLink>
        </div>
        <div className="intro-baseline mono">
          <span>BUILT FOR APPLICATION OPERATIONS</span>
          <span>HUMAN JUDGMENT / SCOPED EVIDENCE</span>
        </div>
      </section>
      <PracticeStrip />
      <section className="problem-section">
        <div className="split-heading">
          <div>
            <span className="eyebrow">PROBLEMS / [02]</span>
            <h2>
              Your signals tell
              <br />
              parts of the story,
              <br />
              not the whole picture
            </h2>
          </div>
          <p>
            Monitoring detects symptoms. Understanding the incident still means
            joining metrics, logs, traces and changes. That context should stay
            connected throughout the investigation.
          </p>
        </div>
        <div className="problem-grid">
          {[
            [
              "Manual",
              "Every signal<br/>needs context",
              "Metrics, logs and traces. Each useful, but only part of the incident.",
            ],
            [
              "Disjointed",
              "AI answers need<br/>verifiable evidence",
              "A plausible explanation is not proof. Inspect the sources and missing context.",
            ],
            [
              "Blind",
              "Missing context<br/>hides uncertainty",
              "Keep gaps visible. An inconclusive investigation is a valid result.",
            ],
            [
              "Slow",
              "Every action<br/>needs control",
              "Review exact parameters. Approval, execution and recovery are separate steps.",
            ],
          ].map(([label, title, body], i) => (
            <article key={label}>
              <SectionLabel number={`0${i + 1}`}>{label}</SectionLabel>
              <div
                className={`problem-graphic graphic-${i}`}
                aria-hidden="true"
              >
                {i === 0 ? (
                  <FloorPlan />
                ) : i === 1 ? (
                  <>
                    <Mark />
                    <span>↔</span>
                    <Mark />
                  </>
                ) : i === 2 ? (
                  <div className="target-diagram">
                    <span>+</span>
                  </div>
                ) : (
                  <div className="clock-diagram">
                    <span />
                  </div>
                )}
              </div>
              <h3>
                {title.split("<br/>").map((line, n) => (
                  <span key={line}>
                    {n > 0 && <br />}
                    {line}
                  </span>
                ))}
              </h3>
              <p>{body}</p>
            </article>
          ))}
        </div>
      </section>
      <ModelWorkflow />
      <Platforms />
      <WhyAegisOps />
      <UseCases />
      <FinalCTA />
      <Footer />
      <PageLink href="/platform" className="sr-only">
        Explore AegisOps Platform
      </PageLink>
    </main>
  );
}
