import gsap from "gsap";

// Each scene belongs to its parent's context and clock; no timers or React frame state.
export function workflowScene(root: Element) {
  const q = gsap.utils.selector(root);
  const tl = gsap.timeline({ defaults: { ease: "none" } });
  tl.fromTo(
    q(".plan-dimensions"),
    { opacity: 0.15 },
    { opacity: 1, duration: 0.85 },
    0,
  )
    .fromTo(
      q(".plan-furniture"),
      { clipPath: "inset(0 0 100% 0)" },
      { clipPath: "inset(0 0 0% 0)", duration: 0.95 },
      0,
    )
    .fromTo(
      q(".plan-labels text"),
      { opacity: 0 },
      { opacity: 1, stagger: 0.055, duration: 0.25 },
      0.2,
    )
    .fromTo(
      q(".scan-line"),
      { y: 0, opacity: 0 },
      {
        y: () => root.querySelector(".workflow-drawing")!.clientHeight * 0.77,
        opacity: 1,
        duration: 0.95,
      },
      0,
    )
    .to(q(".scan-line"), { opacity: 0, duration: 0.12 }, 0.95)
    .fromTo(
      q(".plan-issue-pins rect"),
      { scale: 0, opacity: 0, transformOrigin: "center" },
      { scale: 1, opacity: 1, stagger: 0.08, duration: 0.18 },
      1,
    )
    .fromTo(
      q(".model-issue-frame, .model-leader"),
      { strokeDasharray: 1, strokeDashoffset: 1 },
      { strokeDashoffset: 0, stagger: 0.15, duration: 0.35 },
      1,
    )
    .fromTo(
      q(".model-clearance"),
      { opacity: 0 },
      { opacity: 1, duration: 0.25 },
      1.1,
    )
    .fromTo(
      q(".workflow-alert"),
      { clipPath: "inset(0 100% 0 0)" },
      { clipPath: "inset(0 0% 0 0)", duration: 0.3 },
      1.2,
    )
    .fromTo(
      q(".model-reticle"),
      { x: 550, y: 163, opacity: 0 },
      { x: 423, y: 191, opacity: 1, duration: 0.4 },
      1.6,
    )
    .to(
      q(".workflow-alert, .plan-issue-pins, .model-issue-frame, .model-leader"),
      { opacity: 0, duration: 0.2 },
      2,
    )
    .fromTo(
      q(".model-before"),
      { opacity: 0 },
      { opacity: 0.45, duration: 0.1 },
      2,
    )
    .to(
      q(".editable-door"),
      {
        attr: { d: "M423 191h54v54h-54" },
        stroke: "#282828",
        strokeWidth: 2.4,
        duration: 0.65,
      },
      2,
    )
    .to(q(".model-reticle"), { x: 477, y: 224, duration: 0.65 }, 2)
    .to(
      q(".model-clearance"),
      { attr: { x: 423 }, fill: "#626b5f", stroke: "#626b5f", duration: 0.65 },
      2,
    )
    .fromTo(
      q(".geometry-fix"),
      { clipPath: "inset(0 100% 0 0)" },
      { clipPath: "inset(0 0% 0 0)", duration: 0.3 },
      2.35,
    )
    .to(
      q(".model-before, .model-reticle, .geometry-fix"),
      { opacity: 0, duration: 0.25 },
      2.8,
    )
    .fromTo(
      q(".model-standard-route"),
      { strokeDasharray: 1, strokeDashoffset: 1 },
      { strokeDashoffset: 0, duration: 0.65 },
      3,
    )
    .fromTo(
      q(".model-standard-node"),
      { opacity: 0 },
      { opacity: 1, duration: 0.18, stagger: 0.2 },
      3.08,
    )
    .fromTo(
      q(".learned-standard"),
      { clipPath: "inset(0 100% 0 0)" },
      { clipPath: "inset(0 0% 0 0)", duration: 0.3 },
      3.4,
    )
    .to({}, { duration: 0.3 }, 3.7);
  return tl;
}

export function featureScene(root: Element, index: number) {
  const q = gsap.utils.selector(root);
  const tl = gsap.timeline({ defaults: { ease: "power1.inOut" } });
  if (index === 0) {
    tl.fromTo(
      q(".window-stack > div"),
      { y: 90, scaleX: 0.55, transformOrigin: "50% 100%" },
      { y: 0, scaleX: 1, stagger: 0.065, duration: 0.35 },
      0,
    )
      .fromTo(
        q(".front-window"),
        { yPercent: 25 },
        { yPercent: 0, duration: 0.5 },
        0.12,
      )
      .fromTo(
        q(".preview-stats > div"),
        { clipPath: "inset(0 0 100% 0)" },
        { clipPath: "inset(0 0 0% 0)", stagger: 0.04, duration: 0.22 },
        0.22,
      )
      .fromTo(
        q(".activity-row"),
        { xPercent: 10, opacity: 0 },
        { xPercent: 0, opacity: 1, stagger: 0.075, duration: 0.2 },
        0.35,
      );
  } else if (index === 1) {
    tl.fromTo(
      q(".plan-alert"),
      { scaleY: 0, transformOrigin: "50% 0%" },
      { scaleY: 1, duration: 0.45 },
      0,
    )
      .fromTo(
        q(".plan-dimensions"),
        { x: -18, opacity: 0.15 },
        { x: 0, opacity: 1, duration: 0.5 },
        0,
      )
      .fromTo(
        q(".approval-card"),
        { xPercent: 35, yPercent: 12 },
        { xPercent: 0, yPercent: 0, duration: 0.55 },
        0.12,
      )
      .fromTo(
        q(".approval-card > p, .approval-detail"),
        { clipPath: "inset(0 100% 0 0)" },
        { clipPath: "inset(0 0% 0 0)", duration: 0.3, stagger: 0.1 },
        0.4,
      );
  } else if (index === 2) {
    tl.fromTo(
      q(".history-spine"),
      { scaleY: 0, transformOrigin: "top" },
      { scaleY: 1, duration: 0.8 },
      0,
    )
      .fromTo(
        q(".history-event"),
        { x: 25, opacity: 0 },
        { x: 0, opacity: 1, stagger: 0.2, duration: 0.3 },
        0.1,
      )
      .fromTo(
        q(".editable-door"),
        { attr: { d: "M423 191h-54v54h54" } },
        { attr: { d: "M423 191h54v54h-54" }, duration: 0.5 },
        0.35,
      );
  } else if (index === 3) {
    tl.fromTo(
      q(".team-spine"),
      { scaleY: 0, transformOrigin: "top" },
      { scaleY: 1, duration: 0.8 },
      0,
    )
      .fromTo(
        q(".team-member"),
        { xPercent: 20 },
        { xPercent: 0, duration: 0.35, stagger: 0.12 },
        0.05,
      )
      .fromTo(
        q(".team-member > span:last-child"),
        { clipPath: "inset(0 100% 0 0)" },
        { clipPath: "inset(0 0% 0 0)", duration: 0.22, stagger: 0.12 },
        0.25,
      )
      .fromTo(
        q(".topology-guides"),
        { scaleX: 0.7, opacity: 0 },
        { scaleX: 1, opacity: 0.55, duration: 0.65 },
        0,
      );
  } else {
    tl.fromTo(
      q(".standards-field b"),
      { clipPath: "inset(0 100% 0 0)" },
      { clipPath: "inset(0 0% 0 0)", duration: 0.3, stagger: 0.15 },
      0,
    )
      .fromTo(
        q(".room-label"),
        { opacity: 1 },
        { opacity: 0, duration: 0.25, stagger: 0.1 },
        0.3,
      )
      .fromTo(
        q(".standard-room-labels text"),
        { opacity: 0, y: 6 },
        { opacity: 1, y: 0, duration: 0.25, stagger: 0.1 },
        0.4,
      )
      .fromTo(
        q(".standard-connection"),
        { strokeDasharray: 1, strokeDashoffset: 1 },
        { strokeDashoffset: 0, duration: 0.65 },
        0.2,
      )
      .fromTo(
        q(".standard-saved"),
        { clipPath: "inset(0 100% 0 0)" },
        { clipPath: "inset(0 0% 0 0)", duration: 0.25 },
        0.65,
      );
  }
  // A common length makes the five scenes predictable when nested in the scrub timeline.
  tl.to({}, { duration: 0.1 }, 0.9);
  return tl;
}
