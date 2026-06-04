# Current Product State

Last updated: 2026-05-25
Status: Active source of truth for product progress and agent continuity

Canonical long-form vision and architecture:
[../research/deep-research-report.md](../research/deep-research-report.md)

Canonical master project view:
[../MASTER_PROJECT_VIEW_2026-04-22.md](../MASTER_PROJECT_VIEW_2026-04-22.md)

Canonical active workplan:
[../strategy/TEXT_FIRST_MOAT_WORKPLAN_2026-05-20.md](../strategy/TEXT_FIRST_MOAT_WORKPLAN_2026-05-20.md)

Self-dogfood architecture and execution:
[../architecture/SELF_DOGFOOD_TARGET_ARCHITECTURE_2026-05-25.md](../architecture/SELF_DOGFOOD_TARGET_ARCHITECTURE_2026-05-25.md)
[SELF_DOGFOOD_30_DAY_PLAN_2026-05-25.md](./SELF_DOGFOOD_30_DAY_PLAN_2026-05-25.md)

## Reporting Rule
Этот файл - единая короткая точка состояния для Codex и Claude Code.

Обновлять только секции:
- `Current Wedge`
- `Golden Path`
- `What Works Now`
- `Known Issues`
- `Next Step`
- `Last Update`

Правила:
- 3-7 bullets максимум
- без длинной истории
- без дублирования старых апдейтов
- только текущее состояние, blockers и следующий ход

## Current Wedge
- Активный wedge цикла: self-dogfood подготовка к первой remote hard-currency работе в `ML/AI/SWE-adjacent` направлении.
- Базовая модальность: `text-first` через typed/composer flow; voice остается opt-in delivery layer.
- Главный фокус: `CareerProfile -> VacancyContext -> Mission -> text session -> Evidence -> Next Mission`.
- `project_walkthrough` допустим только как interview-supporting artifact.
- `workplace_communication` вне mainline scope текущего цикла.
- Voice provider work и Inworld/OpenAI/Hume comparisons отложены до text gates и отдельного benchmark gate.

## Golden Path
1. Founder profile фиксирует target role, remote/hard-currency constraint и реальные проекты.
2. Vacancy context из реальных вакансий превращается в interview-prep mission.
3. Typed/composer session тренирует один конкретный ответ или artifact.
4. Session сохраняет evidence: raw answer, correction, gaps, readiness signal.
5. Next mission объясняет, что делать завтра и почему это помогает поиску работы.
6. Voice подключается только если text loop уже показал ценность или speaking pressure стал наблюдаемым blocker.

## What Works Now
- `technical_project_walkthrough` now uses `MissionContract` slot policy: raw answer -> captured mission slots -> one missing slot question -> final compact interview answer.
- Onboarding now has an LLM-backed `TurnAnalyzer` port for partial intent understanding before legacy routing; high-confidence partial intent can ask the next missing slot instead of repeating the broad goal question.
- Foundation missions now accept useful out-of-order answers: if the learner answers a later anchor such as `recent_project` before `current_work`, the state jumps forward instead of repeating the old anchor.
- `ProgramSnapshot` остается product-facing truth surface для mission, evidence и progression.
- `next_mission_choice` уже прошит в roadmap/session evidence contracts.
- Composer/typed input уже существует во frontend и позволяет валидировать text-first loop без STT/TTS риска.
- `chat_v2` уже смещен к controller-owned runtime вместо endpoint-owned session loop.
- Для оператора есть replay path через `scripts/replay_session.py` по `session_id`.
- `memory_kind` enum alignment применен и проверен на dev DB; fresh SQL bootstrap migration теперь добавляет app-level values.
- `scripts/run_managed_product_eval.py` дает воспроизводимый local eval run: старт API -> `/health` -> synthetic eval -> stop API.
- Есть product synthetic evals и отдельный STT benchmark; их нужно держать раздельно.

## Routing Invariants
- `primary_context` остается источником истины для first useful mission.
- `goal_brief` и session evidence остаются server-owned state.
- Voice - delivery layer; evidence - control layer.

## Known Issues
- Text-first interview loop прошел synthetic check; теперь нужен founder live/dogfood run: profile -> mission -> evidence -> next mission.
- Founder `CareerProfile` и real vacancy input пока не зафиксированы как работающий end-to-end slice.
- Качество correction/feedback может быть все еще слишком generic для moat.
- Replay по `session_id` должен стать обязательной частью pilot workflow, а не ad hoc debug.
- В репозитории остаются transitional voice paths; их не расширять до прохождения text gates.
- Старые документы про voice-first и три bucket'а читать только через призму текущего text-first interview sprint.

## Next Step
- Провести первый founder typed/composer run: profile -> mission -> answer -> evidence -> next mission.
- Собрать один replay bundle по `session_id` и проверить, что evidence объясняет next mission.
- Если replay показывает weak mission relevance или generic feedback, чинить бизнесовую логику до voice work.

## Last Update
- Founder dogfood exposed a project-walkthrough loop issue; backend now handles it through `MissionContract` rather than case-specific learning-node branches.
- Founder dogfood also exposed onboarding repetition on `hr interview`; next step now uses `TurnAnalyzer` structured output to ask for the missing target role instead of hardcoding an auto-route.
- Founder dogfood exposed foundation anchor drift after a project answer; learning state now moves to the matched later anchor instead of re-asking current-role wording.
- `memory_kind` blocker закрыт: dev DB принимает `fact/preference/experience/goal/error_pattern`, SQL bootstrap migration обновлена.
- `interview_self_intro_gap` synthetic eval прошел через managed local runner: PASS, score 100%.
- Следующий gate: founder typed/composer self-dogfood run и replay по `session_id`.
- Voice benchmark остается нужным, но только после text/product gates и наблюдаемой нужды в speaking pressure.
