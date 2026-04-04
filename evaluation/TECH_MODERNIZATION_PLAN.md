# Evaluation System Technology Modernization Plan

## Goal
Prepare the evaluation system with clean dual-environment workflows and a realistic replacement roadmap for fragile modules, without integrating into the generation pipeline yet.

## Current Pain Points
1. Coreference module requires a separate environment and version-locked stack.
- Service uses fastcoref with pinned transformers 4.39.x and pydantic 1.x in a dedicated container.
- Main evaluator stack uses newer libraries, so dependency convergence is difficult.
- This split increases startup complexity and maintenance cost.

2. Coreference service had legacy packaging drift.
- Dockerfile referenced a non-existent module name for service entry.
- This has now been corrected in cleanup.

3. Heavy optional acceleration stack causes portability risks.
- bitsandbytes and flash-attn improve speed but can fail by GPU/driver/toolchain profile.
- Local setup and Docker setup both need clear fallback expectations.

4. Optional calibration stack introduces extra dependency burden.
- XGBoost is optional and already degradable, but still adds wheel compatibility pressure for local setup.

## Strict Module Replacement Candidates

### A. Coreference (highest priority)
Current: fastcoref remote service in separate container.

Candidate 1: Keep service, improve isolation and interface (short term)
- Pros: Lowest migration risk, no scoring logic rewrite.
- Cons: Still two runtime environments.
- Use as transition stage only.

Candidate 2: Rule-plus-entity linker only (no extra service)
- Pros: No separate container, simplest deployment.
- Cons: Lower recall on long narrative pronoun chains.
- Good fallback backend, not final premium backend.

Candidate 3: LLM structured coreference extraction (Qwen)
- Pros: Reuses main LLM runtime, no extra coref environment.
- Cons: Token/latency cost, prompt stability needs tuning.
- Strong medium-term target if quality is acceptable.

Candidate 4: spaCy experimental coref ecosystem
- Pros: Python-native integration.
- Cons: Limited language coverage and maturity for this workload.
- Not preferred as primary path.

Recommendation:
- Short term: stabilize current service through clear interface contracts and scripts.
- Medium term: add pluggable coref backend contract and ship rules + remote options.
- Long term: evaluate LLM coref backend to retire dedicated fastcoref container if quality passes thresholds.

### B. Calibration (xgboost)
Current: optional and already degradable.
Plan:
- Keep optional mode.
- Add clear profile split in docs: default path runs without calibration model.
- Defer replacement unless business calibration requirements return.

### C. NER stack (GLiNER + spaCy fallback)
Current: practical but model-heavy.
Plan:
- Keep dual strategy (GLiNER primary, spaCy fallback).
- Add version pin hygiene and explicit local setup guidance.
- Consider migration only after coreference path is stabilized.

## Architecture Preparation (No Pipeline Integration Yet)
1. Define backend seam for coreference in evaluator side only.
- Target interface: resolve_story_coreferences(text, entities) -> normalized payload.
- Backends: remote_fastcoref, fallback_rules, llm_coref (future).

2. Keep KG and model paths shared with generation assets.
- Continue using shared model root and generation KG module path probing.
- Do not couple evaluator execution flow to generation runner.

3. Preserve strict fallback behavior.
- If advanced backend fails, scoring must still complete with fallback rules.

## Environment Preparation Tracks

### Local venv track
- Build_GenAI.bat
- Start_GenAI.bat --eval-only --input output --post-process none
- .env.example

### Docker track
- Build_GenAI_Docker.bat
- Start_GenAI_Docker.bat --eval-only --input output --post-process none
- start.bat retained for legacy one-shot startup

## Cleanup and Migration Checklist
1. Completed
- Coref Docker entry module mismatch fixed.
- Dual-environment script set introduced.
- Shared model/KG path direction aligned with generation assets.
- Coref backend mode and timeout env controls added (`COREF_BACKEND_MODE`, `COREF_TIMEOUT_SEC`).
- Coref fallback payload now includes standardized explainability fields (`backend_mode`, `fallback_mode`, `degradation_reason`).
- Coref backend adapter extracted to `shared/coref_backends.py` and wired through `consistency.py`.
- Deprecation criteria documented in ADR: `docs/adr/ADR-0001-coref-backend-retirement.md`.

2. Next (no testing yet)
- Add regression benchmark script for backend parity gate (quality/latency/reliability).
- Add a release checklist step that enforces ADR exit criteria before removing `coref-service`.

3. Later
- Benchmark quality/cost of llm_coref backend on representative story set.
- If acceptable, decommission Dockerfile.coref and coref-service from compose.

## Definition of Ready Before Integration
1. Environment workflows are deterministic for both local and Docker paths.
2. Coreference backend strategy is documented and switchable.
3. Shared resource paths (models/KG) are stable and configurable.
4. Legacy artifacts are either removed or explicitly marked as transitional.
