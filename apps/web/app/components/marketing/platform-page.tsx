"use client";
import { useRef, useState } from "react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { useGSAP } from "@gsap/react";
import { useSceneEntrances } from "./scene-entrances";
import { featureScene } from "./motion-scenes";
import { ArrowLink, useSiteScroll } from "./site-shell";
import { PracticeStrip } from "./home-page";
import { ProductPreview, featureNames } from "./product-preview";
import { IncidentPlan } from "./system-artwork";
import { FinalCTA, Footer } from "./footer";

const features = [
  [
    "Every service in<br/>one place",
    "Review registered services and persisted incidents together. This public preview is illustrative; your workspace uses authorized account data.",
  ],
  [
    "Review the action.<br/>Then decide.",
    "Inspect the exact staging payload. Approval, execution and recovery verification remain separate backend-controlled steps.",
  ],
  [
    "A record of<br/>every investigation",
    "Retain incident context, cited evidence and auditable decisions. Missing evidence and inconclusive results stay explicit.",
  ],
  [
    "Know what<br/>supports the claim",
    "Review scoped metrics, logs, traces and runbook references. Evidence supports a hypothesis; it does not guarantee a cause.",
  ],
  [
    "Keep useful context",
    "Retrieve relevant runbooks alongside persisted incident history. Records inform review; the model does not automatically retrain.",
  ],
];
function FeatureSequence() {
  const scrollTo = useSiteScroll();
  const ref = useRef<HTMLElement>(null),
    trigger = useRef<ScrollTrigger | null>(null),
    last = useRef(0);
  const [active, setActive] = useState(0);
  useGSAP(
    () => {
      const media = gsap.matchMedia();
      media.add(
        "(min-width: 992px) and (prefers-reduced-motion: no-preference)",
        () => {
          const panels = gsap.utils.toArray<HTMLElement>(".feature-panel");
          gsap.set(panels.slice(1), { autoAlpha: 0, yPercent: 12 });
          const tl = gsap.timeline({
            scrollTrigger: {
              trigger: ref.current,
              start: () =>
                `top top+=${document.querySelector("header")!.offsetHeight + 8}`,
              end: () => `+=${innerHeight * 4}`,
              pin: true,
              pinSpacing: false,
              scrub: 0.8,
              invalidateOnRefresh: true,
              onUpdate: (self) => {
                const next = Math.min(4, Math.floor(self.progress * 5));
                if (last.current !== next) {
                  last.current = next;
                  setActive(next);
                }
              },
            },
          });
          trigger.current = tl.scrollTrigger!;
          panels.forEach((panel, i) => {
            tl.add(featureScene(panel, i).timeScale(1.35), i + 0.08);
            if (i > 0) {
              tl.to(
                panels[i - 1],
                { autoAlpha: 0, yPercent: -5, duration: 0.22 },
                i,
              )
                .to(panel, { autoAlpha: 1, yPercent: 0, duration: 0.22 }, i)
                .to(
                  panels[i - 1].querySelector(".feature-copy"),
                  { opacity: 0, duration: 0.1 },
                  i,
                )
                .fromTo(
                  panel.querySelector(".feature-copy"),
                  { opacity: 0, clipPath: "inset(0 0 100% 0)" },
                  { opacity: 1, clipPath: "inset(0 0 0% 0)", duration: 0.18 },
                  i + 0.12,
                );
            }
          });
          tl.fromTo(
            ".feature-progress",
            { scaleX: 0 },
            { scaleX: 1, duration: 5, ease: "none" },
            0,
          );
          return () => {
            trigger.current = null;
          };
        },
      );
      media.add(
        "(max-width: 991px) and (prefers-reduced-motion: no-preference)",
        () => {
          ref
            .current!.querySelectorAll(".feature-panel")
            .forEach((panel, i) => {
              const scene = featureScene(panel, i);
              ScrollTrigger.create({
                trigger: panel.querySelector(".feature-visual"),
                start: "top 85%",
                end: "center 45%",
                scrub: 0.4,
                animation: scene,
                onEnter: () => setActive(i),
                onEnterBack: () => setActive(i),
                invalidateOnRefresh: true,
              });
            });
        },
      );
      return () => media.revert();
    },
    { scope: ref },
  );
  const select = (i: number) => {
    if (trigger.current)
      scrollTo(
        trigger.current.start +
          ((i + 0.85) / 5) * (trigger.current.end - trigger.current.start),
      );
    else {
      setActive(i);
      ref.current?.querySelectorAll(".feature-panel")[i]?.scrollIntoView({
        behavior: matchMedia("(prefers-reduced-motion: reduce)").matches
          ? "instant"
          : "smooth",
        block: "start",
      });
    }
  };
  return (
    <div className="feature-track">
      <section className="feature-sequence" id="features" ref={ref}>
        <div className="features-heading">
          <span className="eyebrow">KEY FEATURES</span>
          <h2>
            Full oversight, no
            <br />
            digging around
          </h2>
        </div>
        <nav className="feature-tabs" aria-label="Platform features">
          {featureNames.map((name, i) => (
            <button
              key={name}
              aria-pressed={active === i}
              onClick={() => select(i)}
            >
              <span className="mono">[0{i + 1}]</span>
              {name}
            </button>
          ))}
        </nav>
        <div className="feature-panels">
          {features.map(([title, body], i) => (
            <article className="feature-panel" key={title} id={`feature-${i}`}>
              <span className="feature-index mono">[0{i + 1}]</span>
              <div className="feature-copy">
                <span className="eyebrow">{featureNames[i]}</span>
                <h3>
                  {title.split("<br/>").map((line, n) => (
                    <span key={line}>
                      {n > 0 && <br />}
                      {line}
                    </span>
                  ))}
                </h3>
                <p>{body}</p>
              </div>
              <div className="feature-visual drafting-grid technical-corners">
                <ProductPreview variant={i} />
              </div>
            </article>
          ))}
        </div>
        <div
          className="feature-progress"
          style={{ transform: `scaleX(${(active + 1) / 5})` }}
        />
      </section>
    </div>
  );
}
const faqs = [
  [
    "Does AegisOps replace my monitoring tools?",
    "No. Prometheus, Alertmanager, Loki, Tempo and OpenTelemetry supply operational signals. AegisOps brings authorized context into an incident investigation and review workflow.",
  ],
  [
    "Is the topology live or automatically discovered?",
    "The public topology and product previews are an illustrative Shop API scenario. They do not query your account. Registered service and incident views use authorized backend data; unsupported telemetry is marked unavailable.",
  ],
  [
    "Can the AI execute production changes?",
    "No. The agent can propose allowlisted actions. A human must review the exact payload; a separate deterministic backend check controls staging execution. Production remediation is disabled.",
  ],
  [
    "Does every investigation find a root cause?",
    "No. Evidence can be missing or contradictory. Hypotheses stay qualified, and investigations may be inconclusive. Execution success does not prove recovery.",
  ],
  [
    "What does Learn mean?",
    "Retained incident history, decisions and runbooks provide context for future scoped investigations. It does not mean autonomous model training or an unmeasured improvement in accuracy.",
  ],
];
function FAQ() {
  const [open, setOpen] = useState<number | null>(null);
  return (
    <section className="faq-section" id="faq">
      <div>
        <span className="eyebrow">A FEW THINGS TO KNOW</span>
        <h2>
          Got questions?
          <br />
          We’ve got answers.
        </h2>
      </div>
      <div className="faq-list">
        {faqs.map(([q, a], i) => (
          <article key={q}>
            <button
              id={`faq-q-${i}`}
              aria-expanded={open === i}
              aria-controls={`faq-a-${i}`}
              onClick={() => setOpen(open === i ? null : i)}
            >
              {q}
              <span>{open === i ? "−" : "+"}</span>
            </button>
            <div
              id={`faq-a-${i}`}
              role="region"
              aria-labelledby={`faq-q-${i}`}
              className="faq-answer"
              hidden={open !== i}
            >
              <p>{a}</p>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
export function PlatformPage() {
  const root = useRef<HTMLElement>(null);
  useSceneEntrances(root);
  return (
    <main id="main" ref={root} className="dashboard-page">
      <section className="dashboard-hero">
        <div className="dashboard-hero-copy">
          <span className="eyebrow">AEGISOPS / INCIDENT INTELLIGENCE</span>
          <h1>
            From signal
            <br />
            to evidence.
            <br />
            From review
            <br />
            to response.
          </h1>
          <div className="dashboard-hero-bottom">
            <p>
              Monitor applications, investigate scoped evidence and review
              proposed staging actions. One incident record keeps the reasoning
              and human decisions connected.
            </p>
            <a href="#features" className="arrow-link">
              <span>Discover more</span>
              <span>↘</span>
            </a>
          </div>
        </div>
        <div className="dashboard-hero-art technical-corners">
          <ProductPreview hero />
          <span className="mono drawing-index">
            ILLUSTRATIVE SAMPLE / INC-DEMO-042
          </span>
        </div>
      </section>
      <PracticeStrip />
      <FeatureSequence />
      <section className="three-steps">
        <div className="split-heading">
          <h2>
            From evidence to a reviewed response.
            <br />
            In 3 steps.
          </h2>
          <div>
            <p>
              Keep the incident, its evidence and the approval boundary visible.
              Connect a service to begin the real workflow in your workspace.
            </p>
            <span className="mono">[SCROLL TO CONTINUE]</span>
          </div>
        </div>
        <div className="oversight-art drafting-grid">
          <IncidentPlan />
          <div className="oversight-product">
            <ProductPreview hero />
          </div>
        </div>
        <div className="steps-grid">
          {[
            [
              "Register<br/>your service",
              "Connect a service within your organization and configured telemetry scope.",
            ],
            [
              "Investigate<br/>scoped evidence",
              "Follow incident signals, citations and qualified hypotheses; inspect missing or contradictory evidence.",
            ],
            [
              "Review<br/>before execution",
              "Review the exact staging payload. Execute separately and verify observed recovery.",
            ],
          ].map(([title, body], i) => (
            <article key={title}>
              <div className="section-label mono">
                <span>STEP</span>
                <span>[0{i + 1}]</span>
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
      <FAQ />
      <FinalCTA />
      <Footer />
      <div className="sr-only">
        <ArrowLink />
      </div>
    </main>
  );
}
