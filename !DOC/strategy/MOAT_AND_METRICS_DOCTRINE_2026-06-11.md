# Moat & Metrics Doctrine for the Commoditized-Intelligence Era

Last updated: 2026-06-11
Status: strategic architecture doctrine; read together with TEXT_FIRST_MOAT_WORKPLAN

## Premise

Within ~1-2 years, frontier-class inference becomes a local commodity:
DGX Spark already runs 120B-class models on a desk; consumer RTX Spark laptops
(128GB unified memory, ~1 PFLOP FP4) ship via OEMs from fall 2026. Self-hosted
open models (Hermes/Qwen/Llama class) rival proprietary systems.

Consequence: "we have a smart LLM" is zero moat. Anyone's laptop will run a
model as good as ours. EnglishFriend must be designed so that **commoditized
intelligence is a tailwind, not a threat**.

We already live in this future internally: mainline inference runs on a local
Qwen via vLLM. The architecture stance below makes that a strategy, not an
accident.

## Core Thesis

When intelligence is free, the scarce assets are:

1. **The evidence ledger** — structured, longitudinal, schema'd record of what
   this learner actually said, which errors recurred, what improved, which
   artifacts were produced. A blank local LLM has none of this. Raw chat logs
   are NOT a moat (exportable to any model); **typed, comparable-over-time
   evidence** is.
2. **The measurement system** — rubrics and judges that know what "good" means
   for a Russian-speaking ML engineer in a Western interview, calibrated
   against real outcomes (passed screens, used artifacts). This is the data
   flywheel: sessions → labeled evidence → calibrated judges → sharper
   feedback → more sessions. A competitor starting later cannot shortcut the
   calibration data.
3. **The coaching policy** — mission progression (repeat-vs-advance, what to
   practice next and why) driven by accumulated evidence, not by a static
   lesson list and not by model vibes.
4. **Russian-speaker error taxonomy** — niche domain IP. Seed already exists
   (`russian_error_detector.ErrorCategory`); it must become a longitudinal
   per-learner ledger, not a per-turn hint.
5. **The model-agnostic engine port** — the LLM is a replaceable engine behind
   `llm_provider`. The product must get BETTER when models improve, and must
   accept a user-supplied local model (BYO-model) without losing the moat,
   because the moat lives in state and measurement, not in the model.

What is explicitly NOT a moat: prompts, graph/vector infrastructure, voice
latency, UI polish, provider choice.

## Architecture Rules (extend the Clean Architecture rule)

- The domain core must not depend on delivery mechanisms **or on the
  intelligence provider**. Any node must work against any OpenAI-compatible
  endpoint that meets a small capability contract (JSON reliability, context
  size).
- PostgreSQL evidence ledger is the system of record. Append-only in spirit:
  corrections produce new versions, never overwrite the raw answer.
- **Provenance is mandatory**: every evidence record and every judged feedback
  must be stamped with `model_id` + `prompt_version` (today only
  career_classifier does this). Without provenance the flywheel cannot compare
  feedback quality across models, and old data cannot be relabeled.
- Error events persist with `ErrorCategory` granularity per session, so
  recurrence can be trended per learner. Taxonomy evolves by versioned
  migration, never by silent renaming.
- Evals are product infrastructure, not dev tooling. A judge failure is a
  product regression.

## Metrics (computable solo, dumb SQL first, no dashboards)

### L1 — Usefulness ("would I open it tomorrow?")
- `evidence_reuse_rate`: % of sessions whose mission/feedback referenced prior
  evidence (replay shows the link)
- `return`: prep sessions per week (solo proxy for retention)
- `artifact_export`: count of InterviewPack artifacts actually used outside
  the app (recruiter screen, real interview) — the ultimate dogfood signal
- `beats_blank_chatgpt`: per-session binary judgment (self-rated first,
  LLM-judge proxy later)

### L2 — Learning effectiveness ("is the learner improving?")
- `error_recurrence`: occurrences per 100 words for the learner's top-3
  ErrorCategory classes, trended across sessions — THE learning metric
- `answer_structure_score`: rubric trend (STAR completeness, quantified
  impact, tradeoff present)
- `time_to_usable_artifact`: sessions needed to bring an artifact
  (self-intro, STAR story) to "usable outside the app"

### L3 — System quality ("can we trust the machine?")
- deterministic eval pass rate (exists: run_product_synthetic_eval)
- feedback-specificity judge score (planned LLM-as-judge step)
- evidence persistence rate; replayability rate by session_id
- judge-vs-human agreement on the golden set (target 75-90%)

North star for the dogfood cycle: **every session leaves a structured trace,
and the learner's top recurring error class shrinks session over session**
(= evidence_reuse_rate up, error_recurrence down).

## What to lay down NOW (cheap now, impossible to retrofit)

1. Typed domain core (approved plan Step 1) — the ledger schema IS the durable
   asset. Chat-log soup cannot be restructured retroactively.
2. Provenance stamps (`model_id`, `prompt_version`) on evidence and feedback.
3. Error-taxonomy persistence: per-session ErrorCategory counts linked to
   evidence, enabling `error_recurrence`.
4. LLM-as-judge + golden set (approved plan Step 2); golden set accumulates
   from real dogfood sessions.
5. Metric definitions above as SQL/script, computed per dogfood week.

## What NOT to do now

- No model fine-tuning or custom training.
- No multi-tenant/BYO-model productization before the founder loop works.
- No graph/vector expansion; no voice (gates unchanged).
- No dashboards; a weekly script printout is enough for one user.

## Relationship to existing plans

This doctrine does not change the approved sequence
(dogfood → typed domain core → feedback-quality judge). It sharpens WHY and
adds three cheap requirements: provenance stamps, error-taxonomy persistence,
metric definitions.

## References

- TEXT_FIRST_MOAT_WORKPLAN_2026-05-20.md (gates, wedge, anti-roadmap)
- SELF_DOGFOOD_TARGET_ARCHITECTURE_2026-05-25.md (domain core, data ownership)
- Anthropic, Building Effective Agents (simplicity, workflow-over-agent)
- Data-flywheel / system-of-record moat analyses (2025-2026): models
  commoditize; defensibility = data + behavioral + workflow layers,
  compounding with time-in-market
