# Sonnet task: Career OS D1b.2 ready queue and sent-confirmation

Статус: superseded by bounded split - D1b.2a PASS, D1b.2b separate  
Владелец внешних действий и live rollout: Эрнис  
Исполнитель: Claude Code / Sonnet  
Master SPEC: `../../../career/CAREER_OPERATING_SYSTEM_V1_SPEC.md`, Slice D1b.2

## Подтверждённая предпосылка

D1b.1 принят 2026-07-27:

- approved cover предлагает bounded существующие CV variants;
- Telegram вызывает D1a `prepare_application_package`;
- повторный CV callback не создаёт duplicate package;
- общий feature flag `career_ready_queue_enabled` существует и default `False`;
- 187 focused tests зелёные;
- migration `020` всё ещё только в test DB.

Не менять создание package и не повторять CV-mapping.

## Пользовательский результат

Эрнис открывает `Готовые`, видит до семи immutable packages и после совершённого
внешнего отклика отдельно подтверждает:

```text
company / role / CV / short package hash
-> Отправлено
-> confirmation того же package/hash
-> Подтвердить | Отмена
-> одна application/event либо fail-closed
```

Кнопка не отправляет CV, сообщение или форму наружу. Она записывает факт уже
выполненного владельцем внешнего действия.

## Simplicity budget

До кода:

1. Прочитать `AGENTS.md`, `CLAUDE.md`,
   `!DOC/operations/CURRENT_PRODUCT_STATE.md`.
2. Прочитать master SPEC в частях package, Telegram UX, D1b.2, acceptance и non-goals.
3. Точечный Graphify query по package model/service, career menu/list callbacks,
   approved cover preview/copy, existing confirmation pattern и bot tests.
4. Сверить symbols с актуальным кодом и показать reuse plan + оценку строк.

Budget:

- общий diff <=350 строк, включая tests/docs;
- production target <=180 строк;
- если оценка выше, остановиться до кода и предложить D1b.2a/D1b.2b;
- разрешён ровно один новый service query;
- новая migration/model/feature flag/pending intent запрещены;
- не создавать formatter class, registry, generic pagination или navigation framework;
- не рефакторить `career_inbox_service.py` или Telegram adapter из-за размера.

## Единственный разрешённый service query

Если его ещё нет:

```text
list_ready_application_packages(owner_id, limit <= 7)
```

Инварианты:

- owner isolation;
- только `status=ready`;
- newest first;
- limit 1..7;
- возвращает существующую `CareerApplicationPackage`;
- не вычисляет score и не запускает provider/network;
- не меняет lazy-stale policy D1a.

Другие изменения package authority запрещены.

## Telegram flow

### 1. Меню и bounded list

- Существующий feature flag off скрывает `Готовые` и блокирует callbacks.
- `Готовые` показывает максимум 7 packages и понятное empty state.
- List item: company, role, CV variant, short package hash, номер.
- Callback содержит compact package id.

### 2. Preview

Показывает:

- company и role;
- CV variant человекочитаемо из существующего CV filename/mapping, без нового label
  registry;
- final gates;
- максимум два recruiter questions;
- source URL существующим безопасным способом;
- approved cover через существующий preview/copy path;
- первые 10-12 символов package hash.

Полный raw vacancy text не загружать и не показывать.

### 3. Двойное подтверждение

- Первый клик `Отправлено` ничего не пишет.
- Confirmation показывает company, role и тот же short hash.
- Callback confirmation должен быть связан с показанным snapshot:
  compact package id + hash prefix достаточной длины.
- На `Подтвердить` бот заново читает package, проверяет, что полный canonical hash
  соответствует hash prefix из confirmation, затем передаёт полный expected hash в
  существующий `submit_application_package`.
- Не разрешено молча взять новый current hash, если экран был построен для другого
  snapshot.
- Idempotency key строится существующим Telegram update/callback способом.
- `Отмена` ничего не пишет.

### 4. Результат

- Success показывает application id/status.
- Submitted package исчезает из `Готовые`.
- Stale/expired/hash mismatch/foreign owner/replayed callback дают понятное fail-closed
  сообщение.
- Любой replay создаёт не более одной application/event, даже если Telegram update id
  отличается.

## Разрешённые файлы

- существующий Telegram career adapter;
- package service только для bounded list query;
- существующий gateway protocol/implementation;
- focused package service + bot tests;
- краткое обновление `CURRENT_PRODUCT_STATE.md` после зелёных tests.

Новые model, migration, config field и module/framework запрещены.

## Acceptance tests

Минимум:

1. Feature flag off скрывает menu/action и блокирует callback.
2. Empty ready queue безопасна.
3. List owner-only, newest-first, bounded <=7.
4. Submitted/expired package не отображается.
5. Preview содержит bounded поля и не содержит raw vacancy text.
6. CV label выводится из существующего mapping без нового registry.
7. Первый `Отправлено` не создаёт application/event.
8. `Отмена` ничего не пишет.
9. Confirmation связан с показанным package hash prefix.
10. Changed hash между preview и confirm блокирует submit.
11. Confirm передаёт полный expected hash в service.
12. Success создаёт ровно одну application/event и убирает package из ready list.
13. Повтор того же callback идемпотентен.
14. Повтор с другим Telegram update id также не создаёт вторую application.
15. Foreign owner, stale, expired и malformed callback fail-closed.
16. Provider/network/external send path отсутствует.

Запустить существующие inbox, cover, ledger, package, D1b.1 и новые D1b.2 tests на
отдельной PostgreSQL с migration `020`. Dev DB, `.env`, live bot и polling не менять.

## Non-goals

- применение migration `020` к dev;
- live feature enable/smoke;
- изменение package schema/state machine;
- package creation/CV matcher;
- outreach package;
- recruiter feedback/next action;
- MCP;
- scheduler/background refresh;
- connector или внешний submit;
- shared library;
- рефакторинг services/bot.

## Stop and report

Остановиться после tests. Вернуть:

1. Graphify/reuse plan и line estimate;
2. diff против budget;
3. изменённые файлы;
4. точные tests/results;
5. доказательство preview-bound hash, double-confirmation, stale и replay;
6. known limitations;
7. verdict `D1b.2 PASS` или `D1b.2 BLOCKED`.

Не применять migration к dev и не начинать live rollout, D2, D3 или D4.
