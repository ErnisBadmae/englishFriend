# Current Product State

Last updated: 2026-05-06
Status: Active source of truth for product progress and agent continuity

Canonical long-form vision and architecture:
[../research/deep-research-report.md](../research/deep-research-report.md)

Canonical master project view:
[../MASTER_PROJECT_VIEW_2026-04-22.md](../MASTER_PROJECT_VIEW_2026-04-22.md)

## Reporting Rule
Этот файл — единая точка для коротких обновлений от Codex и Claude Code.

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
- Активный wedge цикла: только `ML/SWE interview prep`.
- Цель валидации: не “красивое демо”, а один удержанный пользователь, который возвращается в `session 2`.
- Mainline модальность цикла: `text-first`; voice — `opt-in` и не должен блокировать проверку ценности.
- `project_walkthrough` допустим только как supporting interview artifact.
- `workplace_communication` вне активного mainline scope этого спринта.

## Golden Path
1. Сначала делаем discovery, потом build.
2. Подтверждаем, что interview-prep pain достаточно реален, чтобы оправдать цикл.
3. Пользователь входит в interview loop через typed/composer baseline.
4. Система подтверждает interview direction и запускает первую полезную mission.
5. Сессия сохраняет evidence и делает следующую mission понятной.
6. Пользователь возвращается в `session 2` из-за felt relevance, а не из-за внешнего polish.

## What Works Now
- `ProgramSnapshot` остается product-facing truth surface для mission, evidence и progression.
- `next_mission_choice` уже явно прошит в roadmap/session evidence contracts.
- Для оператора появился replay path через `scripts/replay_session.py` по `session_id`.
- `chat_v2` уже смещен в сторону controller-owned runtime вместо отдельного endpoint-owned session loop.
- Composer/typed input уже существует во frontend и позволяет сделать `text-first` baseline без изобретения нового user path.
- Для founder workflow появился явный `Phase 0` pack: sourcing runbook, target sheet template, outreach scripts и call-notes template.

## Routing Invariants
- `primary_context` остается источником истины для first useful mission.
- `goal_brief` и session evidence остаются server-owned state.
- Voice — delivery layer; evidence — control layer.

## Known Issues
- `memory_kind` schema mismatch остается blocker, пока миграция не применена и не проверена на реальной БД.
- В репозитории все еще есть transitional voice code paths; convergence mainline runtime не завершен полностью.
- Observability уже есть, но replay по `session_id` должен стать нормальной частью pilot workflow, а не разовой отладкой.
- Warm-network feedback сам по себе слабый сигнал; нужен минимум один cold discovery call и один cold pilot user.
- Старые документы про три bucket’а нужно читать только через призму текущего interview-only sprint.

## Next Step
- Провести 5 discovery calls, включая минимум 1 cold call, до фиксации полного implementation scope.
- Заполнить [DISCOVERY_TARGET_SHEET_TEMPLATE.csv](./DISCOVERY_TARGET_SHEET_TEMPLATE.csv) и отправить первую волну outreach по [DISCOVERY_OUTREACH_SCRIPTS.md](./DISCOVERY_OUTREACH_SCRIPTS.md).
- Применить и проверить memory enum migration.
- Добить convergence runtime ownership для `chat_v2`.
- Гонять pilots на typed interview sessions и отслеживать `Tier 1/2/3` сигналы после сессии.

## Last Update
- Активный план сместился с broad product-engineering roadmap на founder-learning sprint.
- Текущий цикл теперь явно `interview-only`, `text-first` и `retention-driven`.
- Replay по `session_id` стал частью operator story, а не просто ad hoc log spelunking.
