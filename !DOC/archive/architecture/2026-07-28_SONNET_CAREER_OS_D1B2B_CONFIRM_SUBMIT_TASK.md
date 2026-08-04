# Sonnet task: Career OS D1b.2b sent-confirmation

Статус: completed - D1b.2b PASS 2026-07-28  
Владелец внешних действий и live rollout: Эрнис  
Исполнитель: Claude Code / Sonnet  
Master SPEC: `../../../career/CAREER_OPERATING_SYSTEM_V1_SPEC.md`, Slice D1b.2b

## Подтверждённая предпосылка

D1b.2a принят 2026-07-27:

- `Готовые` owner-only, newest-first и bounded до 7;
- preview уже показывает company/role/CV/gates/questions/source/cover/short hash;
- submitted/expired package исчезает из списка;
- feature flag default off;
- 195 focused tests зелёные;
- migration `020` всё ещё только в test DB.

Не менять ready query, preview и CV labels.

## Пользовательский результат

После того как Эрнис сам отправил отклик во внешней системе:

```text
package preview
-> Отправлено
-> company / role / тот же short hash
-> Подтвердить | Отмена
-> ровно одна application/event либо fail-closed
```

Бот не отправляет CV, cover, сообщение или форму наружу.

## Обязательный preflight до Telegram-кода

Проверить service-level сценарий:

```text
submit одного ready package
с idempotency_key A
затем с другим idempotency_key B
-> одна application и один initial application event
```

Сначала добавить или запустить узкую PostgreSQL-регрессию на этот сценарий.

- Если тест уже проходит, продолжить D1b.2b.
- Если создаётся duplicate либо возникает неидемпотентная ошибка, остановиться с
  `D1b.2b BLOCKED: package submit replay defect`.
- Не исправлять package authority внутри этой Telegram-задачи. Для дефекта потребуется
  отдельная corrective task.

## Simplicity budget

До кода:

1. Прочитать `AGENTS.md`, `CLAUDE.md`,
   `!DOC/operations/CURRENT_PRODUCT_STATE.md`.
2. Прочитать master SPEC только в частях package submit, D1b.2b, acceptance и
   non-goals.
3. Точечный Graphify query по package preview callback, D1a submit service,
   gateway protocol/implementation, confirmation patterns и bot tests.
4. Сверить symbols с актуальным кодом и показать reuse plan + line estimate.

Budget:

- общий diff <=300 строк, включая tests/docs;
- production target <=130 строк;
- если оценка выше, остановиться до кода;
- новые migration/model/config/pending intent/service query запрещены;
- не создавать confirmation framework, token store, registry или formatter class;
- не рефакторить service/bot файлы.

## Telegram flow

### Первый клик

- `Отправлено` виден только у ready package и при существующем feature flag.
- Первый клик заново читает package через существующий gateway.
- Ничего не записывает.
- Показывает company, role и первые 10-12 символов package hash.
- Кнопки: `Подтвердить`, `Отмена`.

### Binding к показанному snapshot

- Confirm callback содержит compact package id и hash prefix, показанный владельцу.
- Полный hash, CV text, cover и URL в callback не помещаются.
- На confirm бот заново читает package.
- Текущий полный hash обязан начинаться с callback hash prefix.
- При несовпадении, status != ready, malformed id или foreign owner - fail-closed.
- Запрещено молча подтвердить новый current snapshot.

### Запись

- После проверки prefix бот вызывает существующий `submit_application_package` с
  package id, полным expected hash и idempotency key.
- Использовать существующий Telegram callback/update idempotency pattern.
- `Отмена` ничего не пишет.
- Success показывает application id/status.
- Package исчезает из `Готовые`.
- Replay того же либо нового callback для уже submitted package не создаёт вторую
  application/event и показывает безопасный результат.

## Разрешённые файлы

- существующий Telegram career adapter;
- gateway protocol/implementation только для вызова существующего submit service;
- focused package service regression и bot tests;
- краткое обновление `CURRENT_PRODUCT_STATE.md` после зелёных tests.

Package service production logic, model, migration и config не менять.

## Acceptance tests

1. Service preflight с двумя разными idempotency keys создаёт одну application/event.
2. Feature flag off скрывает/блокирует action.
3. Первый `Отправлено` не создаёт application/event.
4. Confirmation показывает тот же company/role/hash prefix.
5. `Отмена` ничего не пишет.
6. Confirm callback связан с package id + показанным hash prefix.
7. Changed hash между preview и confirm блокирует submit.
8. Confirm передаёт полный expected hash в service.
9. Success создаёт ровно одну application/event.
10. Submitted package исчезает из ready list.
11. Повтор того же callback не создаёт duplicate.
12. Повтор с другим Telegram update id не создаёт duplicate.
13. Foreign owner, expired/submitted/stale/malformed callback fail-closed.
14. Provider/network/external send path отсутствует.

Запустить существующие inbox, cover, ledger, package, D1b.1, D1b.2a и новые D1b.2b
tests на отдельной PostgreSQL с migration `020`. Dev DB, `.env`, live bot и polling не
менять.

## Non-goals

- применение migration `020` к dev;
- live feature enable/smoke;
- изменение package authority/schema;
- ready query/preview/CV mapping;
- recruiter feedback/next action;
- MCP;
- scheduler/background refresh;
- connector или внешний submit;
- shared library;
- рефакторинг.

## Stop and report

Остановиться после tests. Вернуть:

1. service replay preflight result;
2. Graphify/reuse plan и line estimate;
3. diff против budget;
4. test commands/results;
5. доказательство preview-bound hash, no-write first click, cancel, stale и replay;
6. known limitations;
7. verdict `D1b.2b PASS` или `D1b.2b BLOCKED`.

Не применять migration к dev и не начинать live rollout, D2, D3 или D4.
