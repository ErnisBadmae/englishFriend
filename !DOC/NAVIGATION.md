# NAVIGATION

Карта документации и правил навигации. Агенты и люди — читают только нужное, экономя токены.

## Токен-правило №1

Читай файлы последовательно, не все сразу. Каждый файл — ~200-300 строк. Если задача не требует деталей, прочитай index → ссылку → конкретный раздел.

## Быстрый вход

| Если тебе нужно... | Читай | Строк |
|---|---|---|
| Понять, что делает система | `!DOC/README.md` | — |
| Понять архитектуру | `!DOC/ARCHITECTURE.md` | — |
| Найти текущее состояние | `!DOC/operations/CURRENT_PRODUCT_STATE.md` | — |
| Найти текущую задачу | `!DOC/operations/SESSION_LOG.md` | — |
| Прочитать стратегию | `!DOC/strategy/` | — |

## Структура каталогов

```
englishFriend/
  README.md              ← Корневой README (читай первым)
  main.py                ← Точка входа

  !DOC/
    README.md            ← Твой индекс (читай первым)
    ARCHITECTURE.md      ← Active architecture
    GLOSSARY.md          ← Словарь терминов

    operations/          ← Runbooks, журналы, текущее состояние
      CURRENT_PRODUCT_STATE.md ← Source of truth для продукта
      SESSION_LOG.md     ← Журнал сессий (последние 10 записей)
      *_RUNBOOK.md       ← Запусковые инструкции
      archive/           ← Завершённые задачи, расследования, архив сессий

    architecture/        ← Подсистемы (каждый файл — отдельный контекст)
    strategy/            ← Стратегия, roadmap, метрики
    research/            ← Исследования
    implementations/     ← Планы реализации
```

## Кто кому ссылается

```
!DOC/README.md
  ├── !DOC/ARCHITECTURE.md (как устроено)
  ├── !DOC/operations/CURRENT_PRODUCT_STATE.md (что сейчас)
  ├── !DOC/operations/SESSION_LOG.md (последние решения)
  └── !DOC/strategy/ROADMAP.md (куда движемся)

!DOC/ARCHITECTURE.md
  ├── !DOC/GLOSSARY.md (терминология)
  ├── !DOC/architecture/* (детали подсистем)
  └── !DOC/operations/* (runbooks, rollout)

!DOC/operations/CURRENT_PRODUCT_STATE.md
  └── !DOC/strategy/* (стратегические ссылки)
```

## Чего читать НЕ надо (если не нужна глубина)

Эти файлы — исторический контекст. Читай только если:
- нужен полный обзор — `!DOC/strategy/ROADMAP.md`, `!DOC/research/deep-research-report.md`
- разбираешься в архитектуре — `!DOC/architecture/*`

Не читай заранее:
- `!DOC/archive/` — всё завершённое, проверенное, не активное
- `graphify-out/` — автогенерация
- `!DOC/operations/*_RUNBOOK.md` — только при выполнении конкретных задач

## Как экономить токены

1. **Начинай с `!DOC/README.md`** — читай первым, даёт полную карту.
2. **Читай по ссылке** — `!DOC/README.md` → `!DOC/ARCHITECTURE.md` → конкретный файл из `architecture/`.
3. **Session-логи** — `SESSION_LOG.md` содержит последние 10 записей. Архивные недели — в `operations/archive/SESSION_LOG_*.md`.
4. **CURRENT_PRODUCT_STATE.md** — даёт текущее состояние. Не читай `archive/`, если не нужна конкретная дата.
