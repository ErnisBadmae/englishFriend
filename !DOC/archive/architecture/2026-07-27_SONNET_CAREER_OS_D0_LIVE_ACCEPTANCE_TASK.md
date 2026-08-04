# Sonnet task: Career OS D0 live acceptance

Статус: completed - D0 PASS 2026-07-27  
Владелец внешних действий и live confirmation: Эрнис  
Исполнитель: Claude Code / Sonnet  
Master SPEC: `../../../career/CAREER_OPERATING_SYSTEM_V1_SPEC.md`, Slice D0

## Цель

Принять или заблокировать уже реализованный Career Cover Letter Draft на live dev
контуре. Новый продуктовый код не писать, пока smoke не покажет конкретный дефект.

## Перед началом

1. Прочитать `AGENTS.md`, `CLAUDE.md`,
   `!DOC/operations/CURRENT_PRODUCT_STATE.md`.
2. Прочитать master SPEC только в части ownership, safety, Slice D0 и non-goals.
3. Прочитать существующие
   `!DOC/architecture/SONNET_CAREER_COVER_LETTER_DRAFT_TASK.md` и
   `../../../career/CAREER_COVER_LETTER_DRAFT_SPEC.md`.
4. Сделать точечный Graphify query по migration `019`, cover draft service, feature
   flag и Telegram callbacks. Не перестраивать граф без доказательства stale; найденное
   сверить с актуальным кодом.
5. Проверить git status и не затрагивать чужие изменения.

## Разрешённая работа

1. Повторить focused tests cover/inbox/ledger на отдельной test PostgreSQL.
2. Проверить точное имя migration `019`, её applied state и feature flag.
3. Показать владельцу план backup/migration/rollback до изменения dev DB.
4. Только после явного owner approval:
   - сделать backup dev PostgreSQL по существующему runbook;
   - применить ровно migration `019`;
   - включить только cover draft feature flag;
   - перезапустить private bot по действующему runbook.
5. Выполнить synthetic/read-only smoke без внешних сообщений и откликов.
6. Передать Эрнису короткий private Telegram checklist:
   - открыть одну реальную карточку со статусом `Готовить`;
   - сгенерировать draft;
   - увидеть выбранные fact ids/grounding report;
   - проверить `Одобрить`, `Отклонить`, `Скопировать`;
   - подтвердить, что application и external action не созданы.
7. Обновить только краткие секции
   `!DOC/operations/CURRENT_PRODUCT_STATE.md`.

## Запрещено

- Slice D1 и application package;
- новая migration;
- изменение facts bank, CV или root docs;
- import/fetch/Qwen retriage;
- scheduler;
- отправка сообщения или отклика;
- рефакторинг career services;
- новый provider/framework;
- исправление дефекта до точного воспроизведения и отдельного отчёта владельцу.

## Acceptance

- focused career tests зелёные на test PostgreSQL;
- backup создан и путь зафиксирован;
- migration `019` применена ровно один раз;
- feature flag включён отдельно от inbox flag;
- synthetic/read-only smoke зелёный;
- owner private smoke подтверждает корректный draft/grounding/approve/reject/copy;
- нет новой application/event и внешнего submit;
- rollback состоит из выключения feature flag и восстановления по существующему
  runbook, destructive downgrade не выполняется.

## Stop and report

Остановиться после D0. Вернуть:

1. preflight и applied migration state;
2. backup path;
3. точные test/smoke команды и результаты;
4. owner checklist и его результат, если Эрнис уже прошёл;
5. изменённые файлы;
6. найденные defects/risks;
7. явный verdict `D0 PASS` или `D0 BLOCKED`.

При `BLOCKED` не начинать исправление без отдельного owner решения и узкой corrective
задачи.
