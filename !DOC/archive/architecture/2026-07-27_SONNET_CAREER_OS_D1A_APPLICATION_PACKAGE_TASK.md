# Sonnet task: Career OS D1a application package contract

Статус: completed - D1a PASS 2026-07-27  
Владелец внешних действий: Эрнис  
Исполнитель: Claude Code / Sonnet  
Master SPEC: `../../../career/CAREER_OPERATING_SYSTEM_V1_SPEC.md`, Slice D1a

## Подтверждённая предпосылка

D0 принят 2026-07-27:

- migration `019` и cover feature flag уже live;
- 165 focused tests зелёные на отдельной PostgreSQL;
- owner реально использовал draft/approve/reject;
- application создаётся только отдельным `Отклик отправлен`.

Не повторять D0 и не менять live dev state в этой задаче.

## Цель

Добавить минимальный service/storage contract, который доказывает, какой exact пакет
был подготовлен и затем связан с owner-confirmed application event.

D1a не меняет Telegram UX. Он создаёт доменное основание для отдельного D1b.

## Перед кодом

1. Прочитать `AGENTS.md`, `CLAUDE.md`,
   `!DOC/operations/CURRENT_PRODUCT_STATE.md`.
2. Прочитать master SPEC: ownership, state machine, application package, metrics,
   Slice D1a, acceptance, non-goals.
3. Прочитать существующие Cockpit и Cover task/spec только в затрагиваемых контрактах.
4. Выполнить точечный Graphify query по:
   - career inbox version/content hash;
   - cover draft immutable lifecycle и grounding report;
   - career application/event creation;
   - текущему `Отклик отправлен`;
   - migration/model/service tests.
5. Сверить каждый найденный symbol с актуальным кодом и показать компактный reuse
   verdict:

| Вариант | Проверить |
|---|---|
| Расширить cover draft snapshot | сохраняет ли exact vacancy/CV/gates и не ломает immutable lifecycle |
| Сохранить package snapshot в application event payload | можно ли создать ready package до application |
| Новая package table | нужна только если первые два варианта не выполняют инварианты |

Выбрать самый простой вариант. Если новая таблица выводит diff за ориентир 400 строк,
остановиться с предложением D1a.1/D1a.2, а не расширять scope.

## Минимальный контракт package

Package kind в D1a: только `application`.

Outreach package, manual cover text и отправка внешнего сообщения отложены.

Snapshot содержит:

- owner id;
- inbox item id;
- immutable vacancy/source/content hash;
- company, role и source URL;
- final gates snapshot и его deterministic hash/policy reference;
- approved cover draft id, version/text hash и использованные `fact_id`;
- `facts_bank_hash`;
- выбранный `cv_variant_id` и `cv_content_hash`;
- package content hash;
- status `ready | submitted | expired`;
- created/ready/submitted timestamps;
- linked application/event id после `submitted`.

`cv_variant_id` выбирается только из существующего facts-bank/CV mapping. Не строить
новый matcher и не переписывать CV.

`policy_ref` должен использовать уже импортированную версию/final gates, если она
достаточна. Не добавлять runtime sibling-read `PERSONAL_STRATEGY.md` без доказанного
отсутствия применённой policy version.

## Инварианты

1. `ready` возможен только для текущей immutable версии inbox item.
2. Cover draft должен быть `owner_approved` и принадлежать тому же owner/inbox item.
3. CV variant обязан существовать; сохраняется content hash.
4. Package hash вычисляется из canonical serialization всех полей snapshot.
5. Повторный prepare тех же входов возвращает тот же package или idempotent duplicate,
   но не создаёт новую смысловую версию.
6. Любое изменение vacancy hash, approved cover version, CV hash, gates или facts bank
   делает старый ready package `expired` либо блокирует submit как stale.
7. `submitted` требует package id + ожидаемый package hash.
8. Повторный submitted replay не создаёт второй application/event.
9. Package не отправляет данные наружу и не вызывает Telegram/network provider.
10. LLM output не участвует в authority после owner-approved cover draft.

## Разрешённые изменения

- существующие career models/services;
- новый узкий service только если текущий service нарушил бы ownership;
- следующая migration только при доказанной необходимости;
- focused service/PostgreSQL tests;
- краткое обновление `CURRENT_PRODUCT_STATE.md` только после зелёной реализации.

Не применять новую migration к dev и не включать новый feature flag.

## Acceptance

Focused tests доказывают:

- ready package строится из валидного inbox + owner-approved draft + CV;
- чужой owner/inbox/draft блокируется;
- unapproved/rejected draft блокируется;
- missing CV/facts/gates block или fail closed;
- deterministic hash стабилен;
- changed vacancy/cover/CV/facts/gates блокирует stale submit;
- expected hash обязателен;
- submitted создаёт и связывает ровно один existing career application/event;
- replay идемпотентен;
- skip/outreach/false-positive item не становится application package;
- provider/network calls отсутствуют.

Запустить минимум существующие career inbox, cover draft, ledger и новые package tests
на отдельной PostgreSQL. Dev DB не изменять.

## Non-goals

- Telegram `Готовые` и callbacks;
- background refresh/scheduler;
- recruiter feedback/next action;
- MCP changes;
- outreach package;
- manual cover editor;
- автоматический выбор новой версии CV;
- изменение facts bank или root strategy;
- connector, browser automation или submit.

## Stop and report

Остановиться после D1a. Вернуть:

1. Graphify query и проверенные symbols;
2. reuse verdict из трёх вариантов;
3. diff summary и объяснение новой migration, если она появилась;
4. точные test commands/results;
5. доказательство hash/stale/idempotency;
6. известные ограничения;
7. явный verdict `D1a PASS` или `D1a BLOCKED`.

Не начинать D1b.
