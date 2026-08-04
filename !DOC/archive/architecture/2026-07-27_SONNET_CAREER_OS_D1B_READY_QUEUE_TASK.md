# Sonnet task: Career OS D1b ready queue

Статус: superseded by bounded split - D1b.1 PASS, D1b.2 separate  
Владелец внешних действий и live rollout: Эрнис  
Исполнитель: Claude Code / Sonnet  
Master SPEC: `../../../career/CAREER_OPERATING_SYSTEM_V1_SPEC.md`, Slice D1b

## Подтверждённая предпосылка

D1a принят 2026-07-27:

- `career_application_packages` обоснована отдельным pre-application lifecycle;
- migration `020` применена только к test DB, не к dev;
- package service уже владеет prepare, expected hash, stale checks, idempotent submit
  и связью с application/event;
- 179 focused tests зелёные.

Не повторять package authority в Telegram и не менять D1a state machine.

## Пользовательский результат

Эрнис после одобрения cover draft может:

1. выбрать один существующий CV variant;
2. получить immutable ready package;
3. открыть bounded preview из меню `Готовые`;
4. увидеть company, role, CV, cover, gates/questions и short package hash;
5. нажать `Отправлено`;
6. на отдельном confirmation screen проверить company/role/hash;
7. подтвердить создание ровно одной application/event.

`Отправлено` в D1b ничего не отправляет во внешнюю систему. Это подтверждение уже
совершённого Эрнисом действия.

## Simplicity budget

До кода:

1. Прочитать `AGENTS.md`, `CLAUDE.md`,
   `!DOC/operations/CURRENT_PRODUCT_STATE.md`.
2. Прочитать master SPEC только в частях ownership, package, Telegram UX, Slice D1b,
   acceptance и non-goals.
3. Сделать точечный Graphify query по текущим career menu/callbacks, approved cover
   screen, package service и bot tests. Граф не перестраивать без отдельного основания;
   symbols сверить с актуальным кодом.
4. Показать краткий план reuse и оценку строк:
   - существующий menu/markup/callback pattern;
   - существующий cover preview/copy path;
   - существующий owner/compact-id/stale-callback pattern;
   - единственный недостающий package query, если он действительно отсутствует.

Жёсткие правила:

- общий diff D1b <=400 строк, включая tests и docs;
- production diff целевой <=250 строк;
- если оценка выше, остановиться до кода и предложить D1b.1/D1b.2;
- не создавать framework, base class, registry, generic workflow или shared package;
- не рефакторить файл только из-за размера;
- не добавлять второй formatter/state store/pending mechanism, если текущий паттерн
  покрывает flow.

## Разрешённый service scope

Допустим один bounded owner-only query, если его нет:

```text
list_ready_application_packages(owner_id, limit <= 7)
```

Требования:

- только `status=ready`;
- newest first;
- owner isolation;
- limit 1..7;
- возвращает существующую модель package;
- не вычисляет новый score, matcher или strategy;
- не делает provider/network calls.

Другие изменения package authority запрещены. Если UX вскрывает дефект D1a, остановить
задачу и вернуть corrective evidence.

## Telegram flow

### 1. Создание package

- Кнопка появляется только после `owner_approved` cover draft.
- Текст: `Собрать пакет`.
- Бот показывает только CV variants из существующего `facts_bank.yaml -> role_types`.
- Не строить новый matcher. Если текущий draft не даёт однозначной рекомендации,
  показать владельцу bounded список существующих вариантов, максимум 3.
- Callback содержит compact ids, а не filename, text, URL или hash целиком.
- После выбора CV вызвать существующий `prepare_application_package`.
- Повторный callback идемпотентен и возвращает тот же package.

### 2. Меню `Готовые`

- За отдельным feature flag default `False`.
- Не более 7 ready packages.
- Карточка показывает:
  - company и role;
  - CV variant;
  - final gate summary;
  - не более двух recruiter questions;
  - source URL существующим безопасным способом;
  - approved cover preview/copy path;
  - первые 10-12 символов package hash;
  - номер карточки.
- Не загружать полный raw vacancy text.

### 3. Owner sent-confirmation

- `Отправлено` сначала показывает отдельный confirmation:
  `company / role / short package hash`.
- Кнопки `Подтвердить` и `Отмена`.
- Confirm передаёт в service package id, полный expected hash из canonical DB state и
  idempotency key из существующего Telegram update/callback pattern.
- Success показывает application id/status и убирает package из `Готовые`.
- Cancel ничего не пишет.
- Stale/expired/hash mismatch/replayed callback завершаются понятным fail-closed
  сообщением и не создают новую application.

## Разрешённые файлы

- существующий Telegram career adapter либо уже принятый локальный focused-модуль, если
  такой паттерн реально есть в репозитории;
- `app/core/config.py` только для одного feature flag;
- package service только для bounded list query;
- focused bot/service tests;
- краткое обновление `CURRENT_PRODUCT_STATE.md` после зелёных tests.

Новая migration, model и schema запрещены.

## Acceptance tests

Минимум доказать:

1. Feature flag off скрывает `Готовые` и package actions.
2. Package action отсутствует у draft/rejected cover.
3. Owner-approved cover предлагает только разрешённые CV variants.
4. Package prepare получает exact owner/inbox/draft/CV.
5. Повтор CV callback не создаёт duplicate package.
6. Ready list owner-only, newest-first и bounded <=7.
7. Preview содержит company/role/CV/gates/questions/short hash без raw vacancy text.
8. `Отправлено` не вызывает submit до отдельного confirmation.
9. Cancel не меняет package/application.
10. Confirm передаёт expected hash и создаёт одну application/event.
11. Confirm replay не создаёт вторую application.
12. Stale/expired/hash mismatch не создают application.
13. Чужой package и stale callback fail-closed.
14. Provider/network/external send path отсутствует.

Запустить существующие inbox, cover, ledger, package и новые bot tests на отдельной
PostgreSQL с migration `020`. Dev DB, `.env`, live bot и polling не менять.

## Non-goals

- применение migration `020` к dev;
- live feature enable/smoke;
- изменение package schema/authority;
- outreach package;
- ручной редактор CV/cover;
- recruiter feedback/next action;
- MCP;
- background refresh/scheduler;
- connector или реальный submit;
- shared library с EGE Mentor;
- рефакторинг `career_inbox_service.py`;
- новый bot/provider/framework.

## Stop and report

Остановиться после tests. Вернуть:

1. Graphify query, symbols и актуальная проверка кода;
2. reuse plan и фактический diff против бюджета;
3. изменённые файлы;
4. точные test commands/results;
5. доказательство double-confirmation, expected hash, stale и replay;
6. known limitations;
7. verdict `D1b PASS` или `D1b BLOCKED`.

Не применять migration к dev и не начинать live rollout, D2, D3 или D4.
