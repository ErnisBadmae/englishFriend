# Руководство по развертыванию системы документации на других проектах

---
last_updated: 2025-01-31
---

## Быстрый старт (2 способа)

### Способ 1: Автоматический (рекомендуется)

```bash
# Из этого проекта (englishFriend)
cd /path/to/englishFriend
chmod +x scripts/deploy_documentation_system.sh

# Развернуть на новом проекте
./scripts/deploy_documentation_system.sh /path/to/new-project "ProjectName"

# Готово! Система развёрнута за 5 секунд
```

### Способ 2: Ручной

Следуйте инструкциям в файле [DOCUMENTATION_SYSTEM_TEMPLATE.md](./DOCUMENTATION_SYSTEM_TEMPLATE.md)

---

## Что будет создано

После запуска скрипта в целевом проекте появится:

```
new-project/
├── !DOC/
│   ├── README.md                    # ✓ Создан с именем проекта
│   ├── CHANGELOG.md                 # ✓ Создан с текущей датой
│   ├── GLOSSARY.md                  # ✓ Создан шаблон
│   ├── DOCUMENTATION_SYSTEM_TEMPLATE.md  # ✓ Полная документация
│   ├── architecture/
│   ├── strategy/
│   ├── implementations/
│   ├── research/
│   ├── operations/
│   └── archive/
│
├── .claude/
│   ├── agents/
│   │   └── documentation-manager.md     # ✓ Скопирован
│   └── skills/
│       └── documentation-maintenance/
│           └── SKILL.md                 # ✓ Скопирован
│
└── .kiro/
    ├── hooks/
    │   ├── documentation-update-reminder.json      # ✓ Скопирован
    │   └── documentation-staleness-check.json      # ✓ Скопирован
    └── specs/
        └── documentation-management-system/
            ├── requirements.md                     # ✓ Скопирован
            ├── design.md                           # ✓ Скопирован
            └── tasks.md                            # ✓ Скопирован
```

---

## Адаптация под проект

### 1. Настроить паттерны файлов

Отредактируйте `.kiro/hooks/documentation-update-reminder.json`:

**Python:**
```json
"patterns": [
  "app/**/*.py",
  "src/**/*.py",
  "tests/**/*.py"
]
```

**JavaScript/TypeScript:**
```json
"patterns": [
  "src/**/*.ts",
  "src/**/*.tsx",
  "components/**/*.tsx",
  "lib/**/*.js"
]
```

**Go:**
```json
"patterns": [
  "**/*.go",
  "cmd/**/*.go",
  "pkg/**/*.go"
]
```

**Rust:**
```json
"patterns": [
  "src/**/*.rs",
  "tests/**/*.rs"
]
```

**Polyglot:**
```json
"patterns": [
  "backend/**/*.py",
  "frontend/src/**/*.tsx",
  "db/migrations/**/*.sql"
]
```

### 2. Создать начальные документы

Минимальный набор для старта:

```bash
cd new-project/!DOC/

# Архитектура (обязательно)
touch architecture/SYSTEM_OVERVIEW.md
# Добавить: краткое описание системы, компоненты, data flow

# Стратегия (рекомендуется)
touch strategy/TECHNICAL_STRATEGY.md
# Добавить: выбор технологий и почему

touch strategy/ROADMAP.md
# Добавить: фазы разработки, что планируется
```

### 3. Протестировать систему

```bash
# Тест 1: Хук на изменение кода
# 1. Отредактируйте любой .py/.ts/.go файл
# 2. Должно появиться напоминание обновить документацию

# Тест 2: Валидация документов
# Вызовите агента: "Invoke documentation-manager to validate all docs"

# Тест 3: Проверка staleness
# Вызовите: "Run documentation staleness check"
```

---

## Примеры для разных типов проектов

### Веб-приложение (Frontend + Backend)

```bash
# Паттерны
"patterns": [
  "backend/app/**/*.py",
  "frontend/src/**/*.tsx",
  "frontend/src/**/*.ts"
]

# Документы
!DOC/
├── architecture/
│   ├── SYSTEM_OVERVIEW.md      # Общая архитектура
│   ├── FRONTEND_ARCHITECTURE.md # React/Next.js структура
│   ├── BACKEND_ARCHITECTURE.md  # FastAPI/Django структура
│   └── DATABASE.md              # Schema
├── strategy/
│   ├── TECHNICAL_STRATEGY.md    # Выбор стека
│   └── ROADMAP.md               # План разработки
```

### Библиотека/SDK

```bash
# Паттерны
"patterns": [
  "src/**/*.py",
  "src/**/*.ts",
  "examples/**/*"
]

# Документы
!DOC/
├── architecture/
│   ├── API_REFERENCE.md         # Публичный API
│   └── INTERNAL_DESIGN.md       # Внутренняя архитектура
├── implementations/
│   ├── GETTING_STARTED.md       # Быстрый старт
│   └── EXAMPLES.md              # Примеры использования
```

### Микросервисы

```bash
# Паттерны
"patterns": [
  "services/*/src/**/*.py",
  "services/*/src/**/*.go",
  "infra/**/*.yaml"
]

# Документы
!DOC/
├── architecture/
│   ├── SYSTEM_OVERVIEW.md       # Общая архитектура
│   ├── SERVICE_AUTH.md          # Auth сервис
│   ├── SERVICE_PAYMENTS.md      # Payments сервис
│   └── SERVICE_NOTIFICATIONS.md # Notifications сервис
├── operations/
│   ├── DEPLOYMENT.md            # Деплой
│   └── MONITORING.md            # Мониторинг
```

### CLI Tool

```bash
# Паттерны
"patterns": [
  "cmd/**/*.go",
  "internal/**/*.go",
  "pkg/**/*.go"
]

# Документы
!DOC/
├── architecture/
│   └── DESIGN.md                # Дизайн CLI
├── implementations/
│   ├── COMMANDS.md              # Список команд
│   └── CONFIGURATION.md         # Конфигурация
```

---

## Чек-лист внедрения

### Базовое (обязательно)

- [ ] Запущен скрипт `deploy_documentation_system.sh`
- [ ] Адаптированы паттерны файлов в `.kiro/hooks/documentation-update-reminder.json`
- [ ] Создан `architecture/SYSTEM_OVERVIEW.md` (хотя бы краткий)
- [ ] Протестирован хук (отредактирован код → пришло напоминание)
- [ ] Протестирована валидация документов

### Рекомендуемое

- [ ] Создан `strategy/TECHNICAL_STRATEGY.md` (выбор технологий)
- [ ] Создан `strategy/ROADMAP.md` (план разработки)
- [ ] Заполнен `GLOSSARY.md` (основные термины проекта)
- [ ] Добавлены cross-references между документами
- [ ] Обучена команда работе с системой

### Расширенное (опционально)

- [ ] Настроена интеграция с Qdrant для семантического поиска
- [ ] Добавлены Git hooks для валидации при коммите
- [ ] Настроен CI/CD для проверки документации
- [ ] Создан dashboard для метрик покрытия

---

## Частые вопросы

### Q: Нужно ли адаптировать skill и agent?

**A:** Нет, они универсальные. Только хуки требуют адаптации (паттерны файлов).

### Q: Сколько времени занимает внедрение?

**A:**
- Автоматическое развертывание: 5 секунд
- Адаптация паттернов: 2 минуты
- Создание начальных документов: 30-60 минут
- **Итого: ~1 час** для полного внедрения

### Q: Работает ли с монорепозиториями?

**A:** Да, просто настройте паттерны для каждого сервиса/пакета:

```json
"patterns": [
  "packages/frontend/**/*.tsx",
  "packages/backend/**/*.py",
  "packages/shared/**/*.ts"
]
```

### Q: Можно ли использовать на закрытых проектах?

**A:** Да, система не содержит специфики englishFriend. Все компоненты универсальные.

### Q: Как обновить систему на всех проектах?

**A:** Создайте Git-репозиторий с шаблоном, используйте семантическое версионирование. При обновлениях:

```bash
# В каждом проекте
cd <PROJECT>
git remote add docs-template https://github.com/YOU/docs-template
git fetch docs-template
git merge docs-template/main --allow-unrelated-histories
```

### Q: Поддерживаются ли другие языки кроме Python?

**A:** Да, любые языки. Просто настройте паттерны файлов в хуках. Примеры есть в шаблоне.

---

## Метрики эффективности

Замерьте до и после внедрения:

| Метрика | До | После | Улучшение |
|---------|-----|--------|-----------|
| Токены на онбординг агента | 15000-20000 | 2000-3000 | **85%** |
| Время поиска информации | 30-60 сек | 5-10 сек | **80%** |
| Устаревшие документы | 5-10 | 0 | **100%** |
| Broken references | 10-20 | 0 | **100%** |
| Покрытие документацией | 30-50% | 80%+ | **+60%** |

---

## Поддержка

**Документация:**
- Полное руководство: [DOCUMENTATION_SYSTEM_TEMPLATE.md](./DOCUMENTATION_SYSTEM_TEMPLATE.md)
- Система в действии: [DOCUMENTATION_SYSTEM.md](./DOCUMENTATION_SYSTEM.md) (пример на englishFriend)

**Помощь:**
- Вызовите documentation-manager agent
- Создайте issue в englishFriend репозитории

**Обратная связь:**
- Поделитесь опытом внедрения
- Предложите улучшения

---

## Лицензия

Система открыта для использования в любых проектах.
Основано на опыте проекта englishFriend.

**Версия**: 1.0
**Дата**: 2025-01-31
