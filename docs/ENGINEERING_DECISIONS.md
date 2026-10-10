# AegisOps — Engineering Decisions & Interview Defense Journal

> **Canonical repository path:** `docs/ENGINEERING_DECISIONS.md`  
> **Project:** AegisOps — AI-Powered Incident Intelligence & Response Platform  
> **Started:** 2026-10-10  
> **Purpose:** Record *why* AegisOps was built in a particular way, which alternatives were considered, what was learned, what was measured, and how to explain the reasoning during SDE, backend, AI engineering, and FDE interviews.  
> **Source plan:** `AEGISOPS_MASTER_IMPLEMENTATION_PLAN.md` (copy into the repository under the agreed location).  
> **Truth rule:** The architectural decisions below are **design choices, NOT claims that the system has been built, deployed, benchmarked, or used by customers**.

---

## 0. How to use this journal

**Before coding:** Read this journal, the master plan, and `docs/PROJECT_STATE.md`. Add or revise decision entries when a meaningful decision is about to be implemented.

**During coding:** Document **every deliberate behavior-bearing choice, small or large**, even if documenting it slows progress. Save alternatives, prototypes, benchmarks, failures, security trade-offs, and links to changes. Never write a justification invented after the fact.

**After coding:** Update implementation status and **verified evidence** (PR/commit IDs, tests, logs, benchmark commands and sample sizes). If there is no evidence yet, write `Not measured` or `Not implemented`.

**During interviews:** Use each entry's 30–60-second answer as a **speaking framework**, not a memorized claim. Expand with actual code paths and measurements from your project.

### Status vocabulary

- **ACCEPTED — DESIGN ONLY:** Chosen in the blueprint; no verified implementation yet.
- **IMPLEMENTED — UNVERIFIED:** Code exists, but required tests/metrics are incomplete.
- **VERIFIED:** Implementation and cited acceptance evidence exist.
- **REVISIT:** Decision needs re-evaluation due to new evidence/constraints.
- **SUPERSEDED:** Replaced; preserve its history and link to the new entry.
- **REJECTED:** Considered but not selected; record why.

### Mandatory entry format (copy when adding a decision)

```markdown
### ADR-XXX — Clear decision title
- **Date:** YYYY-MM-DD
- **Status:** ACCEPTED — DESIGN ONLY | IMPLEMENTED — UNVERIFIED | VERIFIED | REVISIT | SUPERSEDED
- **Owner:** Developer / decision reviewer
- **Problem and constraints:** What concrete need triggered this choice? Budget, latency, time, permissions, maintenance?
- **Decision:** Exactly what we chose (and what is explicitly out of scope).
- **Alternatives compared:** Option A — advantage/disadvantage; Option B — advantage/disadvantage.
- **Why this wins for AegisOps:** Specific reasoning tied to goals and constraints (not "industry standard").
- **Costs / downsides:** Complexity, resources, failure modes, vendor lock-in, security, performance.
- **Proof / verification:** PR, commit, test command, benchmark dataset, measurements, logs, issue URL; or `Not measured`.
- **Revisit when:** Explicit condition that might reverse this decision.
- **Interview answer (30–60 sec):** Problem -> options -> choice -> trade-off -> demonstrated outcome (only if measured).
- **Follow-up questions:** 2–4 difficult questions, with accurate short answers or TODOs.
```

**Source caution:** Existing ADR alternative comparisons explain proposed trade-offs, **not measured head-to-head evaluations**. The implementation plan is the design authority; mark any extra reasoning as hypothesis until confirmed.

**When a decision changes:** Create an additional ADR, mark the old one `SUPERSEDED`, and explain the evidence that changed the decision. Never silently rewrite history.

---

## 1. Decision map

| ID | Topic | Selected direction | State | Verified implementation |
|---|---|---|---|---|
| ADR-001 | Agent framework | Google ADK (Python) | ACCEPTED — DESIGN ONLY | No |
| ADR-002 | Agent topology | One bounded investigation agent first | ACCEPTED — DESIGN ONLY | No |
| ADR-003 | Model/provider | Configurable Gemini API model, selected by evaluation | ACCEPTED — DESIGN ONLY | No |
| ADR-004 | Control-plane backend | FastAPI/Python | ACCEPTED — DESIGN ONLY | No |
| ADR-005 | Web application | Next.js/TypeScript | ACCEPTED — DESIGN ONLY | No |
| ADR-006 | Telemetry | OpenTelemetry + Prometheus/Alertmanager + Loki + Tempo | ACCEPTED — DESIGN ONLY | No |
| ADR-007 | Detection vs reasoning | Deterministic alerts first, event-triggered LLM investigation | ACCEPTED — DESIGN ONLY | No |
| ADR-008 | Primary database/RAG | PostgreSQL + pgvector + lexical fallback | ACCEPTED — DESIGN ONLY | No |
| ADR-009 | Task execution | Celery + Redis + PostgreSQL run ledger | ACCEPTED — DESIGN ONLY | No |
| ADR-010 | Automation | Internal, operator-authored n8n workflows | ACCEPTED — DESIGN ONLY | No |
| ADR-011 | Remediation | Suggestions + backend-enforced approval; staging-only actions | ACCEPTED — DESIGN ONLY | No |
| ADR-012 | Evidence reliability | Typed diagnoses and independent citation validation | ACCEPTED — DESIGN ONLY | No |
| ADR-013 | Deployment | Docker Compose to start; avoid premature Kubernetes | ACCEPTED — DESIGN ONLY | No |
| ADR-014 | Evaluation | Fault-injection lab, labeled holdouts, measured baselines | ACCEPTED — DESIGN ONLY | No |
| ADR-015 | Integration security | Read-only, tenant-scoped tool gateway; GitHub read-only v1 | ACCEPTED — DESIGN ONLY | No |
| ADR-016 | Multi-tenancy | Tenant-aware schema, restricted initial public rollout | ACCEPTED — DESIGN ONLY | No |

---

## 1A. Plan-derived **granular baseline decision register**

**Source of authority:** `AEGISOPS_MASTER_IMPLEMENTATION_PLAN.md`, v1.0, dated 2026-10-10. This register breaks out 202 major **and small** design choices into independently traceable entries; during implementation, record any additional specifics or omissions rather than assuming this baseline covers every future choice. Every entry is **DESIGN ONLY** at creation; it does not claim code, tests, measured alternatives, or production use.

**Reading the columns:** “Why” states the rationale in the implementation plan or a direct engineering implication of that rationale. “Instead of / accepted trade-off” is a **design-stage comparison**, *not* evidence that an alternative was prototyped or benchmarked. If a comparison needs factual verification or empirical results, the coding agent must record it as **OPEN** until tested. Section references point to the supplied master plan.

**Granularity policy:** If a future developer chooses a timeout, metric name, auth claim, schema field, default threshold, package version, log size, retry count, vector distance function, component route, UI empty state, testing tool, naming convention, or other behavior-bearing detail, **it gets its own record even if it seems minor**. Large decisions use full ADRs; small decisions use append-only `DEC-` entries. Mechanical edits that merely implement an already-recorded choice link back to its decision ID; don't fabricate new reasoning for each keystroke.

### A. Product, audience and release scope
| ID | Choice (DESIGN ONLY) | Reason | Alternative / trade-off | Source |
|---|---|---|---|---|
| `DEC-001` | Initial user: individual developers and small SRE teams | Narrow integration requirements and keep one coherent persona before adding enterprise complexity | Enterprise-wide observability product expands integration and governance needs | §0, §1.1 |
| `DEC-002` | Initial problem: reduce time spent triaging incidents across telemetry and changes | Gives the product a measurable outcome instead of generic AI chat | A general AI assistant would have no bounded operational success criterion | §0, §1.1 |
| `DEC-003` | Initial supported domain: HTTP APIs, PostgreSQL and Dockerized services | Failures can be recreated, instrumented and assessed reliably | Supporting every language/cloud on day one increases adapter and test coverage | §0 |
| `DEC-004` | Position as investigation layer, not Grafana/Datadog replacement | Existing telemetry products already handle ingestion, charts and alerting | Building a complete telemetry database would dilute the agent focus | §0 |
| `DEC-005` | First product promise: evidence-grounded hypotheses, not certainty | Root cause can be underdetermined from observations | Always asserting a diagnosis risks false conclusions | §0, §1.2 |
| `DEC-006` | Thin end-to-end slice before broad feature count | Tests value across collection, alerts, tools and report early | Many incomplete parallel features defer integration failures | §0, §1.3 |
| `DEC-007` | M0 deadline: fault -> alert -> incident -> read-only agent report | Provides a focused demonstration and explicit gate | Frontend-only or mocked incident demos cannot validate core value | §1.3, §17 |
| `DEC-008` | M1 scope: authenticated incident product plus evaluation and safe staging actions | Balances portfolio depth and attainable release size | Full enterprise platform in v1 would overextend scope | §1.3 |
| `DEC-009` | M2 agent-workflow failure detection postponed | Existing HTTP incident investigation must become reliable first | Launching both general SRE and agent debugging tracks doubles evaluation needs | §1.3 |
| `DEC-010` | M2 multi-agent only with measured gain | Avoid complexity until a single-agent baseline is trustworthy | Many-agent architecture is not a quality metric by itself | §1.3 |
| `DEC-011` | M2 production remediation excluded | Production infrastructure modification carries outsized risk | Fully autonomous production response is unsafe for portfolio v1 | §1.3, §8 |
| `DEC-012` | M2 hosted multi-tenant ingestion excluded | Requires metering, isolation and retention controls not proved in v1 | Open telemetry gateway creates high operational and privacy overhead | §1.3, §3.4 |
| `DEC-013` | Public visitor sees synthetic protected demo rather than customer data | Keeps demo safe, repeatable and lawful to share | Real logs can carry secrets and personal information | §0, §1.1 |
| `DEC-014` | One incident may have multiple investigation runs | Supports re-analysis, model comparisons and versioned findings | Coupling incident identity to one model run loses lifecycle/history | §4.2 |
| `DEC-015` | Allow an investigation to be marked inconclusive | Missing or conflicting telemetry is a valid outcome | Forcing an answer encourages fabricated certainty | §1.2, §4.3 |

### B. Architectural boundaries and source-of-truth choices
| ID | Choice (DESIGN ONLY) | Reason | Alternative / trade-off | Source |
|---|---|---|---|---|
| `DEC-016` | Five planes: telemetry, control, AI, automation and frontend | Separates distinct reliability, security and scaling concerns | One mixed service makes hot-path telemetry dependent on model latency | §3.2 |
| `DEC-017` | FastAPI control plane owns accounts, incidents and approvals | Authoritative changes should be deterministic and transactional | Putting mutable incident state inside an LLM or workflow engine risks inconsistency | §3.2 |
| `DEC-018` | Telemetry ingestion cannot block on the LLM | Preserve collection when a model is slow, unavailable or rate limited | Inline inference could lose alerts and amplify incident effects | §3.3, §14.2 |
| `DEC-019` | PostgreSQL is authoritative for incident and approval state | Relational constraints and durable audit are necessary for lifecycle correctness | n8n execution history or transient agent session is not operational truth | §0, §3.2 |
| `DEC-020` | ADK worker distinct from synchronous API request | Multi-step investigations outlive normal HTTP response windows | Synchronous request processing risks timeouts and poor UI responsiveness | §3.2, §4.3 |
| `DEC-021` | n8n handles integrations, not authoritative transitions | Notifications and tickets can retry without silently rewriting state | Workflow-engine-only ownership complicates approval and incident consistency | §3.2, §7.3 |
| `DEC-022` | Read observability data through existing backends first | Reduces storage duplication and integration scope | Hosting general raw log/trace ingestion in the product is deferred | §3.4, §5.2 |
| `DEC-023` | Raw logs/traces remain in Loki/Tempo rather than Postgres | Specialized stores already handle retention and retrieval | Mirroring all telemetry into relational tables adds cost and scale pressure | §5.2, §9.3 |
| `DEC-024` | Postgres stores bounded redacted evidence and source pointers | Makes reports auditable without copying whole telemetry collections | Persisting unrestricted raw telemetry increases privacy and storage risk | §9.3 |
| `DEC-025` | SSE for investigation progress with polling fallback | Progress arrives promptly and reconnects can recover persisted state | UI relying only on a live socket would lose updates after refresh | §3.2, §11.5 |
| `DEC-026` | Strong service ownership boundaries in schema from start | Tenant leakage is difficult to retrofit once query pathways spread | Pure single-user schemas lower initial code but weaken growth path | §3.3, §9.2 |
| `DEC-027` | Initial rollout private/restricted single-team demo | Limits operational burden until isolation has been verified | Open self-service SaaS is premature without privacy/retention controls | §0, §19.3 |

### C. Google ADK, models, tool calling and agent execution
| ID | Choice (DESIGN ONLY) | Reason | Alternative / trade-off | Source |
|---|---|---|---|---|
| `DEC-028` | Google ADK is the one primary agent framework | Focus implementation on investigation behaviors rather than custom runtime | Mixing ADK, LangGraph and other agent runtimes creates overlap and debugging cost | §0, §4 |
| `DEC-029` | Use Python ADK with a FastAPI ecosystem | Shared language supports typed contracts and test tooling | Splitting AI runtime into another language increases integration complexity | §0, §4 |
| `DEC-030` | Start with one incident_investigator agent | Simplifies traces, budgets and evaluation | Multi-agent orchestration is a later hypothesis to test, not a launch prerequisite | §4.1 |
| `DEC-031` | Snapshot incident/service/tenant/time-window before a run | Makes tool context reproducible and authorization bounded | Allowing dynamic untrusted model-selected scope invites cross-service access | §4.3 |
| `DEC-032` | Deterministic initial context retrieval | Agent receives compact, predictable information before exploration | Dumping entire observability histories creates cost and prompt overflow | §4.3 |
| `DEC-033` | Registered read-only tools only | Gives the model needed evidence without operational control | Generic shell, HTTP, SQL and privileged credentials expose unsafe capabilities | §4.4 |
| `DEC-034` | query_service_metrics only uses predefined metrics and query templates | Limits cardinality, abuse and accidental costly PromQL | Arbitrary PromQL generated by a model can be inefficient or unsafe | §4.4 |
| `DEC-035` | search_service_logs imposes time, row and byte bounds | Prevent huge results, runaway spend and accidental sensitive data exposure | Unlimited LogQL and unrestricted log dumps are rejected | §4.4 |
| `DEC-036` | get_trace_summary is restricted to authorized traces | Lets agent correlate latency and errors while preserving access boundaries | Global trace browsing would violate tenant/service scope | §4.4 |
| `DEC-037` | get_recent_deployments uses read-only GitHub access | Provides timing and code-change clues without write permissions | GitHub write capability is not needed for diagnosis | §4.4 |
| `DEC-038` | retrieve_runbook and get_related_incidents retain tenant filters | Avoid retrieving another organization's material | Model-provided tenant identifiers cannot be trusted | §4.4 |
| `DEC-039` | create_remediation_proposal does not execute anything | Cleanly separates recommendation and authorization | A model-generated tool call must not mutate production | §4.4, §8 |
| `DEC-040` | Structured Pydantic investigation result | Enables deterministic validation, storage and consistent UI | Free-form prose cannot be robustly checked for citation integrity | §4.5 |
| `DEC-041` | Confidence is low/medium/high label, not numeric probability | Model self-assessment is not calibrated risk estimation | Showing 94% confidence without calibration would mislead users | §4.5 |
| `DEC-042` | Track supporting and contradicting evidence per hypothesis | Avoid confirmation bias and support auditable reasoning | A single one-sided explanation can hide conflicting signals | §4.5 |
| `DEC-043` | Evidence IDs validated independently of model text | Detect invented or unauthorized citations | Prompt-only citation instructions are not a security or truth guarantee | §4.3, §4.5 |
| `DEC-044` | Keep logs, docs and GitHub content marked untrusted | External text may contain prompt injection instructions | Treating retrieved text as system instructions creates prompt-injection exposure | §4.6 |
| `DEC-045` | Redact secrets and cap prompt context | Reduce leak risk, cost and unsupported model assumptions | Sending entire unredacted stack traces is unnecessary and unsafe | §4.6 |
| `DEC-046` | Starting bound: at most 12 tool calls per run | Prevent loops and runaway query costs in demo | Unbounded agent steps have unpredictable latency and spend | §4.7 |
| `DEC-047` | Starting bound: 3 minute demo investigation ceiling | Makes requests controllable and failure behavior predictable | Infinite waiting prevents dependable UX and resource budgets | §4.7 |
| `DEC-048` | Starting bound: 2 concurrent runs per demo workspace | Protect local hardware and API quota from overload | Unlimited concurrency can starve the monitoring stack | §4.7 |
| `DEC-049` | Starting bound: up to 50 rows and 32 KB per log result | Reduce raw context and redaction workload | Dumping massive log results to the model impairs efficiency and safety | §4.7 |
| `DEC-050` | One bounded retry for transient read-only tool/model failures | Improves tolerance without uncontrolled retry storms | Blind retries of side-effectful actions risk duplicate effects | §4.7 |
| `DEC-051` | Separate durable Postgres run ledger from ADK session mechanics | Enables auditing and recovery even when framework session APIs change | ADK session data alone may not satisfy product audit invariants | §4.7 |
| `DEC-052` | Gemini API first, choose exact current model after eval | Matches ADK path while preserving evidence-based provider selection | Hardcoding an untested model version is brittle | §4.8 |
| `DEC-053` | Persist model ID, provider, prompt version and generation parameters | Necessary to reproduce varying model behavior | Reports without run configuration cannot be compared reliably | §4.8 |
| `DEC-054` | Do not build multi-provider adapter until genuinely needed | Avoid abstractions with no real second integration | Premature generic provider layers often obscure actual model constraints | §4.8 |
| `DEC-055` | MCP is optional post-MVP using existing scoped ToolGateway | Demonstrates interoperability only after core tools work reliably | MCP as MVP dependency would add another authorization and integration surface | §4.9 |
| `DEC-056` | No unrestricted MCP shells, web fetch or tenant selection | Preserve identical least-privilege policy across clients | Generic MCP tools would bypass the scoped gateway | §4.9 |

### D. Telemetry, alerts and incident normalization
| ID | Choice (DESIGN ONLY) | Reason | Alternative / trade-off | Source |
|---|---|---|---|---|
| `DEC-057` | Use a real Express/TypeScript shop-api as demo target | Produces genuine errors, spans and metrics for demonstration | Fake AI-created telemetry would not validate detection path | §5.1 |
| `DEC-058` | Provide /healthz, /products, /checkout and /metrics | Offer clear user journeys and stable fault-trigger endpoints | A dummy status page alone cannot exercise backend/database failures | §5.1 |
| `DEC-059` | Instrument HTTP and database spans with trace context | Allows correlating latency across request/dependency steps | Isolated uncorrelated logs make causal investigation weaker | §5.1 |
| `DEC-060` | Use structured JSON logs with service, environment and trace IDs | Supports filtering, joins and reproducibility | Arbitrary string logs are harder to correlate and redact | §5.1 |
| `DEC-061` | Include release version and Git SHA in telemetry | Allows investigation of deployment correlation | Without a release identifier, temporal clues are harder to verify | §5.1 |
| `DEC-062` | Expose RED metrics (rate/errors/duration) | These signals directly describe HTTP service health | CPU alone does not prove user-facing degradation | §5.1 |
| `DEC-063` | Use OpenTelemetry Collector for logs and traces | Standardize instrumentation, routing, batching and filtering | Writing a custom cross-language telemetry SDK is outside v1 scope | §5.2 |
| `DEC-064` | Prometheus scrapes metrics endpoints | Works with instrumented app and native alert rules | Sending all metrics through custom application database adds unnecessary work | §5.2 |
| `DEC-065` | Alertmanager groups and routes alert events | Separates alert detection from incident-management API | Directly asking AI to interpret every metric sample is costly and non-deterministic | §5.2 |
| `DEC-066` | Use Loki for logs and Tempo for traces | Specialized backends support signal-specific querying | Postgres-as-raw-log-and-trace store would complicate scale and retrieval | §5.2 |
| `DEC-067` | Verify native OTLP settings per telemetry backend | Loki and Tempo are not guaranteed interchangeable exporter configurations | Assuming one generic exporter will work can silently drop signals | §5.2 |
| `DEC-068` | Starter alert: sustained high 5xx ratio with volume guard | Captures meaningful customer-visible errors without low-traffic division noise | Triggering on a single 500 causes excessive false alerts | §5.3 |
| `DEC-069` | Starter alert: p95 latency spike with traffic guard | Captures slow service behavior at meaningful load | Average latency alone can hide slow tail requests | §5.3 |
| `DEC-070` | Starter alert: service up==0 after stability period | Detects outages without flapping on transient restarts | Instant fail on any missing scrape can create noise | §5.3 |
| `DEC-071` | DB saturation alert only if instrumented metrics exist | Avoid rules that look functional but never receive samples | Inventing a metric label or trusting illustrative PromQL risks broken detection | §5.3 |
| `DEC-072` | Normalize incoming alerts to one canonical event contract | Simplifies provider adaptation and consistent incident history | Storing opaque provider payloads only couples UI and logic to Alertmanager | §5.4 |
| `DEC-073` | Deduplicate using workspace/source/fingerprint/episode | Prevent repeated delivery from multiplying incidents | Assuming webhooks are delivered exactly once is unsafe | §5.4 |
| `DEC-074` | Retain delivery counts/timestamps for duplicates | Dedup should not erase evidence of repeated alert delivery | Silently dropping repeats loses operational signal | §5.4 |
| `DEC-075` | Correlate alerts by service and bounded incident window | Groups related symptoms while limiting unrelated merges | Merging all recent alerts risks inventing a single cause | §5.4 |
| `DEC-076` | Treat firing and resolved events separately | Keeps incident lifecycle faithful to actual monitoring updates | One boolean event cannot handle clear/reopen transitions safely | §5.4 |
| `DEC-077` | Accept out-of-order and replayed webhooks | Real deliveries may retry or arrive late | Sorting strictly by arrival time causes incorrect timeline transitions | §5.4 |
| `DEC-078` | First demo uses local Docker Compose observability | Can verify entire signal path without cloud fees or credentials | External observability connectors initially increase troubleshooting scope | §5.5 |
| `DEC-079` | Bring-your-own telemetry connectors after core slice | Useful for existing SRE teams once adapter boundaries work | Hosted ingestion is significantly more expensive and sensitive | §5.5 |
| `DEC-080` | Optional URL probe must block SSRF and internal hosts | Prevent external checks becoming an internal network scanner | Naively fetching arbitrary URLs allows metadata and private-network access | §5.5 |

### E. RAG, documents and retrieval quality
| ID | Choice (DESIGN ONLY) | Reason | Alternative / trade-off | Source |
|---|---|---|---|---|
| `DEC-081` | RAG corpus limited to runbooks, architecture docs and verified postmortems | Directly supports operational explanations and next steps | Generic internet knowledge is not evidence of this service's incident | §6.1 |
| `DEC-082` | RAG means retrieval, not fine-tuning | Documents change and need citations/versioned deletion | Fine-tuning is not the proposed method for current document facts | §6.1 |
| `DEC-083` | Allow initially Markdown and text, PDF optional | Simpler safe extraction and heading preservation for MVP | Broad arbitrary file support adds parsing and security risk | §6.2 |
| `DEC-084` | Validate file type, MIME, size, owner and active content | Documents are untrusted uploads that may contain hazards | Trusting file extension alone is insufficient | §6.2 |
| `DEC-085` | Extract section hierarchy and revision metadata | Improves specific citations and outdated-document filtering | Unstructured text blobs lose provenance and useful boundaries | §6.2 |
| `DEC-086` | Redact secrets before embedding/external model calls | Prevent sensitive information flowing into model input or indexes | Document ownership does not imply safe model disclosure | §6.2 |
| `DEC-087` | Start semantic chunks around 400–800 tokens; tune later | Balances retrieval granularity and context completeness | Fixed enormous chunks reduce precision; tiny chunks lose context | §6.2 |
| `DEC-088` | Record embedding model, dimension and document version | Necessary for reproducible indexing and migrations | Silent model changes can break similarity indexes | §6.2 |
| `DEC-089` | Use pgvector plus Postgres full-text search | Captures both semantic similarity and exact incident/error terms | Vector-only retrieval can miss codes and stack identifiers | §6.2–§6.3 |
| `DEC-090` | Apply tenant/service authorization before ranking | Prevents unauthorized chunks entering result candidates | Post-ranking filtering may expose metadata or distort relevance | §6.3 |
| `DEC-091` | Use scoped hybrid fusion/weighting initially | Tests whether lexical plus semantic improves recall | A reranker is deferred until gain is demonstrated | §6.3 |
| `DEC-092` | Reject stale or contradictory runbook authority | Old instructions may conflict with current deployment configuration | Relevance score does not establish current operational validity | §6.3 |
| `DEC-093` | Return chunk IDs, section, revision and hashes | Makes passage citations resolvable and auditable | Generated links without persisted provenance can be fabricated | §6.3 |
| `DEC-094` | Test deletion and reindexing of embeddings | Prevent documents lingering after their owners remove them | Deleting only file metadata leaves searchable residual content | §6.2–§6.4 |
| `DEC-095` | Prepare 30+ judged retrieval questions with negative cases | Gives measurable recall@5 and no-answer behavior | A few subjective examples cannot establish retrieval quality | §6.4 |
| `DEC-096` | Do not treat retrieved runbook as proof of actual cause | Generic instructions are supporting context, not telemetry observations | RAG relevance does not establish incident causality | §6.4 |

### F. n8n integrations and reliable automation
| ID | Choice (DESIGN ONLY) | Reason | Alternative / trade-off | Source |
|---|---|---|---|---|
| `DEC-097` | Use self-hosted n8n Community for operator-authored workflows | Adds flexible integration while controlling initial software spend | A custom integrations framework costs time; customer SaaS editing may violate license | §7.1 |
| `DEC-098` | Do not embed n8n workflow editor for customers in v1 | Avoid a license conflict and expanded tenancy attack surface | Customer-controlled automation requires license and governance review | §7.1 |
| `DEC-099` | Incident-created notification workflow | Provides timely handoff without coupling notification to detection logic | Manual-only checking of dashboard slows response | §7.2 |
| `DEC-100` | Incident-investigated workflow includes uncertainty and evidence link | Prevent receivers interpreting a hypothesis as a confirmed root cause | Sending only a confident summary could mislead operators | §7.2 |
| `DEC-101` | Approval-requested workflow notifies but cannot approve | Keep authorization in AegisOps access control | Approving inside an unverified webhook/chat action is unsafe | §7.2 |
| `DEC-102` | Incident-resolved workflow sends lifecycle update | Prevent notifications remaining misleading after recovery | Only initial alerts would leave responders without closure | §7.2 |
| `DEC-103` | Optional postmortem export/GitHub issue via preauthored workflow | Produces useful artifacts through controlled integration | Arbitrary model-created external tickets are not needed for MVP | §7.2 |
| `DEC-104` | Write outbox event in same transaction as state change | Avoid lost notifications between DB commit and HTTP webhook call | Sending directly before commit causes ghost/missing events on crash | §7.3 |
| `DEC-105` | Deliver signed payload with idempotency key | Supports retries without duplicate issues/messages | Plain unsigned webhooks invite spoofing and replay | §7.3 |
| `DEC-106` | Exponential backoff and failed-delivery tracking | Handle third-party outages observably | Fire-and-forget network requests silently lose notifications | §7.3 |
| `DEC-107` | Only operator-configured n8n endpoints | Avoid model choosing arbitrary destinations or exfiltration targets | Direct agent-supplied URLs create SSRF and data exposure risk | §7.3 |
| `DEC-108` | Version n8n workflow exports in automations/n8n | Makes integrations reviewable and reproducible | UI-only unversioned workflows are difficult to audit and restore | §7.3 |

### G. Human approval, response and action policy
| ID | Choice (DESIGN ONLY) | Reason | Alternative / trade-off | Source |
|---|---|---|---|---|
| `DEC-109` | Default AI ability is proposal creation only | AI analysis must not silently become execution authority | Direct production restart/rollback is inappropriate for v1 | §8.1 |
| `DEC-110` | Staging actions from allowlisted catalog only | Deterministic executors can be tested and authorized | Free-form shell commands or generated scripts are not allowed | §8.1 |
| `DEC-111` | No real production action execution in portfolio v1 | Safety and correctness have not been field-proven | Impressive autonomous demo is not sufficient justification for real access | §8.1 |
| `DEC-112` | Require target service, environment and workspace in action | Prevents approval being reused on wrong infrastructure | Target inferred only from chat context may be wrong | §8.2 |
| `DEC-113` | Immutable action parameters and action hash | Ensures approver saw exactly what executor will run | Editable parameters between approval and execution permit tampering | §8.2–§8.3 |
| `DEC-114` | Proposal expiry/TTL | An old approval may become unsafe after state changes | Non-expiring approval could authorize stale remediation | §8.2–§8.3 |
| `DEC-115` | Link proposed action to supporting evidence IDs | Reviewers can assess whether recommendation has basis | Unexplained action recommendations are hard to audit | §8.2 |
| `DEC-116` | Record approver identity and full audit metadata | Enables accountability and incident reconstruction | Status-only tracking hides who approved what | §8.2 |
| `DEC-117` | Recheck RBAC and environment policy at execution time | Permissions and target state may have changed since approval | Trusting an earlier approval check permits time-of-check/use errors | §8.3 |
| `DEC-118` | Use transactional compare-and-set/idempotency for execution | Prevent two workers executing one approved action twice | Application-level Boolean guards alone can race | §8.3 |
| `DEC-119` | ADK human-confirmation UX is optional, not sole control | Backend policy remains authoritative across framework changes | Model/framework dialog is not a security boundary | §8.4 |
| `DEC-120` | Approval changes or expiration require fresh approval | Guarantees signed-off parameters remain exact | Silent amendment of a proposal voids informed approval | §1.2, §8.3 |

### H. Data modeling, API contracts, authentication and UX
| ID | Choice (DESIGN ONLY) | Reason | Alternative / trade-off | Source |
|---|---|---|---|---|
| `DEC-121` | Use organizations, memberships and services tables | Enables tenant ownership and RBAC on core records | One global incidents table without ownership risks cross-user leakage | §9.1–§9.2 |
| `DEC-122` | Separate alert_events, incidents and incident_events | Distinguishes incoming signal, correlated operational issue and timeline | One overloaded table loses event and incident lifecycle semantics | §9.1 |
| `DEC-123` | Separate investigation_runs and tool_executions | Preserve per-run history and tool failures independently | One summary field is not sufficient for debugging agents | §9.1 |
| `DEC-124` | Separate evidence_items, hypotheses and join records | Captures many-to-many supporting/contradicting evidence | Embedding evidence only as free-text explanation prevents validation | §9.1 |
| `DEC-125` | Separate approvals, proposals and executions | Explicitly model intent, authorization and action outcome | One action status field cannot prove who approved exact parameters | §9.1 |
| `DEC-126` | Store UTC timestamps as Postgres timestamptz | Avoid timezone ambiguity across alerts and deployments | Local-time strings are error-prone for incident correlation | §9.2 |
| `DEC-127` | Use uniqueness/foreign keys for consistency | Enforces invariants under concurrent requests | Application-only checks can race or be bypassed | §9.2 |
| `DEC-128` | Prefer PostgreSQL RLS as extra tenant defense if tested | Adds query-level barrier beyond app checks | RLS without disciplined session context can itself be misconfigured | §9.2 |
| `DEC-129` | Use Alembic migrations with restore/downgrade plan | Makes schema evolution reproducible and reversible | Manual schema edits are difficult to audit/deploy | §9.2 |
| `DEC-130` | Index common workspace/service/time access paths | Supports normal incident filtering as volume increases | Indexing every field wastes write/storage without workload evidence | §9.2 |
| `DEC-131` | Version public API under /api/v1 | Gives clients explicit contract evolution path | Unversioned endpoints complicate breaking changes | §10 |
| `DEC-132` | Use typed JSON, uniform errors and generated OpenAPI | Enables reliable frontend contracts and debugging | Ad-hoc shapes become fragile between Python and TypeScript | §10 |
| `DEC-133` | Prefer secure HttpOnly session cookies and mature auth/OIDC | Keep browser credentials off JS and avoid unnecessary custom crypto | Hand-rolled JWT authorization adds security burden | §10.1 |
| `DEC-134` | Use server-authenticated identity to derive tenant scope | Stops browsers or LLMs spoofing organization IDs | Client-supplied tenant ID alone cannot authorize access | §9.2, §10 |
| `DEC-135` | Paginate incidents and bound request sizes | Prevent slow list endpoints and oversized ingestion requests | Unbounded responses will degrade with traffic growth | §10.4 |
| `DEC-136` | Use idempotency keys on mutable APIs | Helps safely retry requests after network errors | Blind retries can create duplicate investigations/proposals | §10.4 |
| `DEC-137` | Use Next.js, TypeScript, Tailwind and shadcn/ui | Gives typed UI foundation and reusable accessible components | Ad-hoc UI implementation lengthens product polish work | §0, §11 |
| `DEC-138` | Use incident-focused dark utilitarian visual design | Supports reading telemetry and communicating operational urgency | Heavy 3D effects distract and can harm console performance | §11.1 |
| `DEC-139` | Center incident detail on timeline, metrics, hypotheses and evidence | Lets users inspect the complete cause/evidence chain | Chat-only interface hides critical operational context | §11.3 |
| `DEC-140` | Provide precise loading, missing-data and inconclusive UI states | Avoid treating unknown as success or hiding source outages | Generic spinner/error toast would obscure reliability state | §11.4 |
| `DEC-141` | Make charts accessible through text/tabular equivalents | Status and numeric data must be usable beyond visual cues | Color-only charts exclude some users and complicate interpretation | §11.5 |
| `DEC-142` | Persist run progress and reconnect SSE clients safely | Users can refresh without losing the investigation | Ephemeral socket-only state is fragile | §11.5 |
| `DEC-143` | Virtualize large log lists and use incremental loading | Prevent excessive frontend memory and network work | Fetching entire history for every incident makes UI sluggish | §11.5 |

### I. Incident Simulation Lab and objective evaluation
| ID | Choice (DESIGN ONLY) | Reason | Alternative / trade-off | Source |
|---|---|---|---|---|
| `DEC-144` | Build dedicated fault injection lab with real telemetry | Establishes known ground truth and compelling portfolio proof | Fake output from a mocked incident does not show a working monitor | §12.1 |
| `DEC-145` | Use controlled 500 errors as first scenario | Simple, deterministic signal for first real pipeline | Hard-to-reproduce failures would slow early integration | §12.2 |
| `DEC-146` | Include slow DB and pool-exhaustion faults | Exercise tracing and dependency-level reasoning | Testing only 500 errors underrepresents performance incidents | §12.2 |
| `DEC-147` | Include bad deployment linked to Git SHA | Test causal correlation between release and regression | Without deployment cases GitHub integration lacks measured value | §12.2 |
| `DEC-148` | Include service stop and downstream slowness | Cover availability and dependency latency failure classes | Only in-process exceptions cannot validate infrastructure symptoms | §12.2 |
| `DEC-149` | Include benign noisy logs and missing telemetry | Test false-positive handling and honest abstention | Scenarios containing obvious errors only inflate measured accuracy | §12.2 |
| `DEC-150` | Include malicious log prompt-injection scenario | Verify prompt boundaries and tool policy under adversarial input | Normal data tests do not exercise injection risk | §12.2 |
| `DEC-151` | Include overlapping failures and out-of-order alerts | Test ambiguity, grouping and lifecycle robustness | Isolated linear incidents oversimplify operational reality | §12.2 |
| `DEC-152` | Fault triggers restricted to isolated demo administrator | Stop public controls from manipulating real infrastructure | Unauthenticated fault endpoints would be exploitable | §12.3 |
| `DEC-153` | Auto-expire faults and provide deterministic reset | Protect shared demo stability and reproducibility | Manual-only cleanup can leave faults active accidentally | §12.3 |
| `DEC-154` | Version scenario manifests with seeds and expected causes | Makes replay and diagnosis comparisons repeatable | Informal manual scenarios cannot be reliably scored | §12.4 |
| `DEC-155` | Use unit, integration, system, frontend, fault and security tests | Different levels catch different classes of failure | Unit tests alone do not prove end-to-end telemetry and authorization | §13.1 |
| `DEC-156` | Build 40–60 incident cases with at least 25 held-out causes | Separate tuning from final accuracy reporting | Measuring prompts on development examples overstates quality | §13.2 |
| `DEC-157` | Hold out ambiguous, adversarial and no-incident cases | Measure uncertainty and defensive behavior explicitly | Accuracy on only obvious incidents gives biased impression | §13.2 |
| `DEC-158` | Compare B0 deterministic, B1 logs-only LLM, B2 tools, B3 tools+RAG | Isolate incremental contribution of AI, telemetry and retrieval | Reporting one B3 score cannot show added value | §13.2 |
| `DEC-159` | Measure citation correctness and unsupported assertions | Plausible narratives are not always grounded | LLM-as-judge alone cannot verify actual operational causes | §13.2 |
| `DEC-160` | Measure diagnosis, abstention, latency, tool counts and USD/incident | Balance quality, safety and running cost | Maximizing apparent accuracy alone can produce expensive risky behavior | §13.2 |
| `DEC-161` | Use ADK eval plus deterministic/domain human scoring | Combine framework trajectory checks with real ground-truth judging | Generic model judge can share the investigated model's biases | §13.2 |
| `DEC-162` | Freeze model, prompt, tool versions and dataset hash for evaluation | Make results reproducible despite model/provider changes | Unversioned score claims are not defensible | §13.3 |
| `DEC-163` | Do not publish target metrics as achieved performance | Avoid fabricated resume claims | Plan targets are goals until tests are actually run | §2, §13.3 |
| `DEC-164` | Enforce zero unsupported citation and unauthorized execution in gates | Some failure classes are unacceptable even with high mean accuracy | Aggregate success rates can hide critical safety regressions | §2, §13.3 |

### J. Reliability, security and privacy details
| ID | Choice (DESIGN ONLY) | Reason | Alternative / trade-off | Source |
|---|---|---|---|---|
| `DEC-165` | Verify webhook source/signature, timestamp and replay protection | External alert delivery is untrusted input | A publicly reachable unauthenticated webhook can create fake incidents | §3.3, §14.1 |
| `DEC-166` | Treat telemetry and model output as untrusted | Logs and generated responses may contain adversarial commands | Prompt wording alone cannot protect system authority | §3.3 |
| `DEC-167` | Server holds connector secrets, never model or browser | Enforces least privilege and limits exfiltration surface | Tokens in browser, chat prompts or tool outputs are unacceptable | §3.3 |
| `DEC-168` | Use TLS and encrypted provider credentials at rest | Operational integrations access sensitive production-adjacent data | Storing clear-text tokens increases compromise impact | §14.1 |
| `DEC-169` | Apply outbound SSRF controls and private CIDR blocking | Prevent probes/connectors reaching internal metadata or hosts | Arbitrary agent-selected URLs expand attack surface | §14.1 |
| `DEC-170` | Apply CSRF, cookie hardening and CORS allowlist | Protect authenticated browser operations and approvals | Permissive cross-origin settings can expose session workflows | §14.1 |
| `DEC-171` | Do not expose Redis, DB, n8n editor or telemetry admin endpoints publicly | These are trusted infrastructure services | Public admin ports invite compromise and data exfiltration | §14.1 |
| `DEC-172` | Use per-tenant tool and DB checks | Security must hold across API, workers, RAG and evidence browsing | UI-only access restrictions are bypassable | §14.1 |
| `DEC-173` | Scan dependencies, containers and committed secrets | Catch known vulnerabilities before public deployment | Manual review alone misses known packages and accidental credentials | §14.1 |
| `DEC-174` | Use transactional outbox and idempotent consumers | Delivery is normally at-least-once, not magically exactly-once | Fire-and-forget delivery can lose messages on crash | §14.2 |
| `DEC-175` | Prevent duplicate run creation under concurrent alerts | Guard costly model jobs against race conditions | Dedup in only one worker does not handle multiple consumers | §14.2 |
| `DEC-176` | Heartbeat and recover stale worker runs | Worker process may die mid-investigation | A perpetual RUNNING status hides lost work | §14.2 |
| `DEC-177` | Cancellation must revoke subsequent tool authorization | Stop expensive/stale execution, not just hide UI output | Cosmetic cancellation can allow background work to continue | §14.2 |
| `DEC-178` | Use timeouts, bounded jittered retries and queue limits | Reduce cascading failures during upstream outages | Infinite retries make incidents worse under load | §14.2 |
| `DEC-179` | Monitoring must continue during Gemini outage | Deterministic system should retain core value without AI | Failure of external LLM should not halt alert ingestion | §14.2 |
| `DEC-180` | Backup and test restoring actual PostgreSQL state | Backup success alone does not prove recovery | Untested backups can fail exactly when needed | §14.2 |
| `DEC-181` | Have retention and deletion policy for incident and telemetry data | Limit storage/privacy impact and stale retrieval | Retaining everything forever is unnecessary and risky | §14.2 |
| `DEC-182` | Disallow Docker socket, SSH root and Kubernetes admin from agent | These primitives allow broad unauthorized infrastructure changes | LLM tool input cannot be treated as privileged operator instruction | §14.3 |

### K. Repo operations, resource budgets and launch discipline
| ID | Choice (DESIGN ONLY) | Reason | Alternative / trade-off | Source |
|---|---|---|---|---|
| `DEC-183` | Use monorepo with apps/web, apps/api, apps/worker and integrations | Keep shared contracts/documentation discoverable for solo development | Premature multi-repo/microservices adds release coordination burden | §15 |
| `DEC-184` | Keep API and worker able to share Python package where appropriate | Avoid duplicating business models, config and permissions | Strict independent microservices too early can fragment authority | §15 |
| `DEC-185` | Pin Python/Node/ADK/infra versions and use lockfiles | Reproducible builds and auditable upgrades | latest tags risk silent incompatible changes | §3.5 |
| `DEC-186` | Maintain exact installed versions in TECH_STACK_LOCK.md | Permits interview reproduction and debugging version-specific APIs | Generic tech-stack slogans omit implementation details | §3.5 |
| `DEC-187` | Coding assistant reads plan/state/ADR before changes | Prevent scope drift and repeated architectural mistakes | Agent writing code without context can violate phase gates | §16.2 |
| `DEC-188` | Code change always includes relevant tests and exact outcomes | Provides verifiable quality evidence rather than self-reported completion | Untested generated code is not a release gate | §16.2 |
| `DEC-189` | No hosted CI green claims unless hosted run inspected | Distinguish local success from actual GitHub status | Assuming CI passed creates false release readiness | §16.2 |
| `DEC-190` | Keep phase-complete reports with paths, results, blockers and security | Makes status auditable and resume interview preparation easier | Vague percent-complete estimates are not proof | §16.3 |
| `DEC-191` | Week 1 requires pinned ADK tool-calling smoke test | Proves highest-risk framework feature before large buildout | UI scaffolding alone doesn't de-risk AI integration | §17 P0 |
| `DEC-192` | Week 2 requires injected fault -> real deduped alert -> incident | Validates the ingestion pipeline before introducing agent explanations | Mock incident creation cannot prove monitoring integration | §17 P1 |
| `DEC-193` | Week 3 requires sourced diagnosis and false citation rejection | Proves end-to-end AI differentiation and integrity | A plausible text answer without source verification is inadequate | §17 P2 |
| `DEC-194` | Release gates include authorization, restore, performance and security tests | Credible production-oriented portfolio needs failure-path proof | Polished happy-path demo alone is insufficient | §17 P10–P11, §22 |
| `DEC-195` | If behind schedule, cut animation and optional agents before tests/security | Protect core correctness and measurable differentiator | Removing verification just to meet date devalues resume claims | §17 |
| `DEC-196` | Start with local Compose profiles core/observability/automation/lab | Reduce memory pressure on development machine | Running full stack 24/7 on constrained RAM leads to thrashing | §19.2 |
| `DEC-197` | Prefer hosted Gemini over local LLM on constrained laptop | Avoid competing for RAM with observability containers | Local model plus Tempo/Loki/etc may exceed practical machine resources | §19.2 |
| `DEC-198` | Budget Gemini tool runs and record actual API cost | Free tier quotas are separate from consumer subscriptions | Unbounded experiment spending creates financial and availability risks | §19.1 |
| `DEC-199` | Deploy local -> private staging -> restricted public demo | Advance access only as boundaries and proof mature | Anonymous full-access production SaaS is not an appropriate first rollout | §19.3 |
| `DEC-200` | Keep admin and telemetry backends private behind TLS gateway | Reduce exposed attack surface while preserving public demo experience | Publishing internal Grafana/n8n/DB ports is unsafe | §19.4 |
| `DEC-201` | Record video, architecture, test commands and measured results in README | Let recruiters verify the end-to-end engineering work | Resume claims without proof links are easy to dismiss | §21, §22 |
| `DEC-202` | Use a 12-week schedule plus 2-week contingency, not a guarantee | Time is a planning constraint and uncertainty remains | Declaring production readiness by calendar date alone is misleading | §17, §20 |

**Baseline total: 202 separately reasoned decisions, all DESIGN ONLY.** The 16 detailed ADRs below provide deeper interview-focused explanations for the highest-impact architectural choices.


## 1B. Append-only micro-decision and implementation reasoning log

**Start here once coding begins.** The initial `DEC-` rows describe *what the blueprint proposes*. Actual implementation choices need their own next sequential `DEC-` IDs unless they are direct execution of an existing entry with no new design trade-off. Do not overwrite baseline rationale to claim a result; add an implementation update or a superseding record with evidence.

Every new choice, including a small setting or a rejected workaround, MUST capture these fields:

```markdown
### DEC-<next-id> — Short specific question answered
- Date/time (UTC): YYYY-MM-DDTHH:MM:SSZ
- Phase / work item: P# / issue link
- Scope: file(s), endpoint, workflow or component
- Status: PROPOSED | ACCEPTED-DESIGN | IMPLEMENTED-UNVERIFIED | VERIFIED | REJECTED | SUPERSEDED | OPEN
- Trigger / problem: What forced this choice?
- Constraints: Budget, device, permissions, API behavior, performance, release gate
- Selected choice: Exact setting/design/behavior and important defaults
- Alternatives: Real options evaluated; if none, state 'Not evaluated yet'
- Why selected: Mechanism and expected benefit, not 'best practice' alone
- Costs / failure modes: Downside and risks consciously accepted
- Evidence level: MASTER-PLAN | REASONED-HYPOTHESIS | DOC-CONFIRMED | TESTED | MEASURED
- Evidence: Plan § / official pinned doc / code ref / test command + output / benchmark N, p50/p95, etc., or 'Not yet tested'
- When to revisit: Measurable trigger or dependency change
- Interview answer: 2–4 sentences: problem, alternatives, trade-off, demonstrated outcome (only if verified)
- Related ADR/DEC: IDs, PR, commit, incident, test
```

**During a coding change:** (1) identify *all* new decisions; (2) append or revise proposed entries before implementation; (3) update them with paths/tests after implementation; (4) include IDs in the phase report and agent response. A PR with new code but no journal change must explicitly list the existing decision IDs that fully cover it, or remain incomplete.

**Examples of micro choices that must be captured:** `httpx.Timeout(10) vs 30 seconds`, a PromQL minimum request-volume threshold, event fingerprint composition, Celery retry jitter, ADK max steps, JWT/cookie TTL, table index, embedding dimensions, chunk overlap, job queue concurrency, third-party SDK patch version, trace retention days, chosen icon/status copy for inconclusive UI. **Don't invent values today:** log the exact value and reason only when chosen during implementation.

**What does not count as a new decision:** Formatting, a typo correction, or direct mechanical execution of a choice already documented **without** adding a new behavior, dependency, risk, or trade-off. Such code changes still reference the relevant decision ID.

### Current implementation events

_No implementation events recorded. Add first actual entry at Phase 0, before the first meaningful coding choice._

### Assumption/verification queue

- `OPEN-001`: Exact stable Google ADK, Gemini API, Next.js, Python and telemetry package versions and their pinned contracts (master plan §3.5 and §17 P0).
- `OPEN-002`: Gemini model pricing/quota/privacy treatment and comparative tool-calling results (master plan §4.8, §19.1).
- `OPEN-003`: Concrete Prometheus metric/label names and actual threshold tuning from observed sample traffic (master plan §5.3).
- `OPEN-004`: Exact embedding model/dimensions, vector index strategy, lexical/vector weighting, reranker value (master plan §6).
- `OPEN-005`: Real workstation RAM footprint and which Compose profiles can coexist (master plan §19.2).
- `OPEN-006`: Measured SLOs, RCA accuracy, RAG recall, token cost and safe behavior (master plan §2 and §13).
- `OPEN-007`: Current n8n Community/license terms before any customer-configurable automation or commercial SaaS expansion (master plan §7).
- `OPEN-008`: Whether multi-agent or MCP integration offers measurable benefit beyond the single ADK agent (master plan §4.1 and §4.9).
- `OPEN-009`: External hosted monitoring connector authentication and egress requirements (master plan §5.5).
- `OPEN-010`: Public demo readiness after auth, isolation, secret scans and failure recovery tests (master plan §19.3 and §22).

**Interview accuracy rule:** Do not say “I measured,” “I optimized,” “I deployed,” or “I reduced” unless the record links actual reproducible evidence. A sound proposed trade-off is worth discussing as a design choice, not an accomplished outcome.


## 2. Initial architectural decision records

### ADR-001 — Choose Google ADK as the agent framework
- **Date:** 2026-10-10
- **Status:** ACCEPTED — DESIGN ONLY
- **Problem and constraints:** Need a maintainable Python agent that can call bounded investigation tools, preserve conversational state, and be evaluated; developer also wants to learn agent building for AI-focused FDE roles.
- **Decision:** Use **Google ADK (Python)** as the *single* primary agent framework for v1, encapsulated by an AegisOps-specific agent adapter. Pin and test its exact package version.
- **Alternatives compared:** **LangGraph** — explicit graph/state control and checkpoint-centric workflows, but more orchestration design for this initial agent; **OpenAI Agents SDK** — strong lightweight agent toolkit, but different provider/ecosystem emphasis; **custom tool loop** — maximum control but substantial orchestration and instrumentation code to maintain.
- **Why this wins for AegisOps:** Shortens the time to an initial evidence-gathering agent, fits Python tooling and the planned Gemini-first stack, while the application remains responsible for authorization, durability, and outputs.
- **Costs / downsides:** Dependency on ADK API semantics and release maturity; not every agent feature automatically guarantees correct recovery, durability, or authorization. Changing frameworks later requires adapting sessions/tools/tests.
- **Proof / verification:** Not implemented. Validate against an ADK spike: execute 4 read-only tools, handle a timeout, persist run metadata, validate typed output, and rerun an evaluation fixture.
- **Revisit when:** ADK cannot meet measured state recovery, tooling, latency, or model-provider requirements without unacceptable workarounds.
- **Interview answer:** “I chose Google ADK over building an agent runtime so I could focus on incident-investigation logic. LangGraph offered stronger low-level workflow control, but my initial requirement was a bounded tool-using agent. I kept policy checks, persistence, and evidence validation outside the agent so the system was not dependent on its framework for security.”
- **Follow-up questions:** Why not LangGraph? Could ADK be replaced? Which responsibilities must stay outside the agent?

### ADR-002 — Start with one investigation agent, not many
- **Date:** 2026-10-10
- **Status:** ACCEPTED — DESIGN ONLY
- **Problem and constraints:** Too many autonomous agents can increase coordination complexity, token spend, trace debugging, and failure modes before a baseline exists.
- **Decision:** Launch a single `incident_investigator` with registered tools. Consider specialist agents only after showing measured improvement.
- **Alternatives compared:** Multi-agent triage/log/RCA/recovery team — potentially parallel specialization, but orchestration overhead; deterministic rule-only engine — easy to reason about, but weaker at correlating unstructured evidence.
- **Why this wins:** One clear execution trace, bounded step count, simpler evaluation and safety model.
- **Costs / downsides:** A single agent may have more context to manage and less specialized focus.
- **Proof / verification:** Not implemented. Benchmark cost/accuracy/latency before any multi-agent redesign.
- **Revisit when:** A specialist produces repeatable gains on held-out scenarios large enough to justify added cost and complexity.
- **Interview answer:** “I intentionally avoided multi-agent complexity initially. One agent gave me a reproducible baseline, and I planned to add specialist agents only if evaluations showed better diagnoses or efficiency.”

### ADR-003 — Gemini API first, model ID configurable
- **Date:** 2026-10-10
- **Status:** ACCEPTED — DESIGN ONLY
- **Problem and constraints:** Need structured outputs/tool calls at a predictable cost; Gemini developer API availability and quotas can change. Consumer subscriptions are not general API credits.
- **Decision:** Use a currently supported Gemini API model after evaluating accuracy, tool-call behavior, latency, and cost; store provider/model/prompt version per run. Do **not** hardcode a specific model family as permanent.
- **Alternatives compared:** OpenAI API — another capable paid provider; local Ollama — possible no marginal token cost, but local hardware and tool-calling quality constraints; hardcoded model — simpler, but brittle.
- **Why this wins:** Pairs naturally with ADK and supports fast prototyping; a configurable setting avoids assumptions about which model or quota remains available.
- **Costs / downsides:** API spend and availability; privacy concerns when telemetry is sent to a third party; provider features differ.
- **Proof / verification:** Not measured. Build a representative evaluation dataset before locking final model configuration.
- **Revisit when:** Another model clearly improves verified diagnosis quality, cost, or data-governance fit.
- **Interview answer:** “I chose a Gemini-first configuration, not permanent vendor lock-in. The model is selected by measured tool-use reliability, evidence quality, and cost, and every run records its version for reproducibility.”

### ADR-004 — FastAPI for the core backend
- **Date:** 2026-10-10
- **Status:** ACCEPTED — DESIGN ONLY
- **Problem and constraints:** Need typed APIs, asynchronous request handling, Python agent integration, security middleware, and integration tests.
- **Decision:** Use FastAPI with Pydantic for the control plane. Long investigations run in workers, **not** inside HTTP handlers.
- **Alternatives compared:** Node.js/Express — strong ecosystem and developer familiarity, but would need Python interop for the chosen agent; Django — integrated batteries, but more opinionated features than the initial services require; NestJS — clear structure but another language runtime.
- **Why this wins:** Shared Python types and libraries around ADK, retrieval, and evaluations, without cross-language RPC in the initial MVP.
- **Costs / downsides:** Python runtime CPU limitations require worker separation; async endpoints can still block if used incorrectly.
- **Proof / verification:** Not implemented. Add typed OpenAPI contracts, API integration tests, load testing, and background task separation.
- **Revisit when:** Workload or team requirements justify additional services or another language for a performance-critical boundary.
- **Interview answer:** “I used FastAPI because the AI layer and evaluation stack were Python-based. It simplified integration and typed contracts; long-running LLM calls were moved to workers rather than blocking API requests.”

### ADR-005 — Next.js + TypeScript for the UI
- **Date:** 2026-10-10
- **Status:** ACCEPTED — DESIGN ONLY
- **Problem and constraints:** Need a polished incident dashboard, protected routes, streaming investigation status, robust data visualization, and maintainable UI contracts.
- **Decision:** Use Next.js with TypeScript and a typed FastAPI client. Render incident-state changes via SSE, with a polling fallback.
- **Alternatives compared:** Vite + React SPA — simpler and potentially lighter for an authenticated dashboard; server-rendered Python templates — fewer frontend tools but less flexible interactive visualization.
- **Why this wins:** Familiar React ecosystem with routing and a clear application structure; useful for full-stack interviews. **Do not claim SSR as a performance benefit for private dashboards unless measured.**
- **Costs / downsides:** Additional framework complexity and separate frontend deployment/runtime.
- **Proof / verification:** Not implemented. Compare performance/accessibility metrics once dashboard exists.
- **Revisit when:** A Vite SPA is demonstrably simpler for the actual UI without sacrificing requirements.
- **Interview answer:** “I chose TypeScript/Next.js for a maintainable, highly interactive incident console and typed contracts. I acknowledge a plain React SPA could have been simpler and would reconsider that if the server-rendering features don't add value.”

### ADR-006 — Reuse observability standards, don't reinvent telemetry
- **Date:** 2026-10-10
- **Status:** ACCEPTED — DESIGN ONLY
- **Problem and constraints:** Need genuine metrics, logs, and traces with consistent service/time attribution without inventing a monitoring protocol.
- **Decision:** Instrument with OpenTelemetry; use Prometheus + Alertmanager for metrics/alerts, Loki for logs, and Tempo for traces.
- **Alternatives compared:** Custom ingestion/monitoring stack — maximum control but huge scope and reliability risk; managed Datadog/New Relic — quick to integrate but can create recurring fees, external dependencies, and limited demo control; logs-only analysis — too little context for many incidents.
- **Why this wins:** Standardized signals and existing query APIs let the project focus on AI reasoning over incident evidence.
- **Costs / downsides:** Multiple infrastructure services consume memory, CPU, storage, and operational time.
- **Proof / verification:** Not implemented. Demonstrate an instrumented sample request across metrics, trace, and logs; record true correlation IDs and retention bounds.
- **Revisit when:** Resource usage or operational burden outweighs diagnostic benefit for a small deployment.
- **Interview answer:** “Instead of rebuilding an observability platform, I integrated established telemetry tools. AegisOps's differentiator is correlating the signals and producing auditable incident hypotheses.”

### ADR-007 — Deterministic incident detection before AI reasoning
- **Date:** 2026-10-10
- **Status:** ACCEPTED — DESIGN ONLY
- **Problem and constraints:** 24/7 LLM inference would be costly, slow, and less predictable than telemetry-based detection.
- **Decision:** Prometheus alert rules and Alertmanager trigger incidents. Only then do bounded ADK investigations run. Ingestion and alerting must continue when the model service fails.
- **Alternatives compared:** Constant AI inspection of every request/log — expensive and unnecessary; simple scheduled health URL polling — inexpensive but lacks internal diagnostic context.
- **Why this wins:** Clear operational separation, controlled token spend, and reliable handling when LLMs are unavailable.
- **Costs / downsides:** Alerts require threshold tuning; noisy rules cause unnecessary investigations and missed events are possible.
- **Proof / verification:** Not implemented. Test model outage with alert ingestion still functioning and duplicate alerts deduplicated.
- **Revisit when:** Specific incidents need safe anomaly detection beyond static alert thresholds, backed by measured results.
- **Interview answer:** “I separated detecting an incident from explaining it. Monitoring remains deterministic and always-on; the LLM activates only after a real alert, improving resilience and controlling cost.”

### ADR-008 — PostgreSQL + pgvector for incident state and RAG
- **Date:** 2026-10-10
- **Status:** ACCEPTED — DESIGN ONLY
- **Problem and constraints:** Store incident/run state, approvals, audit, document metadata, and embeddings with tenant-level authorization under a modest budget.
- **Decision:** Use PostgreSQL as source of truth, pgvector for embedding search, and metadata-filtered keyword retrieval as a fallback; evaluate hybrid retrieval.
- **Alternatives compared:** Pinecone/Qdrant — dedicated vector-search capabilities, but additional infrastructure/operations or service dependency; MongoDB — flexible documents but relational incident/approval invariants require care; embeddings-only search — can miss exact error codes and symbols.
- **Why this wins:** Fewer moving parts and strong transactional control for incident state; vector and relational queries can share tenant scoping.
- **Costs / downsides:** Large corpus/high-QPS vector workloads may require indexing, tuning, or a separate search service; pgvector doesn't make search relevance automatic.
- **Proof / verification:** Not implemented. Track recall@k, corpus size, p95 retrieval latency, and tenant isolation tests.
- **Revisit when:** Document scale or latency exceeds measured Postgres capacity, or a specialized engine materially improves relevance.
- **Interview answer:** “I picked pgvector because this project already needs Postgres for transactional state. It reduced infrastructure, enabled scoped retrieval, and let me add hybrid search; I'd move to a dedicated vector system if benchmarks justified it.”

### ADR-009 — Celery + Redis for bounded background work
- **Date:** 2026-10-10
- **Status:** ACCEPTED — DESIGN ONLY
- **Problem and constraints:** An investigation can require many model/tool calls and should not block HTTP requests; retries and failures must be visible.
- **Decision:** Use Celery workers and Redis as the broker with a durable application-level run ledger/outbox in PostgreSQL. Design tasks for **at-least-once delivery** and idempotent processing; don't assume exactly-once execution.
- **Alternatives compared:** FastAPI background tasks — simple but unsuitable as the sole durable queue; synchronous HTTP agent calls — risky timeouts; Kafka — extra platform overhead for v1.
- **Why this wins:** Common Python task ecosystem with explicit execution separation and practical retries.
- **Costs / downsides:** Redis+workers add moving parts; crashes, duplicate delivery, and poison jobs must be tested.
- **Proof / verification:** Not implemented. Kill worker mid-run; replay jobs; verify no duplicate incidents/actions.
- **Revisit when:** Durable orchestration needs exceed queue semantics or measured load justifies alternative systems.
- **Interview answer:** “I moved long-running investigations to Celery instead of keeping HTTP requests open. Because retries can duplicate deliveries, I made incident/run state and idempotency enforcement explicit in PostgreSQL.”

### ADR-010 — Use n8n for automation, not authoritative incident state
- **Date:** 2026-10-10
- **Status:** ACCEPTED — DESIGN ONLY
- **Problem and constraints:** Notifications, issue creation, and approval requests require integrations, but critical incident state must remain auditable and transactionally consistent.
- **Decision:** Self-host n8n for **operator-authored internal workflows**. Persist incidents/approvals in Postgres, emit events through an outbox, and use authenticated idempotent delivery to n8n.
- **Alternatives compared:** Implement every Slack/GitHub/email integration in Python — more maintenance; let n8n own all workflow and incident state — couples core product to external workflow engine; ADK as automation system — mixes LLM reasoning with deterministic operational actions.
- **Why this wins:** n8n accelerates integration work without making the workflow engine the authority on safety or incident truth.
- **Costs / downsides:** Another service with webhook security, retries, and potential licensing limitations. **Review current n8n license before allowing customers to configure or resell workflows.**
- **Proof / verification:** Not implemented. Test outbox delivery, event replay, n8n downtime, and duplicate webhook handling.
- **Revisit when:** Customer-facing workflow building becomes a requirement or license/ops trade-offs become unfavorable.
- **Interview answer:** “Google ADK handles AI investigations; n8n handles deterministic notifications and integrations. Postgres owns incident state, so workflow retries can't silently alter the authoritative incident record.”

### ADR-011 — Human-approved, allowlisted recovery only
- **Date:** 2026-10-10
- **Status:** ACCEPTED — DESIGN ONLY
- **Problem and constraints:** LLM output can be wrong or manipulated by malicious logs; granting direct shell/production access creates unacceptable risk.
- **Decision:** Agent creates recommendations and action proposals. Backend validates target, immutable parameters, permissions, expiry, environment, and approval. Demonstrate execution only on controlled staging/demo infrastructure; no autonomous production remediation in v1.
- **Alternatives compared:** Fully autonomous rollback — impressive demo but dangerous; entirely manual process — safest but demonstrates less orchestration; model-only confirmation — not an authorization boundary.
- **Why this wins:** Allows compelling end-to-end demo while placing authorization in deterministic code instead of the model.
- **Costs / downsides:** Additional UX friction and approval workflow complexity.
- **Proof / verification:** Not implemented. Test invalid/expired approval, target mismatch, prompt injection, replay, and concurrent approval races.
- **Revisit when:** Independently audited permissions, constrained action policy, and real operational evidence support expanding scope.
- **Interview answer:** “I treated model output as untrusted. The agent could propose a preapproved action, but only the backend could verify permission, exact parameters, and environment before a staging action ran.”

### ADR-012 — Evidence IDs and typed output over free-form answers
- **Date:** 2026-10-10
- **Status:** ACCEPTED — DESIGN ONLY
- **Problem and constraints:** LLMs can confidently invent plausible explanations or cite nonexistent logs.
- **Decision:** Force typed investigation results; store evidence with immutable IDs; independently verify that every cited ID exists and is authorized. Allow `inconclusive` as a legitimate outcome and list contradicting/missing evidence.
- **Alternatives compared:** Free-form chatbot response — easy to prototype, hard to audit; self-rated percentage confidence — sounds precise but is not calibrated; RAG-only answers — relevant runbooks are not proof of the current incident's root cause.
- **Why this wins:** Creates a checkable reasoning trail and makes false evidence claims detectable.
- **Costs / downsides:** Citation validity alone does not prove causal correctness; evaluations still needed.
- **Proof / verification:** Not implemented. Reject invented evidence ID in tests and compare diagnoses to ground truth cases.
- **Revisit when:** Richer causal verification is demonstrably possible; do not remove evidence validation.
- **Interview answer:** “I did not trust the model's explanation by itself. Each hypothesis references stored evidence IDs that the backend validates, and the system can report inconclusive results when telemetry is insufficient.”

### ADR-013 — Docker Compose first, Kubernetes later if justified
- **Date:** 2026-10-10
- **Status:** ACCEPTED — DESIGN ONLY
- **Problem and constraints:** Solo developer, constrained deployment budget, several observability services, need reproducible local development.
- **Decision:** Use pinned Docker Compose configurations for local and initial single-node deployment; treat redundancy, backups, TLS, and security separately.
- **Alternatives compared:** Kubernetes — orchestration/scaling capabilities but substantial setup and troubleshooting overhead; manually installed services — less reproducibility.
- **Why this wins:** Easier onboarding and repeatable fault-injection environment without premature operations complexity.
- **Costs / downsides:** A single VPS is a failure domain; Compose does not provide automatic cluster failover, multi-AZ resilience, or enterprise availability.
- **Proof / verification:** Not implemented. Run clean-machine installation, container restart, backup/restore, and upgrade rehearsal.
- **Revisit when:** Multi-node availability, high-traffic scaling, or operational constraints justify orchestration.
- **Interview answer:** “I used Compose deliberately because the first requirement was a repeatable observability and agent demo, not cluster management. I'd consider Kubernetes after the workload required multi-node orchestration.”

### ADR-014 — Controlled fault injection and unbiased evaluation
- **Date:** 2026-10-10
- **Status:** ACCEPTED — DESIGN ONLY
- **Problem and constraints:** AI diagnosis accuracy cannot be judged from a few cherry-picked successes or persuasive model output.
- **Decision:** Build a separate instrumented sample application and inject known failures; retain **held-out** scenarios, ambiguous cases, noisy telemetry, and a deterministic/rule baseline. Record precision of causal claims, accuracy, inconclusive detection, latency, cost, and sample sizes.
- **Alternatives compared:** Handpicked demos — compelling but not reliable evidence; only subjective LLM-as-judge scoring — vulnerable to bias; only public incident datasets — labels and access may not match our instrumentation.
- **Why this wins:** Ground truth gives reproducible tests and lets us quantify improvements from retrieval and agent tools.
- **Costs / downsides:** Synthetic incidents are not equivalent to diverse real production incidents; publishing limitations is essential.
- **Proof / verification:** Not implemented. Master plan target: at least 40 labeled scenarios, with held-out cases and documented scoring. Targets are not results.
- **Revisit when:** Real-world partner data with permissions becomes available; evaluate domain transfer carefully.
- **Interview answer:** “I didn't rely on a visually impressive demo as proof. I created repeatable failure scenarios and compared the agent against simpler baselines, including cases where the correct answer was ‘insufficient evidence.’”

### ADR-015 — Tenant-scoped, read-only integrations
- **Date:** 2026-10-10
- **Status:** ACCEPTED — DESIGN ONLY
- **Problem and constraints:** Agent tools touch potentially sensitive logs, credentials, telemetry, and deployment metadata; an LLM could attempt unsafe cross-project queries.
- **Decision:** Route tool calls through backend-managed authorization with fixed workspace/service/time bounds, redaction, size limits, and read-only GitHub tokens in v1. No arbitrary shell, URL fetch, PromQL/SQL, or privileged Docker access exposed to the model.
- **Alternatives compared:** Give LLM generic connector/SSH credentials — easier but unacceptable attack surface; duplicate access checks in every frontend button — bypassable; direct tool access from browser — leaks secrets.
- **Why this wins:** Security boundary is enforced in deterministic code regardless of model output or prompt wording.
- **Costs / downsides:** More adapter implementation and permission tests; some flexibility intentionally restricted.
- **Proof / verification:** Not implemented. Cross-tenant negative tests, log injection tests, secret redaction checks, and permission audit.
- **Revisit when:** Additional tool capabilities can be safely added under the same bounded gateway.
- **Interview answer:** “My agent never receives raw infrastructure credentials or permission to select arbitrary tenant data. Each tool request is scoped and validated by the backend, not by the prompt.”

### ADR-016 — Tenant-aware schema with restricted first release
- **Date:** 2026-10-10
- **Status:** ACCEPTED — DESIGN ONLY
- **Problem and constraints:** Need credible SaaS-style isolation, but unrestricted public multi-tenant telemetry ingestion expands risk, cost, and compliance complexity.
- **Decision:** Include organization/service ownership in schemas and authorization from the beginning; deploy a private or restricted demo first. Public unrestricted tenant onboarding is outside v1 unless isolation is verified.
- **Alternatives compared:** Purely single-user schema — faster, expensive retrofit for team permissions; immediately open SaaS for any customer logs — premature security/operations burden.
- **Why this wins:** Preserves future product boundaries without claiming unverified production-grade multi-tenancy.
- **Costs / downsides:** RBAC and ownership checks complicate API/data design even for a demo.
- **Proof / verification:** Not implemented. Run negative authorization, object-level access, and secret-scoping tests before opening access.
- **Revisit when:** Operational monitoring, tenancy testing, retention policy, and consent/privacy controls justify broader rollout.
- **Interview answer:** “I modeled tenants early because incidents contain sensitive operational data, but I restricted the initial release until cross-tenant isolation and telemetry retention were verified.”

---

## 3. Decision gates that require real evidence

| Question to resolve | Candidate comparison | Evidence required | Decision status |
|---|---|---|---|
| Which Gemini model should be default? | Available Flash-class models, other allowed models | Held-out tool-call success, accuracy, latency, cost | **OPEN** |
| How accurate is the AI? | No AI baseline vs logs-only LLM vs tool + RAG agent | Labeled scenario counts, confusion/error breakdown | **OPEN** |
| Is pgvector fast/relevant enough? | Lexical, vector, hybrid; later dedicated vector store | Recall@5, p95 latency, corpus size | **OPEN** |
| Does adding RAG help? | Same agent with RAG off/on | Paired held-out scenarios, citations, cost | **OPEN** |
| Would multiple agents improve results? | Single vs specialist agent(s) | Controlled accuracy/cost/latency comparison | **OPEN** |
| What is the actual system capacity? | Compose sizing and queue concurrency variants | Load test throughput, p95, memory, failure recovery | **OPEN** |
| How reliable is alert ingestion? | Nominal vs retries, duplicate delivery, outages | Idempotency and failure-injection tests | **OPEN** |
| When is a public SaaS safe? | Private demo vs self-serve onboarding | Authz, isolation, privacy, secrets, rate limits, retention | **OPEN** |

**Never turn a target into an achievement.** Example: `Target ≥70% top-1 accuracy` is not `Achieved 70% accuracy`.

---

## 4. Debugging and learning diary (update whenever something breaks)

### Entry template

```markdown
### BUG-YYYYMMDD-NNN — Short name
- **Symptom:** Exact expected vs actual result; log or trace ID.
- **User impact:** Which workflow and severity?
- **Hypotheses considered:** Potential causes and how each was tested.
- **Actual root cause:** Confirmed cause, or `Unconfirmed`.
- **Fix:** What changed, with code path / commit.
- **Why this fix:** Alternatives and regression/compatibility considerations.
- **Verification:** Reproduction before/after; tests, metrics, CI run URL.
- **Prevention:** New assertion, runbook, monitor, contract, or alert.
- **Interview story (STAR):** Situation / Task / Action / Result — no invented numbers.
```

**Starting state:** No implementation defects recorded yet. Add real entries during development.

---

## 5. Interview question bank (questions to rehearse, not fabricated achievements)

### System/product overview
1. Explain AegisOps in 60 seconds. Who is the user and what pain does it solve?
2. Walk through a real incident from telemetry source to evidence-backed report.
3. What is AegisOps's unique value versus Grafana/Datadog/PagerDuty?
4. Why use an AI model here at all? Which tasks stay deterministic?
5. What did **you** personally implement, and what was generated or assisted by coding tools?

### Agentic AI / ADK
6. Why ADK instead of LangGraph or OpenAI Agents SDK?
7. What is a tool call and how is it different from ordinary text generation?
8. How does the agent get scoped context and retain or resume state?
9. How do you prevent loops, runaway token costs, or tool-call storms?
10. Why one agent first? When would multiple agents help?
11. What happens if Gemini times out, returns invalid JSON, or exceeds its budget?
12. What evidence would convince you to change model or framework?

### RAG
13. Why RAG rather than fine-tuning or placing every runbook in the prompt?
14. How do chunking, metadata filters, lexical retrieval, and embeddings work?
15. Why pgvector rather than Pinecone/Qdrant?
16. Why is a cited runbook **not** proof of the active incident's root cause?
17. How did you measure retrieval usefulness and hallucination/unsupported-claim rate?
18. How do you keep tenant documents from leaking across requests?

### Backend / distributed systems
19. What is idempotency? Show how duplicate Alertmanager webhooks are handled.
20. Why Celery+Redis instead of an HTTP background task or Kafka?
21. What happens when the worker dies halfway through investigation?
22. Why is PostgreSQL the source of truth rather than n8n?
23. Describe a race condition in the approval workflow and your mitigation.
24. How would the design change at 10x/100x alerts or multiple regions?
25. What is your failure strategy if Redis, Postgres, Loki, or GitHub is unavailable?

### Security / reliability
26. How do you prevent prompt injection from logs and retrieved documents?
27. Why is prompt text alone insufficient for tool authorization?
28. Where are secrets stored, rotated, and redacted?
29. Why are read-only tools and approval-gated actions important?
30. How do tenant checks work at API, query, and tool levels?
31. What are your retention, backup, and disaster-recovery limitations?

### Frontend / FDE / operational decisions
32. Why Next.js instead of Vite + React?
33. How does the UI distinguish collecting, investigating, inconclusive, and complete states?
34. How do you avoid showing invented precision or false certainty?
35. How would you integrate AegisOps into a new customer's existing observability stack?
36. How do you handle uncertain requirements from an engineering customer?
37. What metrics demonstrate impact on the incident response process?
38. What trade-off would you reverse if you had two more weeks?
39. Which real failure taught you the most, and how did you debug it?
40. What limits would you clearly disclose before someone used AegisOps with a real production service?

**Answer standard:** Give a 30–60-second response anchored to an ADR, then be prepared to open relevant code and show evidence. If not yet implemented or measured, explicitly say that.

---

## 6. Proof ledger for defensible resume bullets

| Claim you might make | What proof is needed | Current state |
|---|---|---|
| “Built a functional incident investigation platform” | End-to-end demo, source code, screenshots/recording, working deployment | Not yet built |
| “Integrated metrics, logs, and traces” | Live telemetry requests and correlation IDs | Not yet built |
| “Implemented ADK tool-calling with RAG” | Traces, tool tests, retrieved citations and authorization checks | Not yet built |
| “Reduced time to diagnose incidents by X%” | Paired baseline and agent trials, N scenarios, measured elapsed time | **Do not claim until measured** |
| “Achieved X% RCA accuracy” | Labeled holdout, scorer rubric, repeated results, caveats | **Do not claim until measured** |
| “Designed safe automation” | Approved-action boundary and adversarial authorization tests | Not yet built |
| “Production-ready / scale-tested” | Load, failure, security, recovery and deployment evidence | **Do not claim without scope-qualified proof** |

---

## 7. Weekly interview checkpoint

Once per week, the coding agent should append a short update in the project's phase report and link it from here:

```markdown
### Week X — YYYY-MM-DD
- What feature really works end to end?
- What architectural decision changed, and why?
- Which two alternatives were considered seriously?
- What was the hardest bug or trade-off?
- Which tests and exact commands passed?
- What measurable improvement (if any) is supported by evidence?
- Two likely interviewer questions + my answers in plain language.
- What is still incomplete or unverified?
```

Do not write weekly summaries with fabricated project experiences.

---

## 8. Change history

| Date | Change | Link |
|---|---|---|
| 2026-10-10 | Created initial **design-only** ADRs from AegisOps Master Implementation Plan; no implementation or benchmarks asserted. | Master plan |
| 2026-10-10 | Expanded into 202 plan-derived granular decisions across 11 categories; created append-only micro-decision workflow and open-verification queue. | Master plan §0–§24 |

> **Final rule:** A clear, evidenced explanation of a trade-off is more valuable than a list of trendy technologies. Preserve historical reasoning. If a choice fails, document the failure and the new decision—that is excellent interview material.


## Phase 0 execution decisions — 2026-10-10

### DEC-203 — Phase boundary and audit interpretation
- Date/time (UTC): 2026-10-10T08:45:00Z
- Phase / work item: P0 foundation audit
- Scope: docs/PHASE_REPORTS/PHASE_00_AUDIT.md; all Phase 0 changes
- Status: ACCEPTED-DESIGN
- Trigger / problem: Master §18 Day 3 overlaps the separately gated Phase 1.
- Constraints: Explicit developer instruction prohibits starting Phase 1.
- Selected choice: Execute §17 P0 and the Phase 0 report; leave §18 Day 3 for Phase 1. Preserve baseline records.
- Alternatives: Executing all of §18 rejected because it violates the explicit scope.
- Why selected: The user's current instruction resolves the schedule ambiguity without changing architecture.
- Costs / failure modes: No genuine monitored incident is delivered in Phase 0.
- Evidence level: MASTER-PLAN
- Evidence: Master §§17/18/24; developer request; PHASE_00_AUDIT.md.
- When to revisit: Phase 0 exit gates pass and Phase 1 is authorized.
- Interview answer: Foundation tests de-risk the framework and contracts; they do not prove an incident pipeline. We separated the two claims.
- Related ADR/DEC: DEC-187–191, DEC-192

### DEC-204 — Isolated uv and npm toolchains
- Date/time (UTC): 2026-10-10T08:45:00Z
- Phase / work item: P0 reproducibility
- Scope: .gitignore, .tools, pyproject.toml, uv.lock, package-lock.json
- Status: ACCEPTED-DESIGN
- Trigger / problem: uv is absent; dependency installation must not modify host Python.
- Constraints: Workspace write access, 7.1 GiB RAM, installed npm.
- Selected choice: Bootstrap uv 0.13.0 in ignored .tools; use uv.lock and npm package-lock with exact direct pins; ignore credentials and generated artifacts.
- Alternatives: Poetry adds another absent tool; pnpm replaces working npm without a Phase 0 need; system pip risks host packages.
- Why selected: Reproducible dependency resolution with local isolation and existing Node tooling.
- Costs / failure modes: Initial downloads need network; lockfiles require deliberate maintenance.
- Evidence level: DOC-CONFIRMED
- Evidence: https://pypi.org/pypi/uv/json returned 0.13.0; local npm 10.9.8; no install tested yet.
- When to revisit: Resolver or workspace requirements cannot be met.
- Interview answer: Locks capture transitive versions and hashes; direct pins alone do not make a build reproducible. Isolated tools avoid changing the developer machine.
- Related ADR/DEC: DEC-185, DEC-186, DEC-167

### DEC-205 — Python 3.14.7 and Node 22.23.1
- Date/time (UTC): 2026-10-10T08:45:26.858156+00:00
- Phase / work item: P0 foundation
- Scope: toolchain files, Dockerfiles
- Status: ACCEPTED-DESIGN
- Trigger / problem: Phase 0 needs a reproducible, bounded implementation of python 3.14.7 and node 22.23.1.
- Constraints: Existing approved architecture; no Phase 1; local hardware and credential constraints.
- Selected choice: Use installed stable Python 3.14.7 and maintained Node 22.23.1 LTS for initial compatibility checks; do not upgrade host tools.
- Alternatives: Newer Python 3.14.8 / Node 24 LTS need downloads and a different local runtime.
- Why selected: Matches the developer machine and ADK Python >=3.10 / Next Node >=20.9.
- Costs / failure modes: Python patch is superseded; update isolated runtime if audits or compatibility demand it.
- Evidence level: DOC-CONFIRMED for package metadata; REASONED-HYPOTHESIS for untested behavior.
- Evidence: Official Python release page and Node release index; installed --version; runtime verification pending.
- When to revisit: Security advisory, unsupported runtime or failed resolution.
- Interview answer: Matches the developer machine and ADK Python >=3.10 / Next Node >=20.9. Python patch is superseded; update isolated runtime if audits or compatibility demand it. No runtime success is claimed yet.
- Related ADR/DEC: DEC-185

### DEC-206 — Python application pins
- Date/time (UTC): 2026-10-10T08:45:26.858156+00:00
- Phase / work item: P0 foundation
- Scope: pyproject.toml, uv.lock
- Status: ACCEPTED-DESIGN
- Trigger / problem: Phase 0 needs a reproducible, bounded implementation of python application pins.
- Constraints: Existing approved architecture; no Phase 1; local hardware and credential constraints.
- Selected choice: google-adk 2.11.0; google-genai 2.29.0; FastAPI 0.143.0; Pydantic 2.14.0; uvicorn 0.54.0; SQLAlchemy 2.1.4; Alembic 1.20.0; psycopg[binary] 3.3.6; redis client 8.1.0.
- Alternatives: Older releases not benchmarked; floating requirements rejected.
- Why selected: Current non-prerelease registry versions; resolve together before calling compatible.
- Costs / failure modes: Newest stable releases may have integration regressions; no compatibility claim yet.
- Evidence level: DOC-CONFIRMED for package metadata; REASONED-HYPOTHESIS for untested behavior.
- Evidence: Official PyPI JSON version / Requires-Python responses; runtime verification pending.
- When to revisit: Resolver conflict, security advisory or smoke-test failure.
- Interview answer: Current non-prerelease registry versions; resolve together before calling compatible. Newest stable releases may have integration regressions; no compatibility claim yet. No runtime success is claimed yet.
- Related ADR/DEC: ADR-001, ADR-004, ADR-008, DEC-185

### DEC-207 — Python verification pins
- Date/time (UTC): 2026-10-10T08:45:26.858156+00:00
- Phase / work item: P0 foundation
- Scope: pyproject.toml
- Status: ACCEPTED-DESIGN
- Trigger / problem: Phase 0 needs a reproducible, bounded implementation of python verification pins.
- Constraints: Existing approved architecture; no Phase 1; local hardware and credential constraints.
- Selected choice: pytest 9.1.1; pytest-asyncio 1.4.0; httpx 0.28.1; ruff 0.17.0; mypy 2.4.0; pip-audit 2.10.1.
- Alternatives: Not evaluated: no need for a testing framework comparison.
- Why selected: Use familiar Python tests and static checks; audit dependencies.
- Costs / failure modes: Tool upgrades can change diagnostics; CI must use same lock.
- Evidence level: DOC-CONFIRMED for package metadata; REASONED-HYPOTHESIS for untested behavior.
- Evidence: Official PyPI metadata; runtime verification pending.
- When to revisit: Incompatibility or materially useful stable update.
- Interview answer: Use familiar Python tests and static checks; audit dependencies. Tool upgrades can change diagnostics; CI must use same lock. No runtime success is claimed yet.
- Related ADR/DEC: DEC-155, DEC-173, DEC-188

### DEC-208 — Web runtime pins
- Date/time (UTC): 2026-10-10T08:45:26.858156+00:00
- Phase / work item: P0 foundation
- Scope: apps/web/package.json
- Status: ACCEPTED-DESIGN
- Trigger / problem: Phase 0 needs a reproducible, bounded implementation of web runtime pins.
- Constraints: Existing approved architecture; no Phase 1; local hardware and credential constraints.
- Selected choice: Next 16.4.0 with React/react-dom 19.3.0; TypeScript 7.0.2.
- Alternatives: Vite rejected by ADR-005; prereleases excluded.
- Why selected: Registry peer constraints permit this React major and existing Node.
- Costs / failure modes: Actual compile and browser checks pending.
- Evidence level: DOC-CONFIRMED for package metadata; REASONED-HYPOTHESIS for untested behavior.
- Evidence: Official npm latest metadata and Next installation docs; runtime verification pending.
- When to revisit: Peer conflict, build failure or advisory.
- Interview answer: Registry peer constraints permit this React major and existing Node. Actual compile and browser checks pending. No runtime success is claimed yet.
- Related ADR/DEC: ADR-005, DEC-185

### DEC-209 — Web test and styling pins
- Date/time (UTC): 2026-10-10T08:45:26.858156+00:00
- Phase / work item: P0 foundation
- Scope: apps/web/package.json
- Status: ACCEPTED-DESIGN
- Trigger / problem: Phase 0 needs a reproducible, bounded implementation of web test and styling pins.
- Constraints: Existing approved architecture; no Phase 1; local hardware and credential constraints.
- Selected choice: ESLint 10.12.0; eslint-config-next 16.4.0; Prettier 3.9.10; Playwright 1.64.0; Tailwind/@tailwindcss/postcss 4.3.3; React types 19.3.0.
- Alternatives: Handmade interactive widgets and shadcn install deferred: static shell has no widget need.
- Why selected: Respect DEC-137 while keeping the shell semantic and small.
- Costs / failure modes: Browser binaries consume disk; no full dashboard interactions yet.
- Evidence level: DOC-CONFIRMED for package metadata; REASONED-HYPOTHESIS for untested behavior.
- Evidence: Official npm metadata; runtime verification pending.
- When to revisit: Interactive widget introduced or tool compatibility failure.
- Interview answer: Respect DEC-137 while keeping the shell semantic and small. Browser binaries consume disk; no full dashboard interactions yet. No runtime success is claimed yet.
- Related ADR/DEC: DEC-137, DEC-138, DEC-141

### DEC-210 — Minimal Express foundation
- Date/time (UTC): 2026-10-10T08:45:26.858156+00:00
- Phase / work item: P0 foundation
- Scope: examples/shop-api
- Status: ACCEPTED-DESIGN
- Trigger / problem: Phase 0 needs a reproducible, bounded implementation of minimal express foundation.
- Constraints: Existing approved architecture; no Phase 1; local hardware and credential constraints.
- Selected choice: Express 5.3.0 and @types/express 5.0.6; health endpoint only, TypeScript build.
- Alternatives: Business routes and instrumentation deferred by explicit Phase 0 scope.
- Why selected: Verifies demo service runtime without beginning telemetry work.
- Costs / failure modes: Cannot demonstrate any real incident.
- Evidence level: DOC-CONFIRMED for package metadata; REASONED-HYPOTHESIS for untested behavior.
- Evidence: Official npm engines Node >=18; master §17 P0; runtime verification pending.
- When to revisit: Phase 1 unlocked.
- Interview answer: Verifies demo service runtime without beginning telemetry work. Cannot demonstrate any real incident. No runtime success is claimed yet.
- Related ADR/DEC: DEC-057, DEC-203

### DEC-211 — Core infrastructure images
- Date/time (UTC): 2026-10-10T08:45:26.858156+00:00
- Phase / work item: P0 foundation
- Scope: docker-compose.yml
- Status: ACCEPTED-DESIGN
- Trigger / problem: Phase 0 needs a reproducible, bounded implementation of core infrastructure images.
- Constraints: Existing approved architecture; no Phase 1; local hardware and credential constraints.
- Selected choice: pgvector 0.8.7-pg18-bookworm and Redis 8.10.2-alpine; record pulled digest and observed PostgreSQL patch before finalizing.
- Alternatives: Separate vector store rejected by ADR-008; floating tags rejected.
- Why selected: Upstream pgvector supplies a PostgreSQL image; no RAG application work.
- Costs / failure modes: Tag alone does not lock underlying OS/Postgres patch; digest required.
- Evidence level: DOC-CONFIRMED for package metadata; REASONED-HYPOTHESIS for untested behavior.
- Evidence: Official pgvector Docker tags and Redis GitHub latest release; runtime verification pending.
- When to revisit: Advisory, supported patch release or failed container smoke.
- Interview answer: Upstream pgvector supplies a PostgreSQL image; no RAG application work. Tag alone does not lock underlying OS/Postgres patch; digest required. No runtime success is claimed yet.
- Related ADR/DEC: ADR-008, ADR-009, ADR-013

### DEC-212 — Local networking and resources
- Date/time (UTC): 2026-10-10T08:45:26.858156+00:00
- Phase / work item: P0 foundation
- Scope: docker-compose.yml
- Status: ACCEPTED-DESIGN
- Trigger / problem: Phase 0 needs a reproducible, bounded implementation of local networking and resources.
- Constraints: Existing approved architecture; no Phase 1; local hardware and credential constraints.
- Selected choice: Bind web/API/shop ports only to 127.0.0.1; DB/Redis internal only; core/lab profiles; API/web 512 MiB each, DB 256 MiB, Redis/shop 128 MiB; serial builds.
- Alternatives: Public bindings or all future services rejected.
- Why selected: Unauthenticated foundation must remain local; measured RAM availability is small.
- Costs / failure modes: Limits are starting constraints, not demonstrated capacity; web build needs separate memory.
- Evidence level: DOC-CONFIRMED for package metadata; REASONED-HYPOTHESIS for untested behavior.
- Evidence: Local free -h, master §19.2 and §14; runtime verification pending.
- When to revisit: OOM or measured footprint requires tuning.
- Interview answer: Unauthenticated foundation must remain local; measured RAM availability is small. Limits are starting constraints, not demonstrated capacity; web build needs separate memory. No runtime success is claimed yet.
- Related ADR/DEC: DEC-171, DEC-196

### DEC-213 — Health and readiness contract
- Date/time (UTC): 2026-10-10T08:45:26.858156+00:00
- Phase / work item: P0 foundation
- Scope: apps/api
- Status: ACCEPTED-DESIGN
- Trigger / problem: Phase 0 needs a reproducible, bounded implementation of health and readiness contract.
- Constraints: Existing approved architecture; no Phase 1; local hardware and credential constraints.
- Selected choice: GET /healthz returns status ok and service api; /readyz probes SELECT 1 and Redis PING and returns 503 without connection details on failure; three-second dependency deadlines.
- Alternatives: Health that always claims dependency readiness rejected; exposing exceptions rejected.
- Why selected: Separate process liveness from usable infrastructure with bounded waits.
- Costs / failure modes: Readiness uses live probes, adds small DB load.
- Evidence level: DOC-CONFIRMED for package metadata; REASONED-HYPOTHESIS for untested behavior.
- Evidence: Master §17 P0; tests pending; runtime verification pending.
- When to revisit: Readiness load becomes measurable or more required services arrive.
- Interview answer: Separate process liveness from usable infrastructure with bounded waits. Readiness uses live probes, adds small DB load. No runtime success is claimed yet.
- Related ADR/DEC: ADR-004, DEC-132, DEC-178

### DEC-214 — Minimal database migration
- Date/time (UTC): 2026-10-10T08:45:26.858156+00:00
- Phase / work item: P0 foundation
- Scope: apps/api/alembic
- Status: ACCEPTED-DESIGN
- Trigger / problem: Phase 0 needs a reproducible, bounded implementation of minimal database migration.
- Constraints: Existing approved architecture; no Phase 1; local hardware and credential constraints.
- Selected choice: Alembic creates organizations and services with mandatory organization foreign key, UUIDs and timestamptz; application has no CRUD endpoints; tests exercise insert/rollback and downgrade/upgrade on disposable DB.
- Alternatives: Full incident schema now rejected as Phase 1+ scope; SELECT 1 alone insufficient migration proof.
- Why selected: Proves real database integration while establishing ownership.
- Costs / failure modes: No RLS/auth claim; application role strategy still needs Phase 3 work.
- Evidence level: DOC-CONFIRMED for package metadata; REASONED-HYPOTHESIS for untested behavior.
- Evidence: Master §9 and §17 P0; runtime verification pending.
- When to revisit: New domain migration or auth implementation.
- Interview answer: Proves real database integration while establishing ownership. No RLS/auth claim; application role strategy still needs Phase 3 work. No runtime success is claimed yet.
- Related ADR/DEC: DEC-121, DEC-126, DEC-127, DEC-129

### DEC-215 — Phase 0 contract boundary
- Date/time (UTC): 2026-10-10T08:45:26.858156+00:00
- Phase / work item: P0 foundation
- Scope: apps/api/app/schemas
- Status: ACCEPTED-DESIGN
- Trigger / problem: Phase 0 needs a reproducible, bounded implementation of phase 0 contract boundary.
- Constraints: Existing approved architecture; no Phase 1; local hardware and credential constraints.
- Selected choice: Strict extra-forbid typed alert, incident, evidence, result and approval envelopes; aware UTC timestamps; bounded strings/lists; no execution endpoints.
- Alternatives: Untyped dicts rejected; full lifecycle behavior deferred.
- Why selected: Makes the specified interfaces reviewable without implementing later phases.
- Costs / failure modes: Contracts will evolve before public APIs; field limits need production tuning.
- Evidence level: DOC-CONFIRMED for package metadata; REASONED-HYPOTHESIS for untested behavior.
- Evidence: Master §4.5, §5.4, §8.2, §9; runtime verification pending.
- When to revisit: First real adapter or lifecycle implementation.
- Interview answer: Makes the specified interfaces reviewable without implementing later phases. Contracts will evolve before public APIs; field limits need production tuning. No runtime success is claimed yet.
- Related ADR/DEC: ADR-012, ADR-016, DEC-040, DEC-132

### DEC-216 — Evidence validator scope
- Date/time (UTC): 2026-10-10T08:45:26.858156+00:00
- Phase / work item: P0 foundation
- Scope: apps/api/app/schemas
- Status: ACCEPTED-DESIGN
- Trigger / problem: Phase 0 needs a reproducible, bounded implementation of evidence validator scope.
- Constraints: Existing approved architecture; no Phase 1; local hardware and credential constraints.
- Selected choice: Validate supporting and contradicting IDs against backend-owned returned ledger and exact organization/service/run scope; complete results require cited hypothesis; action IDs must belong to passed allowlist (empty in spike).
- Alternatives: Global known-ID set and prompt-only verification rejected.
- Why selected: A real ID from another run or tenant is still unauthorized.
- Costs / failure modes: Valid references do not prove the text or cause is correct.
- Evidence level: DOC-CONFIRMED for package metadata; REASONED-HYPOTHESIS for untested behavior.
- Evidence: Master §4.3/§14.1; negative tests planned; runtime verification pending.
- When to revisit: Persisted evidence or new claim-bearing fields introduced.
- Interview answer: A real ID from another run or tenant is still unauthorized. Valid references do not prove the text or cause is correct. No runtime success is claimed yet.
- Related ADR/DEC: ADR-012, ADR-015, DEC-043, DEC-164

### DEC-217 — Gemini spike candidate
- Date/time (UTC): 2026-10-10T08:45:26.858156+00:00
- Phase / work item: P0 foundation
- Scope: agents/incident_investigator
- Status: ACCEPTED-DESIGN
- Trigger / problem: Phase 0 needs a reproducible, bounded implementation of gemini spike candidate.
- Constraints: Existing approved architecture; no Phase 1; local hardware and credential constraints.
- Selected choice: Candidate gemini-3.8-flash configurable through AEGISOPS_AGENT_MODEL; no permanent/default production selection without live evidence.
- Alternatives: Gemini 2.5 restricted for new projects; preview models excluded; 3.5 Flash-Lite not evaluated.
- Why selected: Official current model docs recommend 3.8 Flash for new projects and tool workloads.
- Costs / failure modes: No key/budget currently available; live gate remains blocked.
- Evidence level: DOC-CONFIRMED for package metadata; REASONED-HYPOTHESIS for untested behavior.
- Evidence: https://ai.google.dev/gemini-api/docs/models; runtime verification pending.
- When to revisit: Live rejection, unacceptable tool behavior or model retirement.
- Interview answer: Official current model docs recommend 3.8 Flash for new projects and tool workloads. No key/budget currently available; live gate remains blocked. No runtime success is claimed yet.
- Related ADR/DEC: ADR-003, DEC-052, DEC-198

### DEC-218 — Offline and live spike separation
- Date/time (UTC): 2026-10-10T08:45:26.858156+00:00
- Phase / work item: P0 foundation
- Scope: agents/incident_investigator, tests
- Status: ACCEPTED-DESIGN
- Trigger / problem: Phase 0 needs a reproducible, bounded implementation of offline and live spike separation.
- Constraints: Existing approved architecture; no Phase 1; local hardware and credential constraints.
- Selected choice: Run real ADK runner with deterministic fake model offline and two-record read-only synthetic tool; live mode uses same tool/schema and a real configured Gemini model.
- Alternatives: Handwritten synthetic output presented as live rejected; real telemetry deferred.
- Why selected: Tests actual framework dispatch independently of API availability.
- Costs / failure modes: Offline success proves wiring only, not Gemini behavior or accuracy.
- Evidence level: DOC-CONFIRMED for package metadata; REASONED-HYPOTHESIS for untested behavior.
- Evidence: Master §18 Day 2 and Phase 0 report; runtime verification pending.
- When to revisit: Credentials/budget available; actual telemetry in Phase 2.
- Interview answer: Tests actual framework dispatch independently of API availability. Offline success proves wiring only, not Gemini behavior or accuracy. No runtime success is claimed yet.
- Related ADR/DEC: ADR-001, ADR-002, ADR-012

### DEC-219 — Spike budgets and artifacts
- Date/time (UTC): 2026-10-10T08:45:26.858156+00:00
- Phase / work item: P0 foundation
- Scope: agents/incident_investigator
- Status: ACCEPTED-DESIGN
- Trigger / problem: Phase 0 needs a reproducible, bounded implementation of spike budgets and artifacts.
- Constraints: Existing approved architecture; no Phase 1; local hardware and credential constraints.
- Selected choice: One synthetic scenario per CLI run; hard 180s timeout, <=12 tools, <=4 model requests, <=2048 output tokens/request; no retry; reject invalid result; record events, usage and config without credentials or model thoughts.
- Alternatives: Automatic retries and printing raw provider errors rejected.
- Why selected: Keeps a framework experiment bounded and evidence inspectable.
- Costs / failure modes: Token reservations and pricing must be checked before live requests; no actual billed-cost claim.
- Evidence level: DOC-CONFIRMED for package metadata; REASONED-HYPOTHESIS for untested behavior.
- Evidence: DEC-046/047; live key missing; runtime verification pending.
- When to revisit: Live smoke evidence, pricing change or later durable runs.
- Interview answer: Keeps a framework experiment bounded and evidence inspectable. Token reservations and pricing must be checked before live requests; no actual billed-cost claim. No runtime success is claimed yet.
- Related ADR/DEC: DEC-046, DEC-047, DEC-053, DEC-198

### DEC-220 — Honest static dashboard shell
- Date/time (UTC): 2026-10-10T08:45:26.858156+00:00
- Phase / work item: P0 foundation
- Scope: apps/web/app
- Status: ACCEPTED-DESIGN
- Trigger / problem: Phase 0 needs a reproducible, bounded implementation of honest static dashboard shell.
- Constraints: Existing approved architecture; no Phase 1; local hardware and credential constraints.
- Selected choice: Dark responsive semantic dashboard at /app; root links to it; clear Phase 0/synthetic-only/no connected services copy; no fabricated metrics or working incident controls.
- Alternatives: Mock incident feed rejected because it suggests implemented investigation behavior.
- Why selected: Meets shell gate with accessible truthful empty states.
- Costs / failure modes: No auth, streaming or product workflows yet.
- Evidence level: DOC-CONFIRMED for package metadata; REASONED-HYPOTHESIS for untested behavior.
- Evidence: Master §11, Phase 0 gate; runtime verification pending.
- When to revisit: Phase 1 services/incident API available.
- Interview answer: Meets shell gate with accessible truthful empty states. No auth, streaming or product workflows yet. No runtime success is claimed yet.
- Related ADR/DEC: DEC-138, DEC-140, DEC-141

### DEC-221 — CI proof boundary
- Date/time (UTC): 2026-10-10T08:45:26.858156+00:00
- Phase / work item: P0 foundation
- Scope:  .github/workflows, tests
- Status: ACCEPTED-DESIGN
- Trigger / problem: Phase 0 needs a reproducible, bounded implementation of ci proof boundary.
- Constraints: Existing approved architecture; no Phase 1; local hardware and credential constraints.
- Selected choice: Read-only workflow permissions; pinned tools, frozen installs, lint/format/type/unit, browser shell and Docker integration checks; live API test opt-in locally, never on untrusted PR secrets.
- Alternatives: Claiming hosted green from local run rejected; paid model calls per PR rejected.
- Why selected: Reproducible local baseline without leaking API credentials.
- Costs / failure modes: Hosted run and branch protection need GitHub access/push; remain blockers until inspected.
- Evidence level: DOC-CONFIRMED for package metadata; REASONED-HYPOTHESIS for untested behavior.
- Evidence: DEC-189; no commits at audit; runtime verification pending.
- When to revisit: Verified hosted run or release evaluation scheduling.
- Interview answer: Reproducible local baseline without leaking API credentials. Hosted run and branch protection need GitHub access/push; remain blockers until inspected. No runtime success is claimed yet.
- Related ADR/DEC: DEC-155, DEC-173, DEC-188, DEC-189

### DEC-222 — Resolve FastAPI / ADK OpenTelemetry conflict
- Date/time (UTC): 2026-10-10T08:47:20.397039+00:00
- Phase / work item: P0 dependency lock
- Scope: pyproject.toml, uv.lock; supersedes FastAPI portion of DEC-206
- Status: ACCEPTED-DESIGN
- Trigger / problem: uv found ADK <=1.42.1 and FastAPI >=1.44.0 OpenTelemetry constraints incompatible.
- Constraints: Keep the approved single Python ecosystem and stable ADK release.
- Selected choice: FastAPI 0.141.0, whose official metadata has no incompatible OTel lower bound. Node types 22.20.5 match the installed major.
- Alternatives: FastAPI 0.142.0 has the same conflict; splitting environments adds avoidable overhead; bypassing resolution is unsafe.
- Why selected: Smallest verified dependency-level repair while retaining the approved architecture.
- Costs / failure modes: Not newest FastAPI; security audit and runtime tests remain required.
- Evidence level: TESTED resolver failure / DOC-CONFIRMED metadata
- Evidence: uv sync --all-groups exited 1; https://pypi.org/pypi/fastapi/0.141.0/json; npm view @types/node@22 version.
- When to revisit: ADK supports newer OTel or FastAPI security patch requires upgrade.
- Interview answer: Stable packages are not necessarily compatible together. We used actual resolver evidence and selected the preceding compatible API release rather than forcing installation.
- Related ADR/DEC: DEC-206, DEC-208, DEC-185

### BUG-20261010-001 — Stable release dependency conflict
- Symptom / reproduction: UV_CACHE_DIR=.cache/uv .tools/bin/uv sync --all-groups exited 1 for ADK 2.11.0 + FastAPI 0.143.0.
- User impact: No reproducible Python environment.
- Hypotheses: Network failure ruled out by successful metadata fetch; transitive version conflict reported directly by resolver.
- Root cause: Incompatible opentelemetry-api upper/lower bounds.
- Fix: Pin FastAPI 0.141.0 (DEC-222).
- Why: 0.142.0 metadata has same incompatibility; no constraint overrides.
- Verification: Rerun pending.
- Prevention / lesson: Resolve the whole lock before declaring versions compatible; audit and tests still required.
- Interview story: A dependency lock exposed a release mismatch before application code was written; outcome pending verification.

### DEC-223 — Compatible frontend tooling, unresolved audit finding
- Date/time (UTC): 2026-10-10T08:55:42.213351+00:00
- Phase / work item: P0 frontend checks
- Scope: package.json, apps/web/package.json, package-lock.json
- Status: ACCEPTED-DESIGN
- Trigger / problem: npm installed invalid TypeScript 7 peers and duplicate ESLint versions.
- Constraints: Next config currently depends on TypeScript-ESLint supporting <6.1 and plugins supporting ESLint 9.
- Selected choice: TypeScript 6.0.3 and ESLint 9.39.5; supersedes corresponding pins in DEC-208/209. Keep npm audit failure as a gate blocker.
- Alternatives: Forcing incompatible peers rejected; npm audit fix --force would downgrade Next config to 14.2.35 and is rejected. Latest braces is still 3.0.3, so no patched override exists in the registry.
- Why selected: Align actual supported peer ranges rather than merely the latest versions.
- Costs / failure modes: ESLint 9 is deprecated upstream. Five high audit entries share one braces advisory in development tooling; not waived.
- Evidence level: TESTED
- Evidence: npm ls typescript eslint exit 1; npm audit exit 1; GHSA-vfj7-8cjw-p6xm; npm view typescript@6 and braces version.
- When to revisit: Next tooling supports ESLint 10/TypeScript 7 or a patched braces chain ships.
- Interview answer: Package installation can succeed despite invalid peers. We inspect the dependency tree and distinguish development advisories from clean runtime dependencies, without calling the overall audit green.
- Related ADR/DEC: DEC-208, DEC-209, DEC-173

### BUG-20261010-002 — Frontend peer incompatibility and unpatched glob parser
- Symptom: npm install warned about peers; npm ls found TypeScript 7 outside <6.1. npm audit reported 5 high entries rooted in braces <=3.0.3.
- Reproduction: npm ls typescript eslint --depth=2; npm audit --json.
- Hypotheses/root cause: Published tooling peers lag latest compiler/linter; latest braces has no patched release (registry query returned 3.0.3).
- Fix: DEC-223 aligns peers; no vulnerability fix claimed.
- Verification: Reinstall/static checks pending; security gate remains open.
- Prevention/lesson: Inspect peers and audit transitive packages. Never run destructive major-version audit fixes blindly.
- Interview story: Stable-version verification exposed compatibility and supply-chain limits; runtime testing and security evidence must remain separate.

### DEC-224 — Concrete foundation limits and spike API boundary
- Date/time (UTC): 2026-10-10T08:55:42.213370+00:00
- Phase / work item: P0 implementation details
- Scope: Compose, migrations, ADK spike, Next config
- Status: ACCEPTED-DESIGN
- Trigger / problem: Exact operating defaults are required to make the foundation executable.
- Constraints: Low available RAM; no authenticated product APIs; Gemini Developer API only.
- Selected choice: Redis 64 MiB/noeviction with persistence off for P0 probes only; Next build one CPU with webpack; health probes 5–10s, 3–5s timeouts, 6–12 retries. Tables use UUID IDs, 120-character names, org/name uniqueness and no cascading delete. Contract text 4000 chars, IDs 128 safe chars, snippets 32000 chars, 10 hypotheses, 50 refs, 20 missing/limitation entries, 10 catalog suggestions. Live spike uses <=16000 counted input tokens/request, 2048 output tokens, temperature 0, minimal thinking, 30s HTTP timeout, no retries, <=USD 0.10 ceiling. Pricing expires after 2026-12-31; current standard text rates 0.75/3.75 USD per million input/output tokens. Output allowance is fully reserved before generation. In-memory sessions and local JSON artifacts only.
- Alternatives: Unbounded defaults, persistence without a queue workload and full incident/auth tables rejected; no other threshold values benchmarked.
- Why selected: Conservative bounded synthetic experiment and small reproducible scaffold. These values are initial engineering constraints, not measured optimal settings.
- Costs / failure modes: Redis data is transient; JSON artifacts are not a durable run ledger. Count-token/config support and actual provider billing remain live-unverified. ADK Developer API currently falls back to set_model_response with an experimental JSON schema feature; do not override capability detection or claim native structured-output compatibility.
- Evidence level: DOC-CONFIRMED and REASONED-HYPOTHESIS
- Evidence: Installed ADK 2.11.0 _capabilities.py restricts combined native schema/tools to Vertex; google-genai 2.29.0 CountTokensConfig; official Gemini pricing accessed 2026-10-10. Offline tool smoke passed; live missing credentials.
- When to revisit: Real queue/telemetry, larger schemas, provider changes, resource failures, pricing expiry.
- Interview answer: A framework signature alone is not API compatibility. The local spike validates dispatch; a live run must validate the provider path and budget counting.
- Related ADR/DEC: DEC-212–219; ADR-001, ADR-012

### DEC-225 — Remove the unused vulnerable Next lint bundle
- Date/time (UTC): 2026-10-10T08:59:00.842040+00:00
- Phase / work item: P0 dependency security repair
- Scope: apps/web/eslint.config.mjs, package manifests/lock
- Status: ACCEPTED-DESIGN
- Trigger / problem: Next lint plugin pulls unpatched braces through fast-glob.
- Constraints: Preserve linting, TypeScript checks and accessibility checks; no suppression of audit findings.
- Selected choice: Remove eslint-config-next, directly use already resolved typescript-eslint 8.71.1, @eslint/js 9.39.5 and eslint-plugin-jsx-a11y 6.10.2 flat recommended configurations. Keep compatible ESLint 9/TypeScript 6 pins.
- Alternatives: Keep vulnerable unused glob path rejected; downgrade Next itself rejected; custom patched dependency rejected as maintenance burden.
- Why selected: The static Phase 0 shell needs TypeScript and accessibility linting, not the Next-specific glob scanner. Removes the affected dependency instead of waiving it.
- Costs / failure modes: Next-specific lint rules absent; revisit when advanced Next/client features are added. ESLint 9 remains deprecated while JSX accessibility plugin peers exclude 10.
- Evidence level: DOC-CONFIRMED
- Evidence: https://typescript-eslint.io/getting-started/; installed dependency tree; GHSA-vfj7-8cjw-p6xm lists no patched release. Re-audit pending.
- When to revisit: Patched Next lint chain or interactive React functionality.
- Interview answer: We kept the required checks but removed a convenience bundle carrying an unpatched dependency. This is a narrower change than downgrading the application framework or suppressing the advisory.
- Related ADR/DEC: DEC-209, DEC-223, DEC-173

### BUG-20261010-003 — Local verification environment and compiler details
- Reproductions: Sandboxed pytest stalled before first result; the same 34 tests passed outside sandbox in 4.25s. Exact low-level sandbox cause unconfirmed. Docker Python image pull timed out at registry CDN; explicit retry succeeded with verified digest. TypeScript 6 build required rootDir src (TS5011).
- Hypotheses: Distinguish sandbox event-loop restriction from application failure using identical escalated test; image timeout was network transport; TS error directly named required config.
- Repairs: Run socket/browser checks with permitted host access; retry image pull; set rootDir src without changing output import paths.
- Verification: 34 Python tests passed, image pulled; shop build rerun pending.
- Prevention/lesson: A failed environment check is not evidence of an application bug; preserve exact failed commands and test the specific repair.
- Interview story: Verified test-environment constraints separately from code defects. No production outcome claimed.

### DEC-226 — Destructive migration checks are isolated
- Date/time (UTC): 2026-10-10T08:59:00.842069+00:00
- Phase / work item: P0 DB verification
- Scope: docker-compose.verify.yml, integration tests, Makefile
- Status: ACCEPTED-DESIGN
- Trigger / problem: Downgrade testing can destroy an operator database if aimed at the wrong connection.
- Constraints: Preserve local development data.
- Selected choice: Separate aegisops-verify Compose project/volume and aegisops_phase0_verify database, with an explicit current_database assertion before migrations. Transactional fixture rollback.
- Alternatives: Downgrade the core database rejected; skip downgrade proof rejected.
- Why selected: A reproducible migration gate without touching core data.
- Costs / failure modes: Extra temporary DB container; name guard is not a general production permission system.
- Evidence level: REASONED-HYPOTHESIS
- Evidence: tests/test_integration.py; run pending.
- When to revisit: Migration test fixtures need existing data or production restore proof.
- Interview answer: Migration verification must be safe to repeat; we isolate test state and guard the target.
- Related ADR/DEC: DEC-129, DEC-214

### DEC-227 — Offline auth-library spike only
- Date/time (UTC): 2026-10-10T09:01:32.644760+00:00
- Phase / work item: P0 auth spike
- Scope: test_auth_spike.py; ADR-019
- Status: VERIFIED
- Trigger / problem: Master P0 requests an auth spike but no issuer/account exists.
- Constraints: Do not implement Phase 3 auth/RBAC or invent an authenticated identity.
- Selected choice: Test installed Authlib 1.8.0 authorization URL state/PKCE S256 with reserved example.invalid endpoints; no network calls or product login.
- Alternatives: Managed or self-hosted provider integrations require owner decisions; custom JWT/password implementation rejected by DEC-133.
- Why selected: Exercises library compatibility while preserving unimplemented security gates explicitly.
- Costs / failure modes: Does not verify callbacks, ID tokens or session storage.
- Evidence level: TESTED-LOCAL
- Evidence: `apps/api/tests/test_auth_spike.py` passed (Authlib 1.8.0 installed source `oauth2/client.py`); ADR-019.
- When to revisit: Before user-specific endpoints/deployment.
- Interview answer: PKCE/state primitives are testable offline, but they are not a completed authentication system.
- Related ADR/DEC: ADR-019, DEC-133/134

### DEC-228 — Sequential local verification under workstation RAM limits
- Date/time (UTC): 2026-10-10T09:44:00.000000+00:00
- Phase / work item: Phase 0 full verification
- Scope: Makefile, package scripts, Playwright config, Docker Compose profiles
- Status: VERIFIED
- Trigger / problem: Local developer workstation has 7.1 GiB RAM with ~1 GiB available. GNU `make` is absent in host PATH, and Playwright browser caches live in `.cache/ms-playwright` requiring explicit `PLAYWRIGHT_BROWSERS_PATH`.
- Constraints: Avoid OOM kills, avoid modifying host package managers without passwordless sudo, ensure all verification steps run cleanly and reproducibly.
- Selected choice: Execute verification steps sequentially: static Python checks (`ruff`, `mypy`), Python unit tests (`pytest`), dependency audits (`pip-audit`, `npm audit`), web linters/formatters (`eslint`, `prettier`, `tsc`), Playwright browser smoke test with explicit `PLAYWRIGHT_BROWSERS_PATH`, web production build, sequential Docker image builds (`--parallel 1`), isolated Compose migration round-trip in `aegisops-verify`, and live container health checks against core services before stopping them.
- Alternatives: Running all services and test suites concurrently rejected due to high risk of Linux OOM killer; installing host `make` via sudo rejected because root password was unavailable.
- Why selected: Guarantees deterministic, resource-safe execution that honors host constraints without sacrificing test coverage or integrity.
- Costs / failure modes: Takes slightly more wall-clock time than parallel execution (~3 minutes total); requires explicit environment variables when invoking tools directly outside Make.
- Evidence level: TESTED-LOCAL
- Evidence: All 36 unit tests pass; 2 Playwright browser tests pass; 2 integration tests pass; Docker images build and containers report healthy; 0 audit vulnerabilities.
- When to revisit: When developer workstation is upgraded or hosted CI runners (with ample memory and preinstalled `make`) run the suite.
- Interview answer: Production-grade testing respects target host resource bounds. We sequenced test execution to ensure reliability on an 8 GB workstation rather than letting parallel builds trigger OOM kills.
- Related ADR/DEC: ADR-017, DEC-218, DEC-224

### DEC-229 — Honest live model gate: offline ADK verification vs credential absence
- Date/time (UTC): 2026-10-10T09:45:00.000000+00:00
- Phase / work item: Phase 0 ADK exit gate
- Scope: `agents/incident_investigator/spike.py`, `.env.example`, `docs/PROJECT_STATE.md`
- Status: VERIFIED
- Trigger / problem: Master plan allows optional live Gemini tool-call test, but developer has not configured `GOOGLE_API_KEY` and authorized paid spend is $0.
- Constraints: LLM output is untrusted; never ask for credentials in chat; never simulate fake live API passes; never bill unauthorized API calls.
- Selected choice: Real Google ADK 2.11.0 framework dispatch, runner, and session service verified offline using deterministic test double `OfflineModel` across both supported (`complete`) and conflicting (`inconclusive`) scenarios. Mark live Gemini gate truthfully as `NOT RUN / BLOCKED BY CREDENTIALS`. Provide deterministic, bounded command for future authorized run (`python -m agents.incident_investigator.spike --live --output ...`).
- Alternatives: Replacing Google ADK with a generic mock loop rejected (violates framework lock); fabricating live model pass rejected (violates honesty invariants); executing unauthorized billable API calls rejected (violates zero-spend default).
- Why selected: Strictly preserves agent truthfulness, exercises real ADK SDK contracts and validation code, and protects user from unexpected billing.
- Costs / failure modes: Live function-calling latency, live model thinking behavior, and quota dynamics remain to be observed when credentials are provided.
- Evidence level: TESTED-LOCAL (offline ADK framework) and DOC-CONFIRMED (Gemini API pricing / limits)
- Evidence: `agents/incident_investigator/tests/test_spike.py` passes; `artifacts/spike-supported.json` and `artifacts/spike-conflicting.json` generated; `test_missing_key_fails_before_network` passes.
- When to revisit: When developer explicitly configures `GOOGLE_API_KEY` in `.env` and specifies an approved non-zero spend limit (`AEGISOPS_SPIKE_MAX_USD`).
- Interview answer: We distinguished framework integration from model API connectivity. We proved the Google ADK runner and tool boundaries offline, while truthfully documenting live model access as blocked by credentials to prevent unauthorized billing.
- Related ADR/DEC: ADR-018, DEC-224

### Phase 0 ADR index additions
- [ADR-017](ADR/ADR-017-foundation-lock.md): reproducible compatible locks and resource boundaries.
- [ADR-018](ADR/ADR-018-adk-spike-boundary.md): independent framework/live-model evidence.
- [ADR-019](ADR/ADR-019-auth-spike.md): auth exploration without a fake login; provider choice open.

### DEC-230 — Free-only comparison preflight and evidence boundaries
- Date (UTC): 2026-10-10
- Phase / work item: Phase 0 live Gemini/Groq comparison requested by developer
- Scope: `docs/PHASE_REPORTS/PHASE_00_MODEL_COMPARISON.md`; preflight only, no runtime changes
- Status: VERIFIED for credential presence and pushed/hosted-CI observations; BLOCKED for account eligibility and live comparison
- Trigger / problem: Both local keys are now configured, but the user authorizes no paid requests; previous credential-absence descriptions are historical. Phase 0 gate documents also disagree.
- Constraints: Never print key values; no billing changes, paid inference, Phase 1 work, automatic fallback, or multi-agent orchestration. Follow AGENTS.md conflict reporting.
- Selected choice: Check key presence without values, verify remote SHA and hosted run via read-only GitHub operations, and request account-tier evidence before inference. Pause implementation pending reconciliation of ADR-018 versus project/phase status. Preserve all historical decision entries. Report the two models as NOT RUN with no observed winner.
- Alternatives: Assuming a configured key is free-tier eligible rejected because paid projects can also have keys; setting positive spend merely to satisfy the old guard rejected because it contradicts the user's $0 constraint; claiming local CI proves hosted success rejected. Provider integration alternatives are researched but not selected.
- Why selected: Separates credential presence, project billing eligibility, model behavior, and CI evidence. Prevents an unverified free-tier assumption from authorizing spend.
- Costs / failure modes: Blocks the requested live comparison until account evidence and the document conflict are resolved. No model latency, tokens, quality, or security-verified Groq integration can yet be claimed.
- Evidence level: TESTED-LOCAL, DOC-CONFIRMED, and observed GitHub API/remote refs; account eligibility UNVERIFIED
- Evidence: Both `.env` keys nonempty and file ignored; `git ls-remote origin HEAD refs/heads/main` matches `b0014ab9ad39e4657f20c4f771d71c259067653e`; GitHub Actions API returned completed/success for [run 38043157853](https://github.com/Tarun-sde/AegisOps/actions/runs/38043157853). Sources and per-provider NOT RUN ledger in the comparison report.
- When to revisit: Developer confirms exact account tiers and gate interpretation; then choose/pin/audit the smallest supported adapter and run both fixtures under bounded free-only authorization.
- Interview answer: We verified that credentials existed without exposing them, and verified hosted CI against the exact pushed commit. We did not confuse public free-tier pricing with the actual account's billing state, or offline ADK dispatch with a live model pass. The model comparison remains open.
- Related ADR/DEC: ADR-001/002/003/012/015/018; DEC-217–219/221/224/229

### BUG-20261010-004 — Preflight network and Phase 0 gate discrepancies
- Symptom / reproduction: Sandboxed `git ls-remote origin HEAD refs/heads/main` failed with `Could not resolve host: github.com`; ADR-018 requires live-model evidence to unlock Phase 1 while the project state and Phase 0 report already mark it unlocked.
- Hypotheses: Restricted network versus missing remote; stale ADR follow-up versus incorrect phase completion. No runtime model failure observed.
- Cause / uncertainty: Authorized network escalation made the same Git command succeed, confirming access restrictions affected the initial check. The intended gate interpretation is pending developer clarification.
- Repair: Read-only remote/API checks verified push and hosted CI. Record the document conflict and pause implementation; do not silently rewrite history or billing guards.
- Verification / prevention: Exact SHA and run URL in DEC-230 and the comparison report. No code regression test required for these read-only observations. Local unit-test results will be recorded separately.
- Lesson: Network failures are not CI failures; a documented complete foundation is not evidence of live model compatibility. No live-model or production claim follows from this preflight.

### DEC-230 verification addendum
- Existing offline suite: sandbox invocation stalled after one test and was interrupted (exit 130). Same suite outside sandbox with `timeout 60s .venv/bin/python -m pytest -q -m 'not integration'`: **36 passed, 2 deselected, 4 warnings in 1.33s**, exit 0. Reuses BUG-20261010-003's environment diagnostic; exact sandbox cause remains unconfirmed. `git diff --check` passed.
- No new ADR or runtime change. Governing architecture/security decisions remain ADR-001/002/003/012/015/018; spike behavior remains DEC-217–219/224/229; hosted-CI evidence follows DEC-221. No measured model preference is supported.

### DEC-231 — Developer clarification of the Phase 0 gate
- Date: 2026-10-10
- Scope: PROJECT_STATE, ADR-018, Phase 0 reports, master-plan clarification
- Status: ACCEPTED — developer explicitly authorized
- Context / constraints: Foundation/local verification and hosted CI are complete; live verification is still mandatory before formally unlocking Phase 1.
- Choice / reason: Separate foundation completion from the outstanding live-model gate; mark Phase 1 LOCKED. Preserve previous statements as dated history and append this clarification.
- Alternatives: Leaving “unlocked” active contradicts the developer; restarting foundation wastes verified work.
- Downside / revisit: Phase 1 remains blocked until live evidence and explicit authorization exist; revisit when both occur.
- Evidence: Developer Decision 2 in this task; existing hosted run 38043157853.
- Related: ADR-018, DEC-203/221/229/230. No architecture change.

### DEC-232 — Pin the supported ADK LiteLLM bridge for Groq
- Date: 2026-10-10
- Scope: pyproject.toml, uv.lock, groq_adapter.py, TECH_STACK_LOCK; ADR-020
- Status: ACCEPTED — DESIGN ONLY pending audit and tests
- Context / constraints: A second provider needs protocol conversion without another agent runtime; ADK remains 2.11.0.
- Choice / reason: Pin LiteLLM 1.104.2 (official PyPI metadata, Python >=3.10,<3.15, satisfies ADK >=1.84). Use ADK's existing LiteLlm; no proxy/extras/router. Review wheel hash/contents and audit the resolved set before use. Pin existing dotenv 1.2.4 in the agent group for explicit CLI env loading.
- Alternatives: Custom HTTP/BaseLlm conversion creates protocol code to own; direct Groq SDK still needs ADK conversion; compromised LiteLLM 1.82.7/1.82.8 are excluded.
- Downside / revisit: Additional transitive dependencies and ongoing supply-chain exposure; a clean audit is not proof of absence of vulnerabilities. Revisit if audit or compatibility fails.
- Evidence: https://adk.dev/agents/models/litellm/ ; https://docs.litellm.ai/docs/providers/groq ; PyPI 1.104.2 metadata checked 2026-10-10. Installation/test evidence pending.
- Related: ADR-001/003/017/020, DEC-054/173/217/230.

### DEC-233 — Free-tier evidence is an operator boundary, not a pricing guess
- Date: 2026-10-10
- Scope: spike.py live preflight and tests; comparison report
- Status: ACCEPTED — DESIGN ONLY pending tests
- Context / constraints: No authenticated account console or cloud credentials are available; only free-only inference is authorized.
- Choice / reason: Keep each provider blocked until a local, operator-reviewed tier evidence record identifies the provider, Free tier, exact key SHA-256, account/project reference, console source and verification timestamp. Require <=1 hour freshness and reject future timestamps, paid/unknown tiers, key/provider mismatch and nonzero spend. This records manual account verification; it does not query or prove billing automatically. Never manufacture a record from key presence or model-list responses.
- Alternatives: A bare environment Boolean or public pricing cannot establish account eligibility; attempting inference to discover billing violates the prerequisite; building a cloud billing/OAuth service is out of scope.
- Downside / revisit: Trusts truthful local operator review and no billing changes during a run; the hour window is a conservative unbenchmarked default. Reverify immediately after key/account/billing changes; use a provider-enforced billing control if one becomes available.
- Evidence: Official Google billing and Groq billing/rate-limit documentation; current browser inventory empty, gcloud/ADC absent. Tests pending.
- Related: DEC-198/219/224/229/230. Supersedes the old positive-spend requirement for this spike; paid mode is disabled.

### DEC-234 — Reuse the spike and retain failure measurements
- Date: 2026-10-10
- Scope: spike.py, Groq adapter, offline tests, Makefile
- Status: ACCEPTED — DESIGN ONLY pending tests
- Context / constraints: Compare identical synthetic scenarios without switching providers automatically, extra orchestration or paid retries.
- Choice / reason: Explicit provider selection (Gemini default) and allowlisted configurable model IDs; reuse ADK Runner, prompt, tools, schema and ledger. Retain 4 calls/run, 2048 output tokens/call, 180s run and 30s HTTP limits, no retries. Gemini retains counted input <=16000; Groq caps serialized ADK request bytes at 16000 to avoid an additional tokenizer download (not represented as an exact token count). Record per-response timing/usage, partial events on failure, sanitized exception class/HTTP status, and null for unknown usage/cost. Require supported=complete and conflicting=inconclusive with both support and contradiction citations.
- Alternatives: Separate agent loops would bias the comparison; silently retrying/falling back obscures errors; zero-filled unknown usage fabricates measurement.
- Downside / revisit: Small samples cannot establish production quality/latency distributions. Bytes are conservative context control, not a provider token counter. Revisit for live incompatibility or larger evaluation scope.
- Evidence: Existing DEC-218/219/224 and pinned ADK source; regression and bridge tests pending.
- Related: ADR-012/018/020; DEC-217/221/233.

### DEC-235 — Restrict the Groq bridge to the documented surface
- Date: 2026-10-10
- Scope: groq_adapter.py and boundary tests
- Status: ACCEPTED — DESIGN ONLY pending tests
- Context / constraints: Groq documents that structured-output mode cannot be combined with tool use; generic LiteLlm capability detection can advertise that combination.
- Choice / reason: Declare combined native schema/tools unsupported so ADK uses its existing set_model_response tool. Fixed HTTPS Groq endpoint, explicit key, no provider built-ins, low reasoning effort, no retries/fallback, bundled cost map, telemetry/debug output disabled. Keep Gemini minimal thinking separately; these are provider-specific settings, not equivalent reasoning budgets.
- Alternatives: Forcing native schema+tools contradicts vendor docs; adding a second formatting agent changes topology; remote cost-map downloads introduce unrelated network activity.
- Downside / revisit: Small subclass depends on pinned ADK capability API; tool-produced JSON still needs validation. Revisit when Groq documents and tests combined support.
- Evidence: https://console.groq.com/docs/structured-outputs (tool-use limitation); installed ADK BaseLlm.capabilities and LiteLlm._resolve_capabilities; tests pending.
- Related: ADR-018/020; DEC-224/232/234.

### DEC-236 — Resolved dependency and verification scope
- Date: 2026-10-10
- Scope: uv.lock, Makefile, comparison tests/report
- Status: IMPLEMENTED — verification in progress
- Context / constraints: LiteLLM requires filelock <4; the existing environment had 4.1.0. The connector adds 31 packages and replaces filelock with 3.32.7.
- Choice / reason: Accept the resolver's required filelock downgrade and exact transitive pins, preserving all other existing versions. Audit the entire exported lock before installation, install wheels only, and extend existing mypy/pytest checks to the new modules. Verify HTTP payload conversion, fixed endpoint, output cap, schema-tool fallback, rejected tier proofs, no retries, evidence failures and sanitized errors with synthetic HTTP doubles.
- Alternatives: Silently changing filelock rejected; waiving dependency constraints rejected; live tests without account evidence rejected. Other filelock versions were not benchmarked.
- Downside / revisit: Larger dependency graph; audits and mocks do not certify supply-chain security or live API correctness. Revisit when bridge constraints change or any security/compatibility finding appears.
- Evidence: PyPI wheel SHA-256 416c3538ea78b08d637ec45564a919232aa2093e73adb9dd7752f7cff2ec585e matched downloaded Linux wheel; no .pth/sitecustomize/usercustomize files. Exported resolved set pip-audit: no known vulnerabilities. First full bridge run: 52 passed, 2 failed; fixture correction: 54 passed, 2 deselected in 4.63s. Final expanded checks pending.
- Related: ADR-017/020, DEC-232–235.

### BUG-20261010-005 — Groq mock response omitted documented service tier
- Symptom / reproduction: First ADK→LiteLLM→mock-HTTP run returned APIConnectionError: ModelResponse lacked service_tier; 2 scenario tests failed while 52 passed.
- Hypotheses: Adapter conversion defect versus incomplete mock. Installed LiteLLM Groq transformation reads the response field; official Groq API reference documents service_tier in the response.
- Cause / repair: The synthetic response omitted service_tier; add documented on_demand to the fixture. No vendor code monkeypatch or live request was used. If a real response omits the field, current bridge fails safely; live compatibility remains unverified.
- Verification: Both full ADK/HTTP scenario tests then passed, 54 tests total. HTTP 401/429/500 tests confirm one request and sanitized failure artifacts. Mypy also required a typed subclass constructor and direct pinned capability import; those fixes alter no wire behavior.
- Lesson: A plausible OpenAI-shaped mock is not automatically a faithful Groq fixture; compare vendor fields and test conversion at the HTTP boundary.

### DEC-231–236 verification and recommendation addendum
- Status: DEC-231 documentation reconciled under explicit developer authority. ADR-020 / DEC-232–236 IMPLEMENTED and VERIFIED OFFLINE; live provider compatibility remains BLOCKED, not VERIFIED.
- Evidence: Final suite **59 passed, 2 deselected, 132 warnings in 5.65s**; Ruff clean/19 formatted files; mypy clean/7 source files; installed and pre-install dependency audits report no known vulnerabilities. Both original deterministic CLI scenarios pass. All four real-key CLI preflights without evidence exit 1 with zero inference/tool calls. `git diff --check` passed after whitespace correction. Details and exact commands: PHASE_00_MODEL_COMPARISON.md.
- Actual account verification: no connected browser, gcloud or Google ADC; both exact key-owning tiers remain UNVERIFIED. No real tier record was manufactured. Paid requests, billing activation and Phase 1 work did not occur.
- Recommendation: Gemini remains provisional primary and Groq secondary by developer instruction. There is no observed live model winner. The bridge passes two HTTP-mocked ADK tool trajectories with structured output/citations; those are not real model successes. Native Gemini integration has fewer translation dependencies; Groq's supported bridge adds dependency/security maintenance and a documented schema/tools capability correction. No measured speed/cost/quality advantage is claimed.
- Decisions reused: ADR-001/002/003/012/015/017/018; DEC-217–219/221/224/229/230. Paid-mode requirement of DEC-224/229 is superseded for this spike by DEC-233; historical entries retained. No automatic provider switching or architecture change.
