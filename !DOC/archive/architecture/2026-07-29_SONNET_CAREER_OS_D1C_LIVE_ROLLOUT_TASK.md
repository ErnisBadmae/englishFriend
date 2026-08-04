# Sonnet task: Career OS D1c live rollout

Статус: ready after D1b.2b PASS  
Владелец live DB, feature flag и внешних действий: Эрнис  
Исполнитель: Claude Code / Sonnet  
Master SPEC: `../../../career/CAREER_OPERATING_SYSTEM_V1_SPEC.md`, Slice D1c

## Подтверждённая предпосылка

D1 package flow принят на test PostgreSQL:

- D1a package authority;
- D1b.1 package creation и CV selection;
- D1b.2a bounded `Готовые` и preview;
- D1b.2b no-write first click, cancel, hash-bound confirmation и submit;
- 204 focused tests зелёные;
- migration `020` ещё не применена к dev;
- feature flag существует и default `False`.

## Цель

Без нового продуктового кода безопасно включить package flow в private live bot и
доказать один честный end-to-end сценарий:

```text
реально отправленный владельцем отклик, ещё не записанный в ledger
-> approved cover
-> Собрать пакет / выбрать CV
-> Готовые / preview
-> Отправлено / Отмена
-> повтор / Подтвердить
-> одна application/event
-> replay без duplicate
```

Sonnet не выполняет внешнее действие и не подтверждает его вместо Эрниса.

## Preflight

1. Прочитать `AGENTS.md`, `CLAUDE.md`,
   `!DOC/operations/CURRENT_PRODUCT_STATE.md`.
2. Прочитать master SPEC только в частях ownership, D1c, acceptance, rollout и
   non-goals.
3. Проверить git status и не затрагивать чужие изменения.
4. Проверить:
   - точное содержимое и checksum migration `020`;
   - migration/applied state dev DB;
   - test DB state;
   - текущее значение `CAREER_READY_QUEUE_ENABLED`;
   - текущий private bot process и действующий restart/runbook;
   - существующий backup/runbook.
5. Повторить:

```powershell
pytest tests/test_career_inbox_bot.py -q
```

и полный focused career набор D1 на отдельной PostgreSQL с migration `020`.

При красных tests, уже существующей несовпадающей таблице `020` или неизвестном
состоянии dev остановиться до изменений.

## Owner approval gate

До изменения dev DB или `.env` показать Эрнису:

- текущий applied state;
- backup command и ожидаемый path;
- migration checksum;
- единственный меняемый feature flag;
- restart command;
- rollback.

Продолжить только после явного подтверждения владельца.

## Rollout

1. Создать новый timestamped backup dev PostgreSQL.
2. Проверить, что backup существует и имеет ненулевой размер.
3. Применить ровно migration `020` к dev один раз.
4. Проверить:
   - таблица существует;
   - constraints/indexes/RLS присутствуют;
   - существующие `career_*` counts не изменились;
   - package table пуста до owner flow.
5. Включить только `CAREER_READY_QUEUE_ENABLED=true`.
6. Перезапустить private bot по существующему runbook.
7. Выполнить read-only runtime smoke:
   - bot process жив;
   - import/startup без schema error;
   - career menu доступно владельцу;
   - `Готовые` показывает безопасный empty state.

## Owner private smoke

Использовать только вакансию, по которой Эрнис уже реально совершил внешний отклик,
но ещё не зафиксировал его в career ledger. Не создавать фиктивное application.

Checklist владельца:

1. Открыть approved cover.
2. Нажать `Собрать пакет`.
3. Выбрать правильный CV.
4. Открыть `Готовые`.
5. Сверить company, role, CV, gates/questions, cover и short hash.
6. Нажать `Отправлено`, затем сначала `Отмена`.
7. Проверить, что application не появилась.
8. Снова нажать `Отправлено` и `Подтвердить`.
9. Проверить application в `Отклики`.
10. Повторить старый confirm/replay и проверить отсутствие duplicate.

Sonnet после owner действий выполняет только read-only проверку:

- один package со статусом submitted;
- один linked application;
- один initial application event;
- package/application ids связаны;
- ready list больше не содержит package;
- повтор не создал duplicate.

## Запрещено

- новый или изменённый product code;
- изменение migration `020`;
- автоматическое создание synthetic/live package или application;
- отправка отклика/сообщения;
- D2/D3/D4;
- scheduler/background job;
- другой feature flag;
- рефакторинг;
- destructive rollback/down migration;
- очистка live data после smoke.

Если найден дефект, остановиться и вернуть точное воспроизведение. Не исправлять его
в rollout-задаче.

## Rollback

При runtime/UX blocker:

1. `CAREER_READY_QUEUE_ENABLED=false`;
2. restart private bot;
3. additive migration/table и audit data оставить;
4. восстановление backup выполнять только при доказанном повреждении данных и отдельном
   owner approval.

## Acceptance

- preflight tests зелёные;
- timestamped backup существует;
- migration `020` применена ровно один раз;
- counts существующих career tables сохранены;
- feature flag включён отдельно;
- bot runtime smoke зелёный;
- owner прошёл Cancel без write;
- owner подтвердил один реально выполненный внешний отклик;
- package/application/event связаны;
- replay не создал duplicate;
- никакого внешнего действия Sonnet не совершала.

## Stop and report

Остановиться после D1c. Вернуть:

1. preflight;
2. tests;
3. backup path/size;
4. migration checksum и applied state;
5. changed config/docs;
6. runtime smoke;
7. owner checklist;
8. read-only data evidence;
9. rollback state;
10. verdict `D1c PASS` или `D1c BLOCKED`.

Не начинать D2.
