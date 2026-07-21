# ML Technical Acceptance 2026-07-21

Статус: evidence-based приемка текущего состояния `ml_technical` (question bank + progress review) на 2026-07-21.
Этот документ фиксирует факты проверки. Он не меняет код, стратегию, очереди или данные БД.

## Область приемки

- Миграции `012_ml_technical_practice.sql`, `013_ml_technical_telegram.sql`, `014_ml_question_bank.sql`, `015_ml_progress_reviews.sql`.
- Версионированный жизненный цикл контента question bank: draft -> deterministic validation -> independent technical/source review -> owner approval.
- MCP-инструменты `ml_technical` (import вопросов, progress review) и API-эндпоинты `ml_technical`.

## Backup перед изменениями

- Файл: `C:/tmp/englishfriend-pre-question-bank-20260721.dump`.
- Размер: 142810 bytes.
- Снят перед применением миграций `014`/`015` и перед batch-импортом draft-вопросов, по аналогии с процедурой в `ML_TECHNICAL_MIGRATION_RUNBOOK.md`.

## Проверки

### Clone / idempotency

- Restore rehearsal-процедура из `ML_TECHNICAL_MIGRATION_RUNBOOK.md` пройдена на отдельной БД перед live-применением.
- Повторный запуск import с тем же `idempotency_key` не создает дублирующую draft-ревизию.

### Live-верификация состояния

- Live-снимок данных после миграций и импорта:
  - 3 сессии, 8 items, 6 attempts, 0 external_reviews в `ml_technical` evidence.
  - 15 approved вопросов в question bank.
  - 15 draft-ревизий с id `mltech_016`..`mltech_030`.
  - 90 QA-записей: 45 baseline QA + 45 batch QA (15 schema pass, 15 technical pass, 15 source_ip needs_changes).
  - 1 progress review, id `c0bd4016-0bbb-4edf-bc5b-8eac6ca9e27f`.
- API healthy на этом состоянии схемы и данных.

### API smoke

- Базовые `ml_technical` эндпоинты отвечают на здоровой схеме `012`-`015` без ошибок 5xx.

### MCP import / progress review

- MCP-инструмент импорта draft-вопросов успешно создал 15 ревизий `mltech_016`..`mltech_030` с привязкой к идемпотентному ключу.
- MCP-инструмент progress review успешно записал одну ревью-запись (`c0bd4016-0bbb-4edf-bc5b-8eac6ca9e27f`) поверх текущего PostgreSQL evidence hash.

### Тесты

- 137 focused pytest-тестов проходят на текущем состоянии кода и схемы.

## Remaining blockers

- Source-review статус `source_ip needs_changes` для 15 из 45 batch QA-записей не закрыт: нужен exact-match private-corpus check и owner approval перед переводом соответствующих draft-ревизий в approved.
- Telegram-адаптер реализован, но polling не запущен: нет отдельного BotFather bot token и реального Telegram ID/allowlist. Локальный User id=11 имеет placeholder `telegram_id=23`, не привязанный к реальному аккаунту.
- До включения Telegram вживую нужны: получение bot credentials, привязка реального Telegram ID, затем 3 живых drill-прохода с проверкой отсутствия потерянных записей при параллельной записи из web/MCP.
- Qdrant и Neo4j не участвуют в этом срезе - они остаются future derived indexes, а не canonical storage.
