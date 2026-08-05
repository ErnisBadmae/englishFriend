# Current Product State

Last updated: 2026-07-27
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
- Миграции `012`-`017` применены и живут в PostgreSQL; PostgreSQL остается canonical storage для практики, карьерного журнала и ожидаемого Telegram-ввода.
- Live-срез данных на 2026-07-22: 5 сессий, 18 items, 10 attempts, 0 external_reviews, 15 approved + 15 draft вопросов, 1 progress review, 0 карьерных откликов.
- 137 focused pytest-тестов проходят на текущем состоянии кода и схемы.
- Telegram ML polling теперь live; прежний блокер "нет BotFather token / нет привязанного Telegram ID" устарел.
- Qdrant и Neo4j остаются future derived indexes для этого среза - не участвуют в bootstrap или canonical storage миграций `012`-`016`.
- Career ledger v0 (`career_vacancy_snapshots`, `career_applications`, `career_application_events`, миграция `016_career_ledger.sql`) работает рядом с `ml_technical`: `/applied` и `/applications` в том же private Telegram-боте пишут через `CareerLedgerService`, MCP читает через `get_career_pipeline_summary` / `get_career_pipeline_review_context` (read-only, bounded, hash-stamped). Миграция `016` применена к live dev-базе 2026-07-22.
- Telegram career menu v0.2.1 хранит 30-минутный pending intent в `career_telegram_pending_inputs`: корректность больше не зависит от `ForceReply`, `reply_to_message` и скрытых маркеров. Порядок маршрутизации: command -> pending career input -> корректные три поля -> vacancy-link guard -> ML. Успех, `Отмена` и `/start` очищают intent; 47 focused pytest зелены на отдельной PostgreSQL-базе.
- Career Inbox v0 Slice A+B+C (`career/CAREER_TELEGRAM_COCKPIT_SPEC.md`) в проде: миграция `018_career_inbox.sql` (`career_inbox_items`, `career_feedback_events`, pending intents `career_manual_lead`/`career_feedback` с ephemeral `payload`) применена к **dev**-базе после backup (`C:\tmp\englishfriend_dev_pre_018_prod_*.dump`); `CAREER_INBOX_ENABLED=true` в `.env`; бот перезапущен, read-only smoke зелёный. `app/services/career_inbox_service.py` — owner-only, идемпотентный (manual lead, verdict, applied-after-prepare, append-only feedback с grounded-quote gate) плюс `import_snapshot`/`validate_import_envelope` (Slice B, idempotent import, versioned content_hash, latest-only `list_inbox_items`, bound 7).
- Career Inbox batch paste v0: `split_pasted_leads` (pure, numbered/blank-line сегментация, MAX_PASTED_LEADS=10) чинит баг "вставил список — сохранился только последний". Paste теперь строит очередь черновиков в одном pending intent (`{"queue": [...], "index": N}`), каждый лид подтверждается/пропускается отдельно (`Лид X из N`), callback data несёт индекс лида — replay старого tap не может подтвердить не тот сегмент. Живой бот перезапущен с этим фиксом.
- Career Cover Letter Draft v0 (`career/CAREER_COVER_LETTER_DRAFT_SPEC.md`, ратифицирован владельцем) за отдельным флагом `career_cover_letter_draft_enabled=true` в `.env` (независим от `career_inbox_enabled`): миграция `019_career_cover_letter_draft.sql` применена к **dev**-базе 2026-07-24 (backup `C:\tmp\englishfriend_dev_pre_019_20260724T151236.dump`), `CareerCoverLetterDraft` — immutable версии, статус меняется один раз (`draft`→`owner_approved`|`rejected`). `generate_cover_letter_draft` читает `career/facts_bank.yaml` (только тир A) как единственный источник фактов, LLM — недоверенный drafter; `build_grounding_report` детерминированно флагает предложения с числом/меткой, отсутствующей в фактах. Пустой/битый facts_bank или сбой LLM → черновик не создаётся, только manual-path сигнал. Кнопка «Черновик сопровода» появляется в Telegram только после `Готовить`; `Одобрить`/`Отклонить`/`Скопировать` не создают заявку и ничего не отправляют. D0 live acceptance (2026-07-27): 165 focused career/ledger/vacancy-refresh pytest зелены на изолированной test PostgreSQL (`englishfriend_test_018`); живые dev-данные подтверждают реальный цикл (8 draft-строк, включая `owner_approved` и `rejected` от 2026-07-27, ни одна не создала заявку сама по себе — `applied` появился отдельным явным действием владельца 23 минуты спустя).
- Vacancy refresh button v0: кнопка «Проверить новые вакансии» в Карьере (флаг `career_vacancy_refresh_enabled=true`) запускает `telegram-digest/refresh_vacancies.py` (fetch → triage → export) как subprocess, затем импортирует результат через `scripts/import_career_inbox.py`; busy-guard блокирует параллельный повторный запуск. Не scheduler — только явный клик владельца. Живой end-to-end прогон на dev 2026-07-24: `imported=4 skipped_duplicate=3 rejected=0`.
- Career OS Slice D1a (`career/CAREER_OPERATING_SYSTEM_V1_SPEC.md`) — application package contract, service/storage только, без Telegram UX: миграция `020_career_application_package.sql` применена только на изолированной test PostgreSQL (`englishfriend_test_018`), **не на dev**, флаг не добавлялся. `CareerApplicationPackage` — immutable snapshot (inbox item content_hash, final gates + hash, owner-approved cover draft id/version/text hash + `used_fact_ids`, `facts_bank_hash`, `cv_variant_id`/`cv_content_hash` из существующего `role_types` в `facts_bank.yaml` — новый CV-matcher не строился) с `package_content_hash` и одноразовым переходом `ready`→`submitted`. `prepare_application_package`/`submit_application_package` в `career_inbox_service.py`: idempotent prepare (по content hash), idempotent submit (по idempotency_key), `submit` требует совпадения `expected_package_hash` и блокирует как stale при изменении vacancy/gates/cover-версии/CV/facts_bank; `submit` переиспользует существующий `CareerLedgerService.record_manual_application` (тот же путь, что и `confirm_applied`) — package не создаёт application/event сам. `record_manual_application` получил необязательный `event_metadata` для трассировки `application_package_id`. 193 focused pytest зелены на test PostgreSQL (179 существующих + 14 новых package-тестов).
- Career OS Slice D1b.1 (package creation UX) — за флагом `career_ready_queue_enabled=False` (default off, не включён нигде): после `owner_approved` черновика появляется кнопка «Собрать пакет» → бот показывает до 3 CV-вариантов из `facts_bank.yaml -> role_types` (новый matcher не строился) → выбор вызывает уже существующий D1a `prepare_application_package` через новую тонкую gateway-обёртку в `ml_technical_bot.py`. `career_inbox_service.py` не менялся. Diff 333 строки (прод ≈123), migration `020` не трогал (dev не тронут). 187 focused pytest зелены на test PostgreSQL.
- Career OS Slice D1b.2a (ready queue, read-only) — тот же флаг `career_ready_queue_enabled`: меню «Готовые» показывает до 7 пакетов (`list_ready_application_packages` — единственный новый query, только `status=ready`, newest-first, owner-only), карточка-превью показывает company/role/человекочитаемое имя CV (из того же `role_types` mapping, без нового registry), final gates, максимум 2 вопроса, source URL, короткий hash и кнопку «Скопировать сопровод» (переиспользует существующий `_career_draft_copy_callback`). Diff ≈280 строк (прод ≈106), migration `020` не трогал (dev не тронут). 195 focused pytest зелены на test PostgreSQL.
- Career OS Slice D1b.2b (двойное подтверждение «Отправлено») — замыкает package flow полностью в рамках того же флага: preflight на реальной Postgres подтвердил, что submit одного package с двумя разными idempotency key не создаёт вторую заявку (только `CareerInboxError`, event остаётся ровно один) — это теперь постоянный регресс-тест. Первый клик «Отправлено» ничего не пишет и показывает company/role/hash-префикс; `Подтвердить` заново читает package, требует совпадения текущего полного hash с показанным префиксом (иначе fail-closed «Пакет изменился»), передаёт полный canonical hash в уже существующий `submit_application_package`; повторный любой replay (тот же callback id или другой) не создаёт вторую заявку — если package уже не `ready`, бот показывает безопасный результат без повторного вызова submit. `Отмена` не делает ни одного вызова gateway. Package-сервис не менялся, прод-код ≈94 строки (в рамках цели 130). Diff ≈321 строка — немного выше общего бюджета 300 (см. отчёт задачи, причина в 8 bot-тестах + 1 обязательном PG-регресс-тесте на invariant из preflight). Migration `020` не трогал (dev не тронут). 204 focused pytest зелены на test PostgreSQL.
- Career OS D1c live acceptance пройден владельцем 2026-07-29: migration `020`/ready queue включены в private bot, полный `cover -> CV -> package -> exact preview -> sent-confirmation -> application` flow проверен на реальных откликах; после owner UX-правок выполнен повторный smoke. Следующий blocker находится upstream: текущая vacancy queue исчерпана, поэтому открыт отдельный HH read-only source pilot в `telegram-digest`.
- Slice B exporter: `telegram-digest/export_career_inbox.py` — детерминированный JSONL top-7 `apply_candidate`/`outreach`, только final gates (без `model_status`/`fit`/`hard_fail_reasons`), без `raw_text`, `evidence_excerpt` только из grounded цитат. Import: `englishFriend/scripts/import_career_inbox.py` — explicit CLI-файл, без sibling-repo reads, без общей БД/HTTP. Реальный round-trip (7 карточек из настоящего `data/vacancies.jsonl`) прогнан на тестовой БД дважды: `imported=7` затем `imported=0 skipped_duplicate=7` — доказано отсутствие дублей; заявок (`career_applications`) import не создаёт. 106 focused pytest зелены на тестовой Postgres (Slice A: 90, Slice B: +16). Feature flag остаётся `False` — включение и личный Telegram-смоук ждут отдельного owner-действия (Slice C).

## Routing Invariants
- `primary_context` остается источником истины для first useful mission.
- `goal_brief` и session evidence остаются server-owned state.
- Voice - delivery layer; evidence - control layer.

## Known Issues
- Live refresh on 2026-08-05 exposed an import-identity defect: owner verdict and
  applied commands overwrite `career_inbox_items.idempotency_key`, so a later
  identical `telegram-digest` import can create a duplicate. Eleven of thirteen
  current outreach candidates were repeats. Corrective task:
  `../architecture/SONNET_CAREER_INBOX_IMPORT_IDEMPOTENCY_CORRECTIVE_TASK.md`.
- Career ledger v0.2.1 запущен; после исправления pending-input еще нужна повторная ручная приемка добавления, смены статуса и `Задать следующее действие` в реальном Telegram.
- Text-first interview loop прошел synthetic check; теперь нужен founder live/dogfood run: profile -> mission -> evidence -> next mission.
- Founder `CareerProfile` и real vacancy input пока не зафиксированы как работающий end-to-end slice.
- Качество correction/feedback может быть все еще слишком generic для moat.
- Replay по `session_id` должен стать обязательной частью pilot workflow, а не ad hoc debug.
- В репозитории остаются transitional voice paths; их не расширять до прохождения text gates.
- Старые документы про voice-first и три bucket'а читать только через призму текущего text-first interview sprint.
- `scripts/run_managed_product_eval.py` и STT benchmark не входят в offline night queue: это кандидаты только после подъёма API/DB/voice stack.
- Career package flow жив и принят. Наблюдаемый карьерный blocker теперь не UX, а отсутствие новых релевантных source items; HH pilot не должен добавлять OAuth/submit/scheduler в EnglishFriend.

## Next Step
- До следующего vacancy refresh исправить import identity по corrective task и
  доказать регрессией: `import -> verdict/applied -> same import` создаёт ноль
  новых inbox-строк. Текущую уже загруженную очередь можно разбирать вручную.
- Записать через `/applied` два уже отправленных отклика и сверить `/applications` с фактической воронкой.
- Провести первый founder typed/composer run: profile -> mission -> answer -> evidence -> next mission.
- Собрать один replay bundle по `session_id` и проверить, что evidence объясняет next mission.
- Если replay показывает weak mission relevance или generic feedback, чинить бизнесовую логику до voice work.
- Первый founder dogfood `ml_technical` через сайт пройден: основной цикл работает, но банк из 15 вопросов все еще мал. Telegram polling теперь live; для банка - exact-match private-corpus check + owner approval для draft-ревизий `mltech_016`..`mltech_030`.
- Провести ручную приемку Telegram career menu v0.2.1 по пунктам 8-11 `ML_TECHNICAL_TELEGRAM_RUNBOOK.md`: ввод без reply-метаданных, невалидный формат, голая ссылка, переход статуса и следующее действие. Автоподачу откликов не включать.
- Не расширять Career Inbox до появления новых данных. Следующий карьерный срез выполняется в `telegram-digest`: HH read-only source pilot, затем текущий import path.

## Last Update
- 2026-08-05: на живом повторном импорте подтверждён дефект identity: 11 из 13
  outreach-карточек оказались ранее виденными вакансиями. Root cause локализован в
  перезаписи стабильного import idempotency key командами владельца; подготовлена
  узкая corrective-задача без миграции и без изменения `telegram-digest`.
- 2026-07-29: Career OS D1c принят владельцем после live smoke, UX-коррекции и реальных откликов. Package flow работает end-to-end; новым blocker признано исчерпание vacancy queue. EnglishFriend-код не расширять до результата HH read-only source pilot.
- 2026-07-27: Career OS D0 live acceptance (Sonnet) — migration `019` и флаг подтверждены уже применёнными к dev (не заново); 165 focused pytest зелены на `englishfriend_test_018`; verdict **D0 PASS**, детали в отчёте задачи.
- 2026-07-27: Career OS D1a application package contract (Sonnet) — новая таблица после доказанного reuse-разбора (cover draft snapshot и application event payload не могут безопасно хранить pre-application immutable state); migration `020` только на test PostgreSQL, dev не тронут, feature flag не добавлялся; 193 focused pytest зелены; verdict **D1a PASS**, детали в отчёте задачи.
- 2026-07-27: Career OS D1b.1 ready-queue package creation (Sonnet) — общий diff-бюджет (400 строк) заставил разбить D1b на D1b.1 (создание пакета, сделано) и D1b.2 (очередь «Готовые» + двойное подтверждение отправки, не начато); diff 333 строки, `career_inbox_service.py`/migration/dev не тронуты; 187 focused pytest зелены; verdict **D1b.1 PASS**.
- 2026-07-27: Career OS D1b.2a ready-queue read-only preview (Sonnet) — бюджет D1b.2 (350 строк) заставил разбить его на D1b.2a (очередь+preview, сделано) и D1b.2b (Отправлено/confirm/submit/stale/replay, не начато); diff ≈280 строк, migration/dev не тронуты; 195 focused pytest зелены; verdict **D1b.2a PASS**.
- 2026-07-28: Career OS D1b.2b sent-confirmation (Sonnet) — обязательный preflight на Postgres подтвердил инвариант «0 duplicate applications» до Telegram-кода; package flow (создание → очередь → двойное подтверждение → submit) замкнут полностью в рамках одного флага `career_ready_queue_enabled`; diff ≈321 строка (бюджет 300, прод 94 из 130); migration/dev не тронуты; 204 focused pytest зелены; verdict **D1b.2b PASS**.

- Delivery-layer cleanup завершен: один движок (`graph_v2`), `onboarding` разрезан на focused-модули, честная `AgentState` schema + drift-guard test, `conversation_runtime` (text-first, `text_only` явный), границы routing задокументированы.
- Codex WIP (MissionContract, TurnAnalyzer, memory_kind migration, eval runner, frontend composer) закоммичен логическими чекпойнтами; флаки onboarding-тестов стабилизированы (`deterministic_routing` fixture).
- Принята moat & metrics doctrine: модель = заменяемый порт, моат = evidence ledger + measurement + coaching policy; обязательные provenance stamps и error-taxonomy persistence (см. canonical link выше).
- Утвержден порядок: dogfood -> typed domain core -> LLM-as-judge на качество фидбэка; метрики L1/L2/L3 определены в доктрине.
- Следующий gate: founder typed/composer self-dogfood run и replay по `session_id`; первый наблюдаемый blocker задает приоритет.
- Voice benchmark остается нужным, но только после text/product gates и наблюдаемой нужды в speaking pressure.
- Подготовлена реплика `night_runner` v1.1 для EnglishFriend: `C:/tmp/englishfriend-qwen-runs`, очередь `scripts/night_queue.json`, offline no-prompt baseline из двух pytest-наборов + `lint-imports`.
- Layering-прививка в работе: роутеры берут `get_db` из `app.core.deps`, shared voice-session persistence вынесен из `app.api.voice_helpers` в сервисный слой без изменения поведения.
- **ml_technical** трек прошёл первый пользовательский web-dogfood: цикл функционален. Наблюдаемые ограничения - слабый ежедневный канал, тонкий банк и неатомарный JSONB read-modify-write, который нельзя оставлять без защиты при одновременной записи из Telegram и MCP.
- 2026-07-21: миграции `012`-`015` подтверждены live в PostgreSQL, API healthy, зафиксирован live-снимок данных (3 сессии, 8 items, 6 attempts, 0 external_reviews, 15 approved + 15 draft вопросов, 90 QA-записей, 1 progress review), 137 focused тестов проходят. Telegram-адаптер реализован, polling теперь live; см. `ML_TECHNICAL_ACCEPTANCE_2026-07-21.md` для evidence-based приемки.
- 2026-07-22: Career ledger v0 реализован Sonnet после Graphify-разбора и принят Codex: добавлена сериализация конкурентных переходов, 30 focused-тестов зелены, включая 10 PostgreSQL-backed тестов. Перед миграцией создан backup `C:\tmp\englishfriend_dev_pre_career_ledger_20260722.dump`; `016` применена к live dev-БД, read-only Telegram smoke зеленый, polling перезапущен без ошибок.
- 2026-07-22: Career Telegram menu v0.2 реализован Sonnet после Graphify-разбора; Qwen провел read-only diff-аудит и добавил две PostgreSQL-регрессии. Codex принял срез на отдельной тестовой БД: 47 focused pytest зелены, polling перезапущен без ошибок. Ошибочная ML-попытка с HH-ссылкой, возникшая до vacancy-link guard, удалена из прогресса и соответствующий пункт помечен пропущенным. Коммит не создавался.
- 2026-07-22: Ручная приемка вскрыла дефект `ForceReply`: Telegram-клиент не передал `reply_to_message`, а zero-width маркер отобразился. v0.2.1 переведен на PostgreSQL pending intent после Graphify-анализа; Sonnet сделал storage и основной Telegram-срез, младший Codex довел тесы, Qwen дал read-only PASS. 47/47 focused tests зелены; backup `C:\tmp\englishfriend_dev_pre_pending_20260722.dump` создан, `017` применена, polling перезапущен, read-only smoke зеленый. Коммит не создавался.
