# Final animation migration matrix

Reference `f46969734ce644be97003f558bd738dd5e76832f`. DEC-378–380/382. Source reuse verified by direct diff. Desktop/tablet/mobile rendered comparisons and behavioral checks completed during iteration; final gallery refreshed and reviewed at all five requested viewports. Source reuse alone is not proof of parity.

| Reference animation | Original source | AegisOps target | Reuse / fidelity status |
|---|---|---|---|
| Hero path drawing, clip, dimensions, stagger, caption | hero.tsx | hero.tsx + SystemDrawing | Target adaptation; same positions/durations/ease |
| Drag selection, overlap, direction gradient | hero.tsx + geometry.ts | hero.tsx + geometry.ts | Reused; sample marker coordinates adapted; keyboard/touch button retained |
| Preloader count, drawing, curtain | site-shell.tsx | site-shell.tsx | Extra independent beats removed; original clock retained |
| Header/menu and route curtain | site-shell.tsx | site-shell.tsx | Original navigation clock; real destinations/native modal |
| Smooth scroll clock / cleanup | site-shell.tsx | SiteShell marketing routes | Reused; excluded from operational screens |
| Workflow pin / scrub / text crossfade | home-page.tsx ModelWorkflow | home-page.tsx | Source 6 viewport distance, scrub 1, four phases, mobile .85 tween |
| Scan, dimensions, instrumentation | motion-scenes.ts workflowScene | IncidentPlan | Source timing retained, software layers replace building targets |
| Pins / frame / leader / evidence card | same | IncidentPlan + workflow-alert | Source timing retained |
| Reticle / reviewed path / proposal | same | proposal route + geometry-fix | Original morph clock; operational path coordinates; awaiting approval, no execution |
| Persisted context route / nodes | same | model-standard-route/node | Original timing; incident/evidence/runbook links, no retraining claim |
| Five feature compositions | motion-scenes.ts featureScene | ProductPreview 0–4 | Full source timeline restored; seven-window stack, approval/history/review/runbook layers |
| Feature panel pin / progress / reverse | dashboard-page.tsx | platform-page.tsx | Source clock; completed-scene click checkpoint (DEC-365) |
| Intro / problems / product rows / use-case reveal | scene-entrances.ts | scene-entrances.ts | Original scene code with event namespace adaptation |
| Why accordion drawing transformation | home-page.tsx | home-page.tsx | Source transitions, operational path targets |
| Ink mask / displacement | footer.tsx FinalCTA | footer.tsx | Reused unchanged timeline; SystemDrawing layers |
| Wordmark lens pointer lag / cleanup | footer.tsx Footer | footer.tsx | Source wordmark composition and timing restored |
| Workspace entrance, sidebar collapse, dialogs | workspace-shell / workspace.css | app-shell / workspace.css / dialogs | Existing source-derived implementation retained; real data and native focus controls |
| Time-series hover / data slider | analytics/time-series.tsx | unavailable analytics frame | Intentionally unavailable: no backend series; no synthetic values in authenticated UI |

Original geometry selector names retained where they form the source timeline contract; this does not imply building content. Tests must assert actual operational drawing content and animation state rather than ban source selector names. Final captures must compare equal viewports, progress and loaded states.

Click-to-phase deliberately retains the existing DEC-365 .85 checkpoint (reference .5), so selecting Act finishes its .65 path transition and selecting a feature finishes its staggered content. Scroll phase boundaries, durations and easing remain source-exact. This previously verified accessibility/detail correction is not a new timeline.


Verified behavior: four operational phases scrub forward/back on one drawing, completed route morph and saved nodes, reference-style drag geometry, keyboard/touch inspection, route cleanup and reduced motion pass the browser gate. All five feature layer compositions are present. Source diffs retain every workflow/feature duration, easing, stagger and placement; only domain path coordinates and one guide selector differ. The collection entrance skips empty target sets on operational routes, preserving source timing where targets exist.

Gallery state coverage: event-relative hero mid-entrance (~650ms, recorded actual offset), finished hero, drag/selected state, workflow initial/Observe/Advise/Act/Learn/reverse, all five feature stages plus mobile completed visual stages, preview approval and hover, menu, ink and footer pointer lens. Native screenshot scheduling is not a frame-perfect animation benchmark. Mobile completed scenes are captured at the source visual scroll endpoint; card-top captures separately show the in-progress reveal.

No animation is authorized to issue a real action. Analytics chart hover/slider remains intentionally unavailable because there are no scoped backend time-series values; source fixtures are not connected to the application.
