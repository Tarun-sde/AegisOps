"use client";
import type { RefObject } from "react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { useGSAP } from "@gsap/react";

export function useSceneEntrances(root: RefObject<HTMLElement | null>) {
  useGSAP(
    () => {
      const media = gsap.matchMedia();
      media.add("(prefers-reduced-motion: no-preference)", () => {
        const deferred = gsap.context(() => {});
        const hero = root.current!.querySelector(".dashboard-hero");
        let releaseEntrance = () => {};
        if (hero) {
          const q = gsap.utils.selector(hero);
          const tl = gsap.timeline({
            paused: true,
            defaults: { ease: "power2.out" },
          });
          tl.fromTo(
            q(".terrain"),
            { clipPath: "inset(100% 0 0 0)" },
            { clipPath: "inset(0% 0 0 0)", duration: 1 },
            0,
          )
            .fromTo(
              q(".activity-panel"),
              { yPercent: 18 },
              { yPercent: 0, duration: 0.9 },
              0.15,
            )
            .fromTo(
              q(".pending-panel"),
              { xPercent: 20, yPercent: 12 },
              { xPercent: 0, yPercent: 0, duration: 0.8 },
              0.35,
            )
            .fromTo(
              q(".activity-row"),
              { clipPath: "inset(0 100% 0 0)" },
              { clipPath: "inset(0 0% 0 0)", duration: 0.5, stagger: 0.07 },
              0.3,
            )
            .fromTo(
              q("h1"),
              { clipPath: "inset(0 0 100% 0)" },
              { clipPath: "inset(0 0 0% 0)", duration: 0.9 },
              0.15,
            );
          const play = () => {
            tl.play();
          };
          let visited = false;
          try {
            visited = sessionStorage.getItem("aegisops-entered") === "1";
          } catch {
            /* Storage is optional. */
          }
          if (
            visited ||
            document.documentElement.dataset.aegisopsEntered === "true"
          )
            tl.play();
          window.addEventListener("aegisops:entrance", play);
          releaseEntrance = () =>
            window.removeEventListener("aegisops:entrance", play);
        }
        const intro = root.current!.querySelector(".intro");
        if (intro) {
          gsap.fromTo(
            intro.querySelector("h2"),
            { clipPath: "inset(0 100% 0 0)" },
            {
              clipPath: "inset(0 0% 0 0)",
              ease: "none",
              scrollTrigger: {
                trigger: intro,
                start: "top 85%",
                end: "center 50%",
                scrub: 0.5,
              },
            },
          );
        }
        root
          .current!.querySelectorAll(".problem-graphic")
          .forEach((graphic, index) => {
            const tl = gsap.timeline({
              scrollTrigger: {
                trigger: graphic,
                start: "top 90%",
                end: "bottom 55%",
                scrub: 0.5,
              },
            });
            if (index === 0) {
              tl.fromTo(
                graphic.querySelector(".plan-furniture"),
                { clipPath: "inset(0 100% 0 0)" },
                { clipPath: "inset(0 0% 0 0)", duration: 1 },
              ).fromTo(
                graphic.querySelector(".plan-dimensions"),
                { scaleX: 0.5 },
                { scaleX: 1, duration: 1 },
                0,
              );
            } else if (index === 1) {
              tl.fromTo(
                graphic.querySelectorAll("svg"),
                { x: (i) => (i === 0 ? 35 : -35) },
                { x: 0, duration: 1 },
              );
            } else if (index === 2) {
              tl.fromTo(
                graphic.querySelector(".target-diagram"),
                { scale: 0.55, rotation: -45 },
                { scale: 1, rotation: 0, duration: 1 },
              );
            } else {
              tl.fromTo(
                graphic.querySelector(".clock-diagram span"),
                { rotation: -150, transformOrigin: "50% 100%" },
                { rotation: 0, duration: 1 },
              );
            }
          });
        root
          .current!.querySelectorAll(".product-row, .oversight-art")
          .forEach((section) => {
            // Defer the richer layer setup until the illustration approaches the viewport.
            ScrollTrigger.create({
              trigger: section,
              start: "top bottom+=150",
              once: true,
              onEnter: () =>
                deferred.add(() => {
                  const q = gsap.utils.selector(section);
                  const tl = gsap.timeline({
                    scrollTrigger: {
                      trigger: section,
                      start: "top 95%",
                      end: "center 55%",
                      scrub: 0.5,
                    },
                  });
                  const layers = q(
                    ".activity-panel, .pending-panel, .approval-card",
                  );
                  if (layers.length)
                    tl.fromTo(
                      layers,
                      { yPercent: (i) => 15 + i * 12 },
                      { yPercent: 0, stagger: 0.12, duration: 0.7 },
                      0,
                    );
                  const rows = q(
                    ".activity-row, .pending-panel > div:not(:first-child)",
                  );
                  if (rows.length)
                    tl.fromTo(
                      rows,
                      { clipPath: "inset(0 100% 0 0)" },
                      {
                        clipPath: "inset(0 0% 0 0)",
                        stagger: 0.07,
                        duration: 0.3,
                      },
                      0.2,
                    );
                  const dimensions = q(".plan-dimensions");
                  if (dimensions.length)
                    tl.fromTo(
                      dimensions,
                      { scaleX: 0.8 },
                      { scaleX: 1, duration: 0.8 },
                      0,
                    );
                }),
            });
          });
        const pavilion = root.current!.querySelector(".use-case-art");
        if (pavilion)
          gsap.fromTo(
            pavilion.querySelector("svg"),
            { clipPath: "inset(0 0 90% 0)" },
            {
              clipPath: "inset(0 0 0% 0)",
              ease: "none",
              scrollTrigger: {
                trigger: pavilion,
                start: "top 85%",
                end: "center 55%",
                scrub: 0.5,
              },
            },
          );
        return () => {
          releaseEntrance();
          deferred.revert();
        };
      });
      return () => media.revert();
    },
    { scope: root },
  );
}
