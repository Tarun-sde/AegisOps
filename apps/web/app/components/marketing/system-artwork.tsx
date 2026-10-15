import { useId } from "react";

// DEC-378: source drawing envelopes and layer contracts, original operational geometry.
export function SystemDrawing({
  shaded = true,
  inspected = false,
}: {
  shaded?: boolean;
  inspected?: boolean;
}) {
  const id = useId().replaceAll(":", "");
  return (
    <g className={`topology-drawing ${inspected ? "inspected" : ""}`}>
      <defs>
        <pattern
          id={`circuit-${id}`}
          width="6"
          height="6"
          patternUnits="userSpaceOnUse"
          patternTransform="rotate(35)"
        >
          <path d="M0 0v6" stroke="#555e56" strokeWidth=".45" opacity=".35" />
        </pattern>
      </defs>
      <g
        className="topology-guides"
        stroke="#8e8e87"
        strokeWidth=".55"
        fill="none"
        opacity=".55"
      >
        {[160, 250, 390, 520, 650, 745, 850].map((x) => (
          <path key={x} d={`M${x} 108V529`} />
        ))}
        {[153, 260, 370, 468].map((y) => (
          <path key={y} d={`M135 ${y}H875`} />
        ))}
        <path d="M155 525H856M155 519v12m700-12v12M228 126H762M228 119v14m534-14v14m-549 8 14-14m521 14 14-14" />
      </g>
      <g
        className="topology-structure topology-links"
        fill="none"
        stroke="#353c38"
        strokeWidth="1"
      >
        <path
          d="M105 482H890M230 154H750V480H230Z"
          fill={shaded ? "#b9bdb2" : "none"}
        />
        <path
          d="M240 164H740V470H240Z"
          fill={shaded ? `url(#circuit-${id})` : "none"}
        />
        <path
          d="M248 176H729V245H248ZM248 272H729V369H248ZM248 396H729V458H248Z"
          fill={shaded ? "#d4d8cd" : "none"}
        />
        <path
          d="M248 252H729V263H248ZM248 377H729V388H248Z"
          fill={shaded ? "#747e71" : "none"}
        />
        <path d="M376 176v69m142-69v69M379 272v97m140-97v97M393 396v62m151-62v62" />
        {/* Instrumentation fans: correlated request spans, not decorative trees. */}
        {[0, 1].map((side) => (
          <g key={side} strokeWidth=".55" opacity=".75">
            {Array.from({ length: 32 }, (_, i) => {
              const anchor = side ? 794 : 174;
              const x = anchor + (side ? 1 : -1) * (25 + (i % 8) * 8);
              const y = 291 + i * 5;
              return (
                <path
                  key={i}
                  d={`M${anchor} 480V${y + 18}L${x} ${y}h${side ? 13 : -13}m0-2v4M${x} ${y}v-5h${side ? 8 : -8}`}
                />
              );
            })}
          </g>
        ))}
        {/* Request ingress and gateway protocol lanes. */}
        {[0, 1, 2, 3, 4].map((i) => (
          <g key={i} strokeWidth=".65">
            <path
              d={`M148 ${182 + i * 17}h48l18 16h34M152 ${182 + i * 17 - 4}h12v8h-12Z`}
            />
            <path d={`M265 ${197 + i * 8}h92m-92 3h${30 + i * 10}`} />
          </g>
        ))}
        {/* Shop API runtime: worker threads and bounded request queues. */}
        {[0, 1, 2, 3].map((i) => (
          <g key={i}>
            <path
              d={`M398 ${187 + i * 13}h101v9H398Z`}
              fill={shaded ? "#a7b4a2" : "none"}
            />
            <path
              d={`M405 ${191 + i * 13}h37m7 0h17m9 0h16`}
              strokeWidth=".6"
            />
            <circle cx="494" cy={191 + i * 13} r="1.4" fill="#586a52" />
          </g>
        ))}
        {/* PostgreSQL pages and WAL journal. */}
        <path
          d="M551 194c0-16 147-16 147 0v35c0 16-147 16-147 0Z"
          fill={shaded ? "#9fa997" : "none"}
        />
        <ellipse cx="624.5" cy="194" rx="73.5" ry="12" />
        <path
          d="M551 207c0 16 147 16 147 0m-147 11c0 16 147 16 147 0"
          strokeWidth=".6"
        />
        {/* Trace propagation through the request bus. */}
        <path d="M314 245v12h135v15m0-27v12h176v-12M314 263v9m311-9v9M750 214h43v-33h57m-57 33v30h57" />
        {[0, 1, 2].map((i) => (
          <g key={i}>
            <path
              d={`M${270 + i * 32} 286h24v48h-24Z`}
              fill={shaded ? "#b3bcad" : "none"}
            />
            <path
              d={`M${275 + i * 32} 292h14m-14 7h14m-14 7h14m-14 7h14m-14 7h14`}
              strokeWidth=".6"
            />
          </g>
        ))}
        {/* A real trace shape, not a decorative empty graph. */}
        <path
          d="M397 290H504M397 306H504M397 322H504M397 338H504M397 354H504"
          stroke="#9baba0"
          strokeWidth=".55"
        />
        <path
          d="M398 300h94m-78 16h67m-47 16h63m-49 16h36"
          strokeWidth="5"
          stroke="#6f806a"
        />
        <path
          d="M398 290v66m17-66v66m19-66v66m14-66v66m49-66v66"
          strokeWidth=".4"
        />
        {/* Metrics trajectory and event/log buffer. */}
        <path
          d="M539 348h171M539 283v65m0-16h171m-171-16h171m-171-16h171"
          strokeWidth=".5"
          stroke="#8b998c"
        />
        <path
          d="M539 335l12-4 11 3 13-4 12 3 14-2 13-5 12-34 13 13 12-12 13 16 12-6 13 20 11-3"
          stroke="#586f50"
          strokeWidth="1.4"
        />
        <path d="M248 350h-47v-37h-45m45 37v43h-45M750 319h34v51h66M314 369v13h155v14m156-27v13H469" />
        {[0, 1, 2, 3, 4].map((i) => (
          <g key={i} strokeWidth=".7">
            <path
              d={`M264 ${408 + i * 8}h111m-111 3h${55 + i * 7}M409 ${408 + i * 8}h118m-118 3h${73 - i * 9}M562 ${408 + i * 8}h145m-145 3h${90 - i * 12}`}
            />
          </g>
        ))}
        <path
          d="M156 306h28v14h-28ZM156 386h28v14h-28ZM814 174h36v14h-36ZM814 237h36v14h-36ZM814 363h36v14h-36Z"
          fill={shaded ? "#c1c7b9" : "none"}
        />
        {[0, 1, 2, 3, 4, 5, 6, 7, 8].map((i) => (
          <path key={i} d={`M${257 + i * 58} 148v12M${257 + i * 58} 474v12`} />
        ))}
        <path d="M252 493h476m-476-5v10m476-10v10" strokeWidth=".55" />
      </g>
      <g
        className="topology-anomaly"
        stroke={inspected ? "#b43e35" : "#966119"}
        fill="none"
        strokeWidth="1.6"
      >
        <path d="M449 231v27h176v-14M625 258v24" />
        <rect x="545" y="177" width="160" height="67" strokeDasharray="3 3" />
        <path d="M705 194h65v-45h58" strokeWidth=".7" />
      </g>
      <g
        className="topology-annotations"
        fontFamily="monospace"
        fontSize="7"
        fill="#515b50"
      >
        <text x="278" y="174">
          API GATEWAY
        </text>
        <text x="415" y="174">
          SHOP API / RUNTIME
        </text>
        <text x="589" y="174">
          POSTGRESQL / STORAGE
        </text>
        <text x="268" y="285">
          BACKGROUND WORKERS
        </text>
        <text x="400" y="285">
          TRACE PROPAGATION
        </text>
        <text x="564" y="285">
          METRICS / p95 840ms
        </text>
        <text x="268" y="405">
          REDIS / QUEUE
        </text>
        <text x="410" y="405">
          EVENT STREAM
        </text>
        <text x="560" y="405">
          OTEL / LOG INSTRUMENTATION
        </text>
        <text x="139" y="171">
          CLIENTS / HTTPS
        </text>
        <text x="785" y="144">
          E03 / 720ms DB SPAN
        </text>
        <text x="787" y="271">
          E01 / METRIC
        </text>
        <text x="133" y="301">
          AUTH / SCOPE
        </text>
        <text x="133" y="383">
          RUNBOOKS
        </text>
        <text x="783" y="390">
          E02 / REDACTED LOG
        </text>
        <text x="435" y="121">
          REQUEST / TRACE / EVIDENCE
        </text>
        <text x="405" y="538">
          ILLUSTRATIVE SYSTEM / INC-DEMO-042
        </text>
        <text x="139" y="502">
          BOUNDARY / STAGING
        </text>
      </g>
    </g>
  );
}

export function SystemElevation({
  className = "",
  shaded = true,
}: {
  className?: string;
  shaded?: boolean;
}) {
  return (
    <svg
      className={className}
      viewBox="0 0 1000 620"
      role="img"
      aria-label="Illustrative service blueprint: gateway, Shop API, PostgreSQL, workers, traces, metrics and logs"
    >
      <SystemDrawing shaded={shaded} />
    </svg>
  );
}

export function IncidentPlan({
  className = "",
  highlight = false,
  narrative = false,
  standardized = false,
}: {
  className?: string;
  highlight?: boolean;
  narrative?: boolean;
  standardized?: boolean;
}) {
  return (
    <svg
      className={`floor-plan incident-plan ${standardized ? "standardized" : ""} ${className}`}
      viewBox="0 0 700 640"
      role="img"
      aria-label="Illustrative INC-DEMO-042: one service system, database latency evidence, staging proposal awaiting approval, and linked investigation history"
    >
      <g
        className="plan-dimensions"
        fill="none"
        stroke="#999b91"
        strokeWidth=".6"
      >
        {Array.from({ length: 10 }, (_, i) => (
          <path
            key={i}
            d={`M${95 + i * 55} 35V603M60 ${55 + i * 58}H660`}
            strokeDasharray="3 4"
            opacity=".4"
          />
        ))}
        <path d="M131 58H575M124 73v-25m462 25v-25M106 81V549m-10-468h25M96 549h25M135 583h446m-446-14v23m446-23v23M137 86H576V540H137Z" />
        {[130, 285, 422, 581].map((x) => (
          <path key={x} d={`M${x} 564v30m-5-7 10-10`} />
        ))}
      </g>
      {highlight && (
        <rect
          className="plan-alert"
          x="148"
          y="94"
          width="265"
          height="151"
          fill="#966119"
          opacity=".18"
        />
      )}
      <g
        className="plan-walls"
        stroke="#41483e"
        fill="#d5d8ce"
        strokeWidth="1.8"
      >
        <path d="M132 82h150v169H132ZM298 82h283v169H298ZM132 270h266v127H132ZM423 270h158v127H423ZM132 416h150v127H132ZM298 416h283v127H298Z" />
        <path
          d="M137 87h140v159H137ZM303 87h273v159H303ZM137 275h256v117H137ZM428 275h148v117H428Z"
          fill="none"
          strokeWidth=".5"
        />
      </g>
      <g
        className="plan-furniture"
        fill="none"
        stroke="#7b8576"
        strokeWidth="1"
      >
        <path d="M132 163H80v-43h52m75 131v19m75-107h16m142 88v19M266 397v19m235-19v19M282 478h16" />
        {[0, 1, 2, 3, 4].map((i) => (
          <g key={i}>
            <path d={`M148 ${111 + i * 24}h117v16H148Z`} fill="#bec7b5" />
            <path
              d={`M156 ${119 + i * 24}h46m9 0h20m8 0h18`}
              strokeWidth=".65"
            />
            <circle cx="257" cy={119 + i * 24} r="2" fill="#727e68" />
          </g>
        ))}
        <path d="M319 113H559M319 134H559M319 155H559" strokeWidth=".5" />
        <path
          d="M319 118h214m-191 21h181m-150 20h176"
          strokeWidth="7"
          stroke="#8d9f80"
        />
        <path
          className="editable-door"
          d="M423 191h-54v54h54"
          stroke="#966119"
          strokeWidth="2.4"
        />
        <path d="M432 191h117v54H432Z" strokeDasharray="3 3" />
        <path d="M442 204h94m-94 10h73m-73 10h84m-84 10h54" strokeWidth=".7" />
        {[0, 1, 2].map((i) => (
          <g key={i}>
            <path d={`M${149 + i * 79} 298h62v68h-62Z`} fill="#c3ccbc" />
            <path
              d={`M${156 + i * 79} 309h48m-48 10h48m-48 10h48m-48 10h48m-48 10h48`}
              strokeWidth=".6"
            />
          </g>
        ))}
        <path
          d="M442 306c0-17 116-17 116 0v59c0 17-116 17-116 0Z"
          fill="#bdc8b5"
        />
        <ellipse cx="500" cy="306" rx="58" ry="13" />
        <path d="M442 328c0 17 116 17 116 0m-116 18c0 17 116 17 116 0" />
        <path
          d="M147 512h119M147 443v69m0-23h119m-119-23h119"
          strokeWidth=".5"
        />
        <path
          className="signal-baseline"
          d="M149 497l12-3 14 2 12-3 13 2 12-1 12 3 14-2 12 1 12-2"
          stroke="#586f50"
        />
        <path
          className="signal-line"
          pathLength="1"
          d="M209 494l10-7 11-31 11 8 11-18 12 20"
          stroke="#966119"
          strokeWidth="1.8"
        />
        <path
          d="M315 439h248m-248 19h248m-248 19h248m-248 19h248m-248 19h248"
          strokeWidth=".5"
        />
        {[0, 1, 2, 3, 4].map((i) => (
          <path
            key={i}
            d={`M318 ${444 + i * 19}h${185 - i * 13}m12 0h${32 + i * 2}`}
            strokeWidth="2"
          />
        ))}
      </g>
      <g
        className="plan-labels"
        fill="#4e5948"
        fontFamily="monospace"
        fontSize="7"
        textAnchor="middle"
      >
        <text className="room-label" x="207" y="102">
          SHOP API / REQUEST POOL
        </text>
        <text className="room-label" x="440" y="102">
          TRACE-DEMO-042 / DB SPAN 720ms
        </text>
        <text className="room-label" x="265" y="288">
          WORKERS / QUEUE / EVENTS
        </text>
        <text className="room-label" x="501" y="288">
          POSTGRESQL
        </text>
        <text className="room-label" x="207" y="432">
          METRIC E01 / p95 840ms
        </text>
        <text className="room-label" x="440" y="432">
          LOG E02 / QUERY TIMEOUT
        </text>
        <text x="350" y="53">
          INC-DEMO-042 / ILLUSTRATIVE SAMPLE
        </text>
        <text x="206" y="601">
          OBSERVE
        </text>
        <text x="359" y="601">
          REVIEW
        </text>
        <text x="499" y="601">
          RETAIN
        </text>
        <text transform="translate(93 320) rotate(-90)">
          SERVICE / EVIDENCE BOUNDARY
        </text>
      </g>
      {standardized && (
        <g
          className="standard-room-labels"
          fill="#4e5948"
          fontFamily="monospace"
          fontSize="7"
          textAnchor="middle"
        >
          <text x="207" y="102">
            AUTHORIZED SERVICE
          </text>
          <text x="440" y="102">
            SCOPED TRACE CITATION
          </text>
          <text x="265" y="288">
            BOUNDED READ-ONLY TOOLS
          </text>
          <text x="501" y="288">
            RB-PG-POOL-01
          </text>
        </g>
      )}
      {narrative && (
        <g className="model-narrative" fill="none" strokeWidth="1.4">
          <rect
            className="model-clearance"
            x="369"
            y="184"
            width="54"
            height="67"
            fill="#966119"
            fillOpacity=".12"
            stroke="#966119"
          />
          <path
            className="model-issue-frame"
            pathLength="1"
            stroke="#b43e35"
            d="M363 178h66v79h-66Z"
          />
          <path
            className="model-leader"
            pathLength="1"
            stroke="#b43e35"
            d="M429 213h66v-51h64"
          />
          <path
            className="model-before"
            stroke="#966119"
            strokeDasharray="3 3"
            d="M423 191h-54v54h54"
          />
          <g className="model-reticle" stroke="#282828">
            <path d="M-13-5v-8h8m10 0h8v8m0 10v8h-8m-10 0h-8v-8M-6 0H6M0-6V6" />
          </g>
          <path
            className="model-standard-route"
            pathLength="1"
            stroke="#626b5f"
            d="M477 224h74v140H335v110h166"
          />
          {[
            [477, 224],
            [335, 364],
            [501, 474],
          ].map(([x, y], i) => (
            <g
              className="model-standard-node"
              key={x}
              transform={`translate(${x} ${y})`}
            >
              <rect
                x="-12"
                y="-12"
                width="24"
                height="24"
                fill="#e0e0da"
                stroke="#626b5f"
              />
              <path d="M-5-6h10v12H-5Zm2 4h6m-6 4h6" stroke="#626b5f" />
              <text
                x="18"
                y="3"
                stroke="none"
                fill="#626b5f"
                fontSize="7"
                fontFamily="monospace"
              >
                {["INCIDENT", "EVIDENCE", "RUNBOOK"][i]}
              </text>
            </g>
          ))}
        </g>
      )}
      <g className="plan-issue-pins" fill="#b43e35">
        <rect x="123" y="179" width="18" height="18" />
        <rect x="413" y="213" width="18" height="18" />
        <rect x="204" y="352" width="18" height="18" />
      </g>
    </svg>
  );
}

export function TelemetryTerrain() {
  return (
    <svg viewBox="0 0 800 320" aria-hidden="true">
      <g fill="none" stroke="#606e58" strokeWidth=".7">
        {Array.from({ length: 22 }, (_, i) => (
          <path
            key={i}
            d={`M0 ${190 + i * 5}L70 ${156 + i * 5} 145 ${34 + i * 9} 220 ${165 + i * 5} 293 ${114 + i * 6} 365 ${201 + i * 4} 439 ${102 + i * 7} 502 ${142 + i * 5} 581 ${57 + i * 8} 658 ${149 + i * 5} 736 ${92 + i * 7} 800 ${152 + i * 5}`}
          />
        ))}
      </g>
    </svg>
  );
}

// Source Pavilion envelope and perspective footprint, operational trace layers.
export function ServiceFabric() {
  return (
    <svg
      viewBox="0 0 800 800"
      role="img"
      aria-label="Illustrative distributed system: layered request, trace and evidence planes with a human review boundary"
    >
      <circle cx="164" cy="210" r="114" fill="#b7b8ae" />
      <path d="M595 0h138v496H595Z" fill="#c1c3b7" />
      <g stroke="#60645b" strokeWidth=".7" fill="none">
        <path d="M0 657 800 337M0 698 800 391M0 742 800 453M0 792 800 526M130 800 800 610M390 800 800 707" />
        {[0, 90, 210, 350, 530, 760, 1000, 1350].map((x, i) => (
          <path key={i} d={`M510 380 ${x - 200} 800`} />
        ))}
      </g>
      {[0, 1, 2].map((layer) => (
        <g key={layer} transform={`translate(0 ${layer * 68})`}>
          <path
            d="m68 360 666-238 66 54L122 438Z"
            fill={["#b9bcb0", "#a6b09b", "#d1d4c8"][layer]}
            stroke="#53574d"
          />
          <path
            d="m122 438 678-262v16L122 454Z"
            fill="#818c76"
            stroke="#666b5e"
          />
          {Array.from({ length: 16 }, (_, i) => (
            <path
              key={i}
              d={`M${100 + i * 41} ${350 - i * 14.7}l35 32m-18-16 30-10`}
              stroke="#606e56"
              strokeWidth=".7"
              fill="none"
            />
          ))}
          {[0, 1, 2, 3, 4].map((i) => (
            <g
              key={i}
              transform={`translate(${185 + i * 108} ${350 - i * 38})`}
            >
              <path
                d="m0 0 51-18 28 24-51 18Z"
                fill="#64775a"
                stroke="#354331"
              />
              <path
                d="m0 0v12l28 24v-12m0 12 51-18V6"
                fill="#929e87"
                stroke="#354331"
              />
              <path d="m9 1 32-11m-24 17 32-11" stroke="#dfe4d7" />
            </g>
          ))}
        </g>
      ))}
      <g stroke="#626f57" fill="none" strokeWidth="1.2">
        <path d="M213 376v153m216-229v153m216-229v153" strokeDasharray="4 4" />
        <path
          d="M645 378v100l-216 76v85l-156 54"
          stroke="#966119"
          strokeWidth="2"
        />
      </g>
      <g fontFamily="monospace" fontSize="9" fill="#4f5c47">
        <text x="25" y="715">
          01 / REQUEST PROPAGATION
        </text>
        <text x="25" y="733">
          02 / SCOPED TRACE EVIDENCE
        </text>
        <text x="25" y="751">
          03 / HUMAN REVIEW BOUNDARY
        </text>
        <text x="25" y="780">
          AEGISOPS / ILLUSTRATIVE SYSTEM
        </text>
        <text x="625" y="780">
          PERSPECTIVE 02
        </text>
      </g>
    </svg>
  );
}
