# Agent & Incident Evaluation Plan — Proposed

**Status:** Design targets, no measured model results. Source: master plan §§2, 12–13.

## Evaluated task

Given one time-bounded incident with authorized telemetry, identify supported causal hypotheses or explicitly abstain when evidence is insufficient. The agent may never execute unauthorized actions.

## Comparison baselines

| Label | System |
|---|---|
| B0 | Deterministic alert summary, no LLM |
| B1 | One LLM prompt with truncated logs only |
| B2 | Google ADK plus metrics/logs/traces read tools, no RAG |
| B3 | ADK plus telemetry, deployment history and runbook RAG |

## Proposed dataset and metrics

- Aim for **40–60 labeled scenarios** including ≥25 held-out known-cause cases, 10 ambiguous/insufficient-evidence cases, 5 prompt-injection cases and 5 noise/no-incident cases. Categories may overlap; publish exact counts when dataset exists.
- Root-cause top-1 and top-3, unsupported causal claims, honest inconclusive outcomes.
- Citation ID validity, evidence precision, RAG recall@5, test data isolation.
- Latency p50/p95, tool calls, token usage, USD per incident, timeouts and unsafe attempts.
- Publish failed examples and run-specific identifiers; no invented percentages.

## Reproducibility contract

Record: scenario manifest hash, selected model ID, ADK version, prompt revision, sampling settings, tool registry version, retrieval corpus version, code commit and data provenance. Avoid evaluating on cases used for prompt iteration when reporting held-out accuracy.

## Release gate

No invalid citations or unauthorized actions in the defined security suite. More stringent targets appear in master plan §2; these are **goals, not current performance**.
