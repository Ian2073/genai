# ADR-0001: Retire Dedicated Coref Container

- Status: Accepted
- Date: 2026-04-04
- Owners: Evaluation System Maintainers

## Context

The evaluation system currently uses a dedicated `coref-service` container based on `fastcoref`.
This provides good quality for pronoun chains, but it also adds:

- A second runtime environment with strict dependency pins
- Extra startup and health-check complexity
- Additional failure modes in deployment

At the same time, the evaluator now has a backend adapter seam in `shared/coref_backends.py`,
so backend changes can be made without rewriting scoring logic.

## Decision

Keep `remote_fastcoref` as the quality baseline for now, but move to a staged retirement model:

1. Keep the adapter contract stable:
- Input: `resolve_story_coreferences(text, entities)`
- Output must include:
  - `coreference_chains`
  - `coreference_relations`
  - `total_relations`
  - `average_confidence`
  - `method`
  - `backend_name`
  - `backend_mode`
  - `fallback_mode`
  - `degradation_reason`

2. Treat `fallback_rules` as mandatory safe fallback.
3. Evaluate `llm_coref` behind the same contract.
4. Retire `coref-service` only after exit criteria are met.

## Exit Criteria For Retirement

All criteria below must hold on a representative validation set:

1. Quality parity:
- New default backend keeps coref-sensitive score deltas within +/- 2.0 points (p95)
  versus current `remote_fastcoref` baseline.

2. Explainability parity:
- 100% of runs still emit all required coref explainability fields.

3. Reliability:
- End-to-end evaluation completion rate is >= 99.5% without manual restart.

4. Latency:
- p95 total evaluation latency does not regress by more than 15%.

5. Rollback safety:
- One env switch can restore previous behavior (`COREF_BACKEND_MODE`) in production.

## Consequences

Positive:

- Cleaner deployment topology
- Lower dependency pressure and maintenance overhead
- Easier backend experimentation

Negative:

- Requires explicit benchmark and regression workflow
- Temporary dual-path maintenance during migration period

## Implementation Notes

- Current active adapter path: `shared/coref_backends.py` + `consistency.py`
- Current operation modes: `auto`, `remote`, `rules`
- Reserved future mode: `llm`
