# Interview Preparation — Built from Real Engineering Decisions

**This is a rehearsal guide, not a list of completed accomplishments.** The detailed question bank and initial answer frameworks already live in `ENGINEERING_DECISIONS.md` §§2, 5–7.

## Weekly review habit

1. Pick three decisions recorded this week, including at least one small `DEC-XXX`.
2. Explain: problem → alternatives → why selected → downside → test evidence → what you would change at scale.
3. Reproduce one failure or benchmark from the actual project when available.
4. If there is no reliable evidence yet, say exactly what remains unverified.
5. Capture one debugging story using situation, hypothesis, experiments, change, result and lesson.

## Core FDE/SDE/AI topics

- Why Google ADK instead of direct tool calling or LangGraph?
- Why does a deterministic monitoring system trigger AI, rather than AI polling continuously?
- How are tenant-safe read-only tools enforced outside the prompt?
- How does evidence citation validation differ from root-cause correctness?
- Why not let n8n or Google ADK own approval state?
- How do idempotency, retries and the outbox prevent duplicate work?
- What does RAG add over logs and traces? Where can it mislead?
- What happens during an upstream Gemini quota or telemetry-store outage?
- What are actual p50/p95 latency, token costs, and known errors, once measured?

## Evidence rule

Every interview claim must point to a real implementation, test, evaluated scenario, or measured result. Never memorize a template as if it were something you already achieved.
