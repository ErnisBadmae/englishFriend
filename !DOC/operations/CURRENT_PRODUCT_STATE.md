# Current Product State

Last updated: 2026-07-21
Status: Active source of truth for product progress and agent continuity

Canonical long-form vision and architecture:
[../research/deep-research-report.md](../research/deep-research-report.md)

Global architecture map:
[../ARCHITECTURE.md](../ARCHITECTURE.md)

Canonical active workplan:
[../strategy/TEXT_FIRST_MOAT_WORKPLAN_2026-05-20.md](../strategy/TEXT_FIRST_MOAT_WORKPLAN_2026-05-20.md)

Self-dogfood architecture and execution:
[../architecture/SELF_DOGFOOD_TARGET_ARCHITECTURE_2026-05-25.md](../architecture/SELF_DOGFOOD_TARGET_ARCHITECTURE_2026-05-25.md)
[SELF_DOGFOOD_30_DAY_PLAN_2026-05-25.md](./SELF_DOGFOOD_30_DAY_PLAN_2026-05-25.md)

Moat and metrics doctrine (commoditized-intelligence era):
[../strategy/MOAT_AND_METRICS_DOCTRINE_2026-06-11.md](../strategy/MOAT_AND_METRICS_DOCTRINE_2026-06-11.md)

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

- `ml_technical` Telegram v0 реализован как отдельный адаптер над тем же `MlTechnicalService`: `/today`, срез до 5 вопросов, progress, skip/cancel, first-class `dont_know`; состояние восстанавливается из PostgreSQL, а не из памяти процесса.
- Миграции `012`-`015` (ml_technical_practice, ml_technical_telegram, ml_question_bank, ml_progress_reviews) применены и живут в PostgreSQL с 2026-07-21; PostgreSQL остается canonical storage, API healthy на этом состоянии схемы.
- Live-срез данных на 2026-07-21: 3 сессии, 8 items, 6 attempts, 0 external_reviews, 15 approved вопросов в question bank, 15 draft-ревизий `mltech_016`..`mltech_030`, 45 baseline QA-записей + 45 batch QA-записей (15 schema pass, 15 technical pass, 15 source_ip needs_changes), 1 progress review (`c0bd4016-0bbb-4edf-bc5b-8eac6ca9e27f`).
- 137 focused pytest-тестов проходят на текущем состоянии кода и схемы.
- Telegram-адаптер implemented, но polling не запущен вживую: нет отдельного BotFather token и реального Telegram ID/allowlist; локальный User id=11 имеет placeholder `telegram_id=23`, не привязанный к реальному аккаунту.
- Qdrant и Neo4j остаются future derived indexes для этого среза - не участвуют в bootstrap или canonical storage миграций `012`-`015`.

## Routing Invariants
- `primary_context` остается источником истины для first useful mission.
- `goal_brief` и session evidence остаются server-owned state.
- Voice - delivery layer; evidence - control layer.

## Known Issues
- Telegram v0 еще не включен вживую: нужны BotFather token, привязка реального Telegram ID к существующему `users` профилю и 3 живых drill-прохода.
- Text-first interview loop прошел synthetic check; теперь нужен founder live/dogfood run: profile -> mission -> evidence -> next mission.
- Founder `CareerProfile` и real vacancy input пока не зафиксированы как работающий end-to-end slice.
- Качество correction/feedback может быть все еще слишком generic для moat.
- Replay по `session_id` должен стать обязательной частью pilot workflow, а не ad hoc debug.
- В репозитории остаются transitional voice paths; их не расширять до прохождения text gates.
- Старые документы про voice-first и три bucket'а читать только через призму текущего text-first interview sprint.
- `scripts/run_managed_product_eval.py` и STT benchmark не входят в offline night queue: это кандидаты только после подъёма API/DB/voice stack.

## Next Step
- После приемки storage cutover применить `013`, выполнить read-only bot smoke и ручной проход `/today` с реального разрешенного аккаунта.
- Провести первый founder typed/composer run: profile -> mission -> answer -> evidence -> next mission.
- Собрать один replay bundle по `session_id` и проверить, что evidence объясняет next mission.
- Если replay показывает weak mission relevance или generic feedback, чинить бизнесовую логику до voice work.
- Первый founder dogfood `ml_technical` через сайт пройден: основной цикл работает, но ежедневный вход через поднятие сайта неудобен, а банк из 15 вопросов слишком мал. Следующий gate перед включением Telegram вживую: bot credentials (BotFather token) и привязка реального Telegram ID вместо placeholder, затем 3 живых drill-прохода; для банка - exact-match private-corpus check + owner approval для draft-ревизий `mltech_016`..`mltech_030`.

## Last Update
- Delivery-layer cleanup завершен: один движок (`graph_v2`), `onboarding` разрезан на focused-модули, честная `AgentState` schema + drift-guard test, `conversation_runtime` (text-first, `text_only` явный), границы routing задокументированы.
- Codex WIP (MissionContract, TurnAnalyzer, memory_kind migration, eval runner, frontend composer) закоммичен логическими чекпойнтами; флаки onboarding-тестов стабилизированы (`deterministic_routing` fixture).
- Принята moat & metrics doctrine: модель = заменяемый порт, моат = evidence ledger + measurement + coaching policy; обязательные provenance stamps и error-taxonomy persistence (см. canonical link выше).
- Утвержден порядок: dogfood -> typed domain core -> LLM-as-judge на качество фидбэка; метрики L1/L2/L3 определены в доктрине.
- Следующий gate: founder typed/composer self-dogfood run и replay по `session_id`; первый наблюдаемый blocker задает приоритет.
- Voice benchmark остается нужным, но только после text/product gates и наблюдаемой нужды в speaking pressure.
- Подготовлена реплика `night_runner` v1.1 для EnglishFriend: `C:/tmp/englishfriend-qwen-runs`, очередь `scripts/night_queue.json`, offline no-prompt baseline из двух pytest-наборов + `lint-imports`.
- Layering-прививка в работе: роутеры берут `get_db` из `app.core.deps`, shared voice-session persistence вынесен из `app.api.voice_helpers` в сервисный слой без изменения поведения.
- **ml_technical** трек прошёл первый пользовательский web-dogfood: цикл функционален. Наблюдаемые ограничения - слабый ежедневный канал, тонкий банк и неатомарный JSONB read-modify-write, который нельзя оставлять без защиты при одновременной записи из Telegram и MCP.
- 2026-07-21: миграции `012`-`015` подтверждены live в PostgreSQL, API healthy, зафиксирован live-снимок данных (3 сессии, 8 items, 6 attempts, 0 external_reviews, 15 approved + 15 draft вопросов, 90 QA-записей, 1 progress review), 137 focused тестов проходят. Telegram-адаптер реализован, но polling не стартован из-за отсутствия отдельного bot token и реального Telegram ID; см. `ML_TECHNICAL_ACCEPTANCE_2026-07-21.md` для evidence-based приемки.
