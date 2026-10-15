// DEC-364: explicit phone geometry; the parent scene retains its shared scroll clock.
export function CompactTopology({
  inspected = false,
}: {
  inspected?: boolean;
}) {
  const nodes = [
    [220, 55, "Clients", "checkout requests"],
    [220, 155, "API gateway", "request routing"],
    [110, 270, "Shop API", inspected ? "p95 840 ms · 6.2%" : "sample service"],
    [330, 270, "Auth service", "identity check"],
    [110, 390, "PostgreSQL", inspected ? "query 720 ms" : "orders database"],
    [330, 390, "Worker", "background jobs"],
    [330, 510, "Redis", "cache and queue"],
    [110, 630, "Event stream", "scoped context"],
  ];
  return (
    <g>
      <g fill="none" stroke="#2862a3" strokeWidth="2">
        <path d="M220 85V125M220 185V210H110V240M220 210H330V240M110 300V360M110 330H220V350H330V360M330 300H430V510H425M330 420V480M110 420V600M330 540V575H110V600" />
        <path
          d="M110 300V360"
          stroke={inspected ? "#b43e35" : "#2862a3"}
          strokeWidth="4"
        />
      </g>
      {nodes.map(([x, y, name, detail]) => (
        <g key={name} transform={`translate(${x} ${y})`}>
          <rect
            x="-95"
            y="-30"
            width="190"
            height="60"
            rx="4"
            fill="#faf9f5"
            stroke={
              inspected && (name === "Shop API" || name === "PostgreSQL")
                ? "#b43e35"
                : "#2862a3"
            }
          />
          <text x="-80" y="-4" fontSize="20" fill="#252b32">
            {name}
          </text>
          <text x="-80" y="18" fontSize="15" fill="#58616b">
            {detail}
          </text>
        </g>
      ))}
      <text x="15" y="700" fontSize="14" fill="#58616b">
        INC-DEMO-042 · illustrative topology
      </text>
    </g>
  );
}
export function CompactGraphic({
  kind,
}: {
  kind: "signal" | "evidence" | "approval" | "history" | "trace";
}) {
  return (
    <svg
      className="compact-art"
      viewBox="0 0 400 480"
      role="img"
      aria-label={`Illustrative ${kind} diagram for Shop API incident INC-DEMO-042`}
    >
      {kind === "signal" ? (
        <>
          <text x="24" y="35" fontSize="16" fill="#252b32">
            Shop API / sample latency
          </text>
          <g stroke="#c7cbc9">
            {[90, 180, 270, 350].map((y) => (
              <path key={y} d={`M50 ${y}H370`} />
            ))}
          </g>
          <text x="12" y="94" fontSize="14" fill="#58616b">
            1s
          </text>
          <text x="12" y="354" fontSize="14" fill="#58616b">
            0
          </text>
          <path d="M50 220H370" stroke="#966119" strokeDasharray="5 5" />
          <text x="175" y="210" fontSize="14" fill="#966119">
            500 ms threshold
          </text>
          <path
            d="M50 322L80 310L110 325L140 305L170 310L200 287L230 260L260 180L290 120L320 145L350 132"
            fill="none"
            stroke="#2862a3"
            strokeWidth="3"
          />
          <circle cx="350" cy="132" r="5" fill="#b43e35" />
          <text x="50" y="380" fontSize="14" fill="#58616b">
            10:38
          </text>
          <text x="285" y="380" fontSize="14" fill="#58616b">
            10:42 UTC
          </text>
          <text x="24" y="425" fontSize="18" fill="#252b32">
            p95 840 ms · errors 6.2%
          </text>
          <text x="24" y="453" fontSize="15" fill="#58616b">
            148 req/min · illustrative values
          </text>
        </>
      ) : kind === "evidence" ? (
        <>
          <path
            d="M100 110V130H200V310M300 110V130H200M100 235V270H200M300 235V270H200"
            fill="none"
            stroke="#7456a0"
            strokeWidth="2"
          />
          {[
            ["E01 / METRIC", "p95 840 ms"],
            ["E02 / LOG", "query timeout"],
            ["E03 / TRACE", "db span 720 ms"],
            ["E04 / RUNBOOK", "check pool"],
          ].map(([label, detail], i) => (
            <g
              key={label}
              transform={`translate(${i % 2 ? 210 : 10} ${i < 2 ? 35 : 160})`}
            >
              <rect
                width="180"
                height="75"
                rx="3"
                fill="#faf9f5"
                stroke="#aeb9c3"
              />
              <text x="12" y="28" fontSize="16" fill="#7456a0">
                {label}
              </text>
              <text x="12" y="54" fontSize="16" fill="#252b32">
                {detail}
              </text>
            </g>
          ))}
          <rect
            x="25"
            y="310"
            width="350"
            height="140"
            rx="4"
            fill="#f3eff8"
            stroke="#7456a0"
          />
          <text x="42" y="340" fontSize="15" fill="#7456a0">
            HYPOTHESIS / UNCONFIRMED
          </text>
          <text x="42" y="375" fontSize="21" fill="#252b32">
            Slow database dependency
          </text>
          <text x="42" y="405" fontSize="15" fill="#58616b">
            Evidence E01–E03 supports review.
          </text>
          <text x="42" y="432" fontSize="15" fill="#966119">
            Pool saturation is not established.
          </text>
        </>
      ) : kind === "approval" ? (
        <>
          <path d="M200 90V410" stroke="#966119" strokeWidth="2" />
          {[
            ["EXACT PAYLOAD", "proposal / staging only"],
            ["HUMAN APPROVAL", "review required"],
            ["BACKEND EXECUTION", "separate policy check"],
            ["OBSERVED RECOVERY", "independent verification"],
          ].map(([title, detail], i) => (
            <g key={title} transform={`translate(35 ${25 + i * 115})`}>
              <rect
                width="330"
                height="85"
                rx="4"
                fill="#faf9f5"
                stroke={i === 1 ? "#966119" : "#2862a3"}
              />
              <text x="18" y="32" fontSize="18" fill="#252b32">
                {title}
              </text>
              <text x="18" y="61" fontSize="16" fill="#58616b">
                {detail}
              </text>
            </g>
          ))}
        </>
      ) : kind === "history" ? (
        <>
          <path d="M30 50V410" stroke="#2862a3" strokeWidth="2" />
          {[
            ["10:42 UTC", "Incident opened", "Threshold exceeded"],
            ["10:43 UTC", "Evidence attached", "Metric, log and trace"],
            ["10:44 UTC", "Awaiting review", "No execution or recovery"],
            ["RETAINED", "Runbook context", "For scoped investigations"],
          ].map(([time, title, detail], i) => (
            <g key={title} transform={`translate(30 ${45 + i * 115})`}>
              <circle cy="20" r="5" fill={i === 2 ? "#966119" : "#2862a3"} />
              <text x="25" y="0" fontSize="15" fill="#7456a0">
                {time}
              </text>
              <text x="25" y="30" fontSize="21" fill="#252b32">
                {title}
              </text>
              <text x="25" y="58" fontSize="16" fill="#58616b">
                {detail}
              </text>
            </g>
          ))}
        </>
      ) : (
        <>
          <text x="20" y="35" fontSize="16" fill="#252b32">
            TRACE-DEMO-042 / checkout
          </text>
          {[
            ["gateway", 840],
            ["Shop API", 790],
            ["auth.verify", 70],
            ["db.query", 720],
          ].map(([name, ms], i) => (
            <g key={name} transform={`translate(20 ${85 + i * 90})`}>
              <text y="0" fontSize="17" fill="#252b32">
                {name} / {ms} ms
              </text>
              <rect
                y="16"
                width={Number(ms) * 0.42}
                height="24"
                rx="3"
                fill={i === 3 ? "#b43e35" : "#2862a3"}
              />
            </g>
          ))}
          <text x="20" y="455" fontSize="15" fill="#58616b">
            Illustrative spans / 10:42 UTC
          </text>
        </>
      )}
    </svg>
  );
}
