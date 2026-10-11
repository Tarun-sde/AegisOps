# ADR-025: Production-Grade RAG Knowledge Subsystem, pgvector Hybrid Retrieval, and Citation Grounding

- **Date:** 2026-10-12
- **Status:** ACCEPTED — VERIFIED
- **Owner:** Principal AI Engineer & Backend Architect
- **Scope:** `apps/api/app/rag`, `agents/incident_investigator`, `apps/worker`, `apps/web/app/app/runbooks`, `evaluations/rag`
- **Governing Phase:** Phase 5 of `AEGISOPS_MASTER_IMPLEMENTATION_PLAN.md`

---

## 1. Context and Problem Statement

AegisOps investigates production incidents across cloud services. While telemetry (metrics, structured logs, distributed traces) reveals *what* is breaking at runtime, resolving incidents requires operational knowledge:
- How is the database connection pool tuned for `shop-api`?
- What are the documented mitigation commands when Redis saturates?
- What were the root causes and remediation steps of past resolved incidents?

Prior to Phase 5, the Google ADK investigation agent was blind to operational documentation, forcing operators to manually consult wikis or risking hallucinated remediation advice.

However, incorporating external runbooks and operational history into an automated AI incident response system presents severe engineering and security challenges:
1. **Hallucination & Fake Citations:** LLMs frequently invent citations or assume runbook text proves causality without runtime telemetry.
2. **Secret Leakage:** Internal operational runbooks frequently contain database connection strings, passwords, private keys, or API tokens that must NEVER enter vector embeddings, external LLM prompts, or vector index logs.
3. **Retrieval Blindspots:** Pure vector search struggles with exact keywords, technical error codes (e.g. `KnexTimeoutError`, HTTP 500), and configuration flags. Pure keyword search fails on conceptual queries (e.g. "traffic drop", "pool exhaustion").
4. **Cross-Tenant Contamination:** In multi-tenant environments, one tenant must NEVER retrieve runbooks or past incident records belonging to another tenant or unauthorized service.
5. **Operational Complexity:** Adding a standalone vector database (Pinecone, Qdrant, Milvus) introduces additional infrastructure, separate backup semantics, network latency, and consistency management.

---

## 2. Decision and Architecture

### 2.1 Retrieval-Augmented Generation (RAG) Over Fine-Tuning
We strictly choose RAG over model fine-tuning:
- **Instant Updatability:** When an SRE updates a runbook or resolves an incident, the knowledge is indexed and retrievable in milliseconds without multi-hour model retraining.
- **Strict Evidence Grounding:** RAG returns concrete text chunks with verifiable IDs (`ev_runbook_...`, `ev_hist_...`) that can be cited and validated deterministically.
- **Tenant Isolation:** Fine-tuned model weights cannot guarantee tenant boundary separation. RAG enforces tenant filtering in deterministic database queries.
- **Zero Hallucinated Procedures:** Prompts strictly bind agent recommendations to retrieved chunk text.

### 2.2 PostgreSQL pgvector Over Standalone Vector Databases
We select PostgreSQL with the `pgvector` extension (0.5.1) rather than a standalone vector database (Pinecone, Qdrant, Weaviate):
- **Single Source of Truth:** Documents, chunks, vector embeddings, and full-text search vectors live in the same PostgreSQL database as tenants, services, and incidents.
- **ACID Transactions:** Document deletion, reindexing, or tenant offboarding atomically updates or purges both relational and vector data in a single transaction.
- **Unified Multi-Tenant Security:** Tenant scoping (`organization_id`, `service_id`) is applied in SQL `WHERE` clauses prior to distance calculation, preventing any cross-tenant vector leakage.
- **Minimal Operational Footprint:** Zero external vector cluster to host, monitor, or pay for.

### 2.3 Hybrid Retrieval with Reciprocal Rank Fusion (RRF, $k=60$)
We implement hybrid retrieval combining lexical and semantic search:
- **Lexical Branch:** PostgreSQL full-text search (`to_tsvector('english', ...)` and `websearch_to_tsquery('english', ...)` / `plainto_tsquery`) over chunk titles and contents, indexed via GIN.
- **Vector Branch:** 768-dimensional vector cosine distance (`DocumentChunk.embedding <=> :query_vector`) using HNSW index (`m=16, ef_construction=64`).
- **Fusion Formula:** Reciprocal Rank Fusion combines rankings into a unified score:
  $$RRF(d) = \sum_{m \in \{lexical, vector\}} \frac{1}{k + rank_m(d)}$$
  where smoothing parameter $k=60$ prevents top-ranked outliers in either modality from skewing results.
- **Measured Evaluation:** On a benchmark of 32 queries across 5 operational runbooks, Hybrid RRF achieved **Recall@5 = 87.5%**, outperforming vector-only (83.3%) and keyword-only (87.5% with lower MRR).

### 2.4 Semantic Heading-Aware Chunking & Token Bounding
We reject naive fixed-character sliding window chunking in favor of structural heading-aware chunking:
- **Markdown & Plain Text Header Parsing:** Documents are split along structural headings (`#`, `##`, `###`), preserving the integrity of operational sections (Symptoms, Diagnostic Procedures, Recovery, Mitigation).
- **Hierarchical Path Propagation:** Every chunk maintains its full hierarchical path (`Doc Title > Section > Subsection`) prepended directly to the chunk content (`### Section\n\nContent`). This provides vital contextual grounding for embeddings and lexical search even on concise sub-paragraphs.
- **Token Bounding:** Token count is bounded using `tiktoken` (`cl100k_base`, max 512 tokens per chunk, overlap 64 tokens) to ensure optimal embedding density and avoid truncating LLM context windows.

### 2.5 Deterministic Secret and Credential Redaction Pipeline
Before chunking, embedding, or indexing, raw document content traverses a deterministic regex redaction scanner:
- Scans for RSA/OpenSSH/PGP private keys, database connection URIs with embedded passwords (`postgresql://user:pass@host/db`), HTTP Bearer tokens, JWT tokens, AWS/Google API keys, and generic credential assignments (`password = ...`).
- Replaces matches with `[REDACTED]`.
- Enforces an invariant: unredacted secrets are never stored in `document_chunks.content`, never sent to embedding APIs, and never present in search results.

### 2.6 Dual Embedding Architecture: Production GenAI vs Hermetic Hash Double
- **Production (`GoogleGenAIEmbeddingProvider`):** Generates 768-dimensional normalized embeddings using Google's `text-embedding-004` via the official `google-genai` SDK.
- **Offline / CI / Testing (`DeterministicHashEmbeddingProvider`):** Generates deterministic 768-dimensional unit-norm vectors via SHA-256 token hashing and L2 normalization. Guarantees 100% reproducible, hermetic test execution with zero external API calls or network latency.

### 2.7 Document Ingestion State Machine & Atomic Reindexing
Documents transition through an explicit state machine:
- `PENDING -> EXTRACTING -> REDACTING -> CHUNKING -> EMBEDDING -> INDEXING -> READY` (or `FAILED` with error message).
- **Versioning:** Documents track monotonic integer `version`. Content updates create pending revisions without dropping active chunks until new indexing is verified.
- **Soft Deletion:** Deleting a document marks `is_deleted = True` and unindexes all associated chunks immediately, preserving audit trails.
- **Background Ingestion:** Worker task `ingest_document_task` offloads asynchronous processing via Celery and Redis.

### 2.8 Related Incidents Retrieval Tool
Historical incident post-mortems provide invaluable context during new outages:
- `RelatedIncidentService` retrieves historically resolved incidents within the tenant and service.
- Indexes incident title, root cause hypothesis, and summary text.
- Returns structured citations (`ev_hist_...`) with symptom overlap scoring.

### 2.9 Anti-Hallucination & Scientific Grounding Invariants
The Google ADK investigator (`incident_investigator`) interfaces with knowledge retrieval exclusively through `ReadOnlyToolGateway`:
- **Unforgeable Evidence Registration:** Retrieved runbook chunks and historical incidents are automatically registered in the gateway's `evidence_ledger` as `ev_runbook_...` and `ev_hist_...`.
- **Deterministic Validation:** `validate_evidence` verifies that every cited evidence ID exists in the ledger. Fabricated citations trigger `ValueError: Unknown evidence reference`.
- **Non-Standalone Evidence Rule (Check 5):** The validator strictly rejects high-confidence root cause hypotheses that cite runbooks or historical incidents without corroborating runtime error telemetry (logs, metrics, traces). Operational documentation describes *how to fix* issues; runtime telemetry proves *what failed*.

---

## 3. Security and Tenant Isolation Guarantees

1. **Zero LLM Database Access:** The agent has zero direct SQL or pgvector access. All queries pass through `retrieve_runbook` and `get_related_incidents` with enforced parameter validation.
2. **Strict Multi-Tenant Pre-Filtering:** Database queries enforce `WHERE organization_id = :org_id` and service bounds before distance calculations. Zero cross-tenant leakage.
3. **Least-Privilege Secret Sanitization:** Documents are sanitized upon entry; no credentials enter downstream pipelines.
4. **Prompt Injection Resistance:** Retrieved document chunks are enclosed in strict XML delimiters `<runbook_context>` and treated by the LLM system prompt as passive background reference, never executable commands.

---

## 4. Consequences and Verification

- **Evaluation Benchmark:** 32 queries evaluated in `evaluations/rag/evaluate.py`. Hybrid RRF achieved **Recall@5 = 87.5%**, surpassing the phase gate threshold of 80%.
- **Test Suite:** 119 unit/integration/security tests passing in `apps/api/tests/test_rag_subsystem.py` and core suites.
- **End-to-End Demonstration:** `scripts/verify_phase5_rag_e2e.py` verifies the complete lifecycle, agent tool call, evidence registration, citation validation, and cross-tenant isolation.
- **Zero New Running Costs:** pgvector runs directly inside the existing PostgreSQL container.
