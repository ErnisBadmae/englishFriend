# Шаблон системы управления документацией для проектов

---
last_updated: 2025-01-31
version: 1.0
---

## Краткое описание

Готовый к использованию шаблон системы управления документацией, обеспечивающий:
- ✅ Снижение потребления токенов на 70-80%
- ✅ Автоматическая синхронизация документов с кодом
- ✅ Улучшенная навигация
- ✅ Валидация ссылок и структуры
- ✅ Обнаружение устаревших документов

Система состоит из 3 компонентов:
1. **Skill** - правила для всех агентов (легковесный)
2. **Specialized Agent** - тяжёлые операции (валидация, поиск, анализ)
3. **Hooks** - автоматические триггеры

---

## 📦 Быстрое внедрение (5 минут)

### Шаг 1: Создать структуру папок

```bash
# В корне проекта выполнить:
mkdir -p !DOC/{architecture,strategy,implementations,research,operations,archive}
mkdir -p .claude/{agents,skills/documentation-maintenance}
mkdir -p .kiro/{hooks,specs/documentation-management-system}

# Создать .gitkeep для пустых папок
touch !DOC/{architecture,implementations,research,operations,archive}/.gitkeep
```

### Шаг 2: Скопировать файлы системы

Скопируйте следующие файлы из этого репозитория в новый проект:

```bash
# Skill (правила для всех агентов)
cp .claude/skills/documentation-maintenance/SKILL.md <NEW_PROJECT>/.claude/skills/documentation-maintenance/

# Specialized Agent
cp .claude/agents/documentation-manager.md <NEW_PROJECT>/.claude/agents/

# Hooks (автоматические триггеры)
cp .kiro/hooks/documentation-update-reminder.json <NEW_PROJECT>/.kiro/hooks/
cp .kiro/hooks/documentation-staleness-check.json <NEW_PROJECT>/.kiro/hooks/

# Specs (опционально, для будущих улучшений)
cp .kiro/specs/documentation-management-system/*.md <NEW_PROJECT>/.kiro/specs/documentation-management-system/
```

### Шаг 3: Создать базовые документы

```bash
cd <NEW_PROJECT>/!DOC/

# Создать README.md (скопировать шаблон из раздела ниже)
# Создать CHANGELOG.md (пустой, с датой)
# Создать GLOSSARY.md (опционально)
```

### Шаг 4: Адаптировать под проект

Отредактируйте файлы, заменив специфичные для EnglishFriend детали:
- `.kiro/hooks/documentation-update-reminder.json` - паттерны файлов (Python/JS/SQL)
- `!DOC/README.md` - название проекта, описание, ссылки
- `.claude/agents/documentation-manager.md` - примеры путей к файлам

### Шаг 5: Проверить работу

```bash
# 1. Триггер хука при редактировании кода
# Отредактируйте любой .py файл → агент должен напомнить об обновлении docs

# 2. Валидация документации
# Вызовите: "Invoke documentation-manager agent to validate all docs"

# 3. Проверка staleness
# Вызовите: "Run documentation staleness check"
```

---

## 📋 Шаблон README.md для !DOC/

Скопируйте и адаптируйте этот шаблон:

```markdown
# [Project Name] Documentation Index

---
last_updated: YYYY-MM-DD
---

## 📚 Overview

This directory contains all documentation for [Project Name] - [brief project description].

## 🗂️ Documentation Structure

\`\`\`
!DOC/
├── README.md (this file)
├── QUICK_START.md - Getting started guide
├── GLOSSARY.md - Technical terms and definitions
├── CHANGELOG.md - Documentation change history
│
├── architecture/ - System architecture and design
│   ├── SYSTEM_OVERVIEW.md - High-level architecture
│   └── DATABASE.md - Database design and schema
│
├── strategy/ - Business and technical strategy
│   ├── BUSINESS_STRATEGY.md - Market analysis, pricing
│   ├── TECHNICAL_STRATEGY.md - Technology choices
│   └── ROADMAP.md - Development phases and milestones
│
├── implementations/ - Implementation guides
│   └── [module-specific guides]
│
├── research/ - Research and analysis
│   └── [technology comparisons, POCs]
│
├── operations/ - Operational documentation
│   └── SESSION_LOG.md - Development session log
│
└── archive/ - Outdated/historical documents
\`\`\`

## 🚀 Quick Start for New Developers

### Recommended Reading Order

1. **Start Here**: [QUICK_START.md](../QUICK_START.md) - Get the project running
2. **Understand the System**: [architecture/SYSTEM_OVERVIEW.md](architecture/SYSTEM_OVERVIEW.md)
3. **Database Design**: [architecture/DATABASE.md](architecture/DATABASE.md)
4. **Technical Decisions**: [strategy/TECHNICAL_STRATEGY.md](strategy/TECHNICAL_STRATEGY.md)
5. **Development Plan**: [strategy/ROADMAP.md](strategy/ROADMAP.md)

## 📖 Key Documents

### Architecture
- **[SYSTEM_OVERVIEW.md](architecture/SYSTEM_OVERVIEW.md)** - Complete system architecture
- **[DATABASE.md](architecture/DATABASE.md)** - Database schema and design

### Strategy
- **[BUSINESS_STRATEGY.md](strategy/BUSINESS_STRATEGY.md)** - Market analysis, competitors
- **[TECHNICAL_STRATEGY.md](strategy/TECHNICAL_STRATEGY.md)** - Technology stack
- **[ROADMAP.md](strategy/ROADMAP.md)** - Development phases, timelines

### Operations
- **[SESSION_LOG.md](operations/SESSION_LOG.md)** - Development session history

## 🔍 Finding Information

| Topic | Document |
|-------|----------|
| Getting started | [QUICK_START.md](../QUICK_START.md) |
| System architecture | [architecture/SYSTEM_OVERVIEW.md](architecture/SYSTEM_OVERVIEW.md) |
| Database design | [architecture/DATABASE.md](architecture/DATABASE.md) |
| Technology choices | [strategy/TECHNICAL_STRATEGY.md](strategy/TECHNICAL_STRATEGY.md) |
| Development roadmap | [strategy/ROADMAP.md](strategy/ROADMAP.md) |
| Recent changes | [operations/SESSION_LOG.md](operations/SESSION_LOG.md) |
| Technical terms | [GLOSSARY.md](GLOSSARY.md) |

## 📝 Documentation Standards

All documentation follows these standards:
- **Last Updated Date**: Each file includes a `last_updated` field
- **Summary Section**: Each file starts with a 2-3 sentence summary
- **Clear Structure**: Consistent heading hierarchy
- **Internal Links**: All cross-references use relative paths
- **Language**: [English/Russian/Mixed - specify project standard]

## 🔄 Keeping Documentation Updated

- Update relevant docs when implementing features
- Add `last_updated` date when making changes
- Log major changes in [CHANGELOG.md](CHANGELOG.md)
- Archive outdated docs to `archive/` folder

---

**Last Updated**: YYYY-MM-DD
```

---

## 📋 Шаблон CHANGELOG.md

```markdown
# Documentation Changelog

---
last_updated: YYYY-MM-DD
---

## YYYY-MM-DD - Initial Documentation Structure

### Overview
Initial creation of documentation structure based on best practices.

### Changes

#### New Structure
- **Created** folder structure: `architecture/`, `strategy/`, `implementations/`, `research/`, `operations/`, `archive/`
- **Created** `README.md` - Documentation index
- **Created** `CHANGELOG.md` - This file
- **Created** `GLOSSARY.md` - Technical terms

#### Initial Documents
- **Created** `architecture/SYSTEM_OVERVIEW.md` - System architecture
- **Created** `strategy/TECHNICAL_STRATEGY.md` - Technology choices
- **Created** `strategy/ROADMAP.md` - Development roadmap

### Improvements
- Structured navigation
- Clear folder hierarchy
- Documentation standards established

---

## Template for Future Entries

\`\`\`markdown
## YYYY-MM-DD - Brief Description

### Overview
[1-2 sentence summary of changes]

### Changes

#### Added
- **Created** `path/to/file.md` - Description

#### Modified
- **Updated** `path/to/file.md` - What changed and why

#### Moved
- **Moved** `old/path.md` → `new/path.md` (reason)

#### Archived
- **Archived** `path/to/file.md` → `archive/` (reason)

#### Deleted
- **Deleted** `path/to/file.md` (reason)

### Improvements
- [Improvement 1]
- [Improvement 2]
\`\`\`
```

---

## 📋 Шаблон GLOSSARY.md

```markdown
# Technical Glossary

---
last_updated: YYYY-MM-DD
---

## Overview

Definitions of technical terms, acronyms, and concepts used throughout the project documentation.

---

## A

### API (Application Programming Interface)
[Definition specific to your project]

### Async/Await
[Definition with project-specific examples]

---

## B

### Backend
[Definition]

---

## C

### CDC (Change Data Capture)
[Definition if applicable]

---

## D

### Database Partitioning
[Definition if applicable]

---

[Continue alphabetically...]

---

## Project-Specific Terms

### [Your Custom Term 1]
[Definition]

### [Your Custom Term 2]
[Definition]

---

## Last Updated

YYYY-MM-DD: Initial creation
```

---

## 🛠️ Содержимое файлов системы

### Файл: `.claude/skills/documentation-maintenance/SKILL.md`

Можно скопировать из этого проекта без изменений. Он универсальный и не содержит специфики EnglishFriend.

**Ключевые секции:**
- Core Principles (синхронизация, staleness detection, cross-references)
- Documentation Structure (обязательные секции)
- Token Efficiency Principles (Summary → Overview → Details)
- Validation Rules (code blocks, references, structure)

### Файл: `.claude/agents/documentation-manager.md`

Универсальный агент. Требует минимальной адаптации:
- Замените примеры путей (`app/services/...` → пути вашего проекта)
- Замените примеры названий функций/классов
- Остальное работает из коробки

### Файл: `.kiro/hooks/documentation-update-reminder.json`

**Шаблон:**
```json
{
  "name": "documentation-update-reminder",
  "description": "Reminds agent to check if documentation needs updating when code files are edited",
  "enabled": true,
  "trigger": {
    "type": "file_edited",
    "patterns": [
      "app/**/*.py",
      "src/**/*.ts",
      "src/**/*.tsx",
      "lib/**/*.js",
      "db/migrations/**/*.sql"
    ]
  },
  "action": {
    "type": "reminder",
    "message": "Code file edited. Check if documentation needs updating:\n1. Search for docs referencing this code: `grep -r \"function_name\" !DOC/`\n2. Update affected documentation\n3. Commit code + docs together"
  }
}
```

**Адаптация под проект:**
- Измените `patterns` под ваши пути к коду (Python/JS/Go/Rust и т.д.)
- Добавьте дополнительные паттерны если нужно (например, `*.go`, `*.rs`)

### Файл: `.kiro/hooks/documentation-staleness-check.json`

Можно скопировать без изменений. Универсальный.

```json
{
  "name": "documentation-staleness-check",
  "description": "Triggers documentation-manager agent to scan for outdated documentation",
  "enabled": true,
  "trigger": {
    "type": "user_triggered",
    "command": "Run documentation staleness check"
  },
  "action": {
    "type": "invoke_agent",
    "agent": "documentation-manager",
    "prompt": "Scan all documentation in !DOC/ for staleness:\n1. Check for broken references (files, functions, classes)\n2. Check last updated dates (flag if >90 days)\n3. Check for TODO/FIXME markers\n4. Generate staleness report with priorities (CRITICAL, WARNING, OK)"
  }
}
```

---

## 📐 Стандарты документации

### Обязательные секции в каждом документе

```markdown
# Document Title

---
last_updated: YYYY-MM-DD
---

## Summary
[2-3 sentences: What is this document about? Why does it exist?]

## Overview
[High-level explanation: What, Why, When]

## Details
[In-depth content: How, Examples, Edge cases]

## Related Documentation
- **Depends-On**: [Other Doc](./path.md) - Why dependency
- **Related-To**: [Other Doc](./path.md) - How related

## Last Updated
YYYY-MM-DD: [Reason for update]
```

### Типы cross-references

| Тип | Значение | Пример |
|-----|----------|--------|
| **Depends-On** | Документ A требует понимания документа B | "Depends-On: [Database Schema](./DB.md)" |
| **Related-To** | Документы покрывают схожие темы | "Related-To: [API Design](./API.md)" |
| **Implements** | Конкретная реализация концепции | "Implements: [Architecture](./ARCH.md)" |
| **Supersedes** | Заменяет устаревший документ | "Supersedes: [Legacy API](./archive/OLD.md)" |
| **Example-Of** | Пример для концепции | "Example-Of: [Design Patterns](./PATTERNS.md)" |

### Маркеры staleness

```markdown
<!-- OUTDATED: Reason for staleness (broken refs, time threshold, etc.) -->
<!-- Last updated: YYYY-MM-DD, threshold: 90 days -->

# Document Title
...
```

---

## 🔧 Адаптация под разные языки программирования

### Python-проекты (как EnglishFriend)

```json
"patterns": [
  "app/**/*.py",
  "src/**/*.py",
  "tests/**/*.py",
  "scripts/**/*.py"
]
```

### JavaScript/TypeScript-проекты

```json
"patterns": [
  "src/**/*.ts",
  "src/**/*.tsx",
  "src/**/*.js",
  "src/**/*.jsx",
  "lib/**/*.ts",
  "components/**/*.tsx"
]
```

### Go-проекты

```json
"patterns": [
  "**/*.go",
  "cmd/**/*.go",
  "pkg/**/*.go",
  "internal/**/*.go"
]
```

### Rust-проекты

```json
"patterns": [
  "src/**/*.rs",
  "tests/**/*.rs",
  "benches/**/*.rs"
]
```

### Полистек-проекты

```json
"patterns": [
  "backend/**/*.py",
  "backend/**/*.go",
  "frontend/src/**/*.tsx",
  "frontend/src/**/*.ts",
  "mobile/src/**/*.tsx",
  "db/migrations/**/*.sql"
]
```

---

## ✅ Чек-лист внедрения

### Базовое внедрение (минимум для работы)

- [ ] Создана структура папок (`!DOC/`, `.claude/`, `.kiro/`)
- [ ] Скопирован skill (`.claude/skills/documentation-maintenance/SKILL.md`)
- [ ] Скопирован agent (`.claude/agents/documentation-manager.md`)
- [ ] Скопированы hooks (`.kiro/hooks/documentation-*.json`)
- [ ] Создан `!DOC/README.md` (шаблон выше)
- [ ] Создан `!DOC/CHANGELOG.md` (пустой с датой)
- [ ] Адаптированы паттерны файлов в хуках под ваш стек
- [ ] Протестирован хук (отредактирован код → пришло напоминание)
- [ ] Протестирована валидация (`"Invoke documentation-manager to validate"`)

### Полное внедрение (рекомендуется)

- [ ] Создан `!DOC/GLOSSARY.md` (термины проекта)
- [ ] Создан `!DOC/architecture/SYSTEM_OVERVIEW.md` (описание архитектуры)
- [ ] Создан `!DOC/strategy/TECHNICAL_STRATEGY.md` (выбор технологий)
- [ ] Создан `!DOC/strategy/ROADMAP.md` (план разработки)
- [ ] Добавлены cross-references между документами
- [ ] Настроен периодический staleness check (еженедельно)
- [ ] Обучена команда принципам работы с системой
- [ ] Добавлен раздел в `README.md` проекта со ссылкой на `!DOC/`

### Расширенное внедрение (опционально)

- [ ] Настроена интеграция с Qdrant для семантического поиска
- [ ] Добавлены Git hooks для валидации при коммите
- [ ] Настроен CI/CD для автоматической проверки документации
- [ ] Создан dashboard для метрик покрытия документацией
- [ ] Добавлена поддержка нескольких языков (EN/RU)

---

## 🎯 Измерение эффективности

### Метрики до внедрения

Замерьте перед внедрением:
1. **Токены на онбординг нового агента**: Сколько токенов тратится на объяснение проекта новому агенту?
2. **Время на поиск информации**: Сколько времени агент тратит на grep/glob для поиска нужной информации?
3. **Количество устаревших документов**: Сколько документов не обновлялись >90 дней?
4. **Broken references**: Сколько ссылок на несуществующие файлы/функции?

### Метрики после внедрения (через 2-4 недели)

Сравните:
1. **Снижение токенов**: 70-80% для повторных вопросов (агент читает Summary вместо кода)
2. **Скорость поиска**: Агент находит нужную информацию в 2-3 раза быстрее (через README.md)
3. **Актуальность документов**: 0 документов со staleness >90 дней
4. **Broken references**: 0 (автоматическая валидация)
5. **Покрытие документацией**: >80% модулей имеют документацию

### Примеры измерений

**До внедрения:**
```
Вопрос: "Как работает авторизация пользователей?"
Ответ агента: [Читает 5 файлов кода, 15000 токенов, 30 секунд]
```

**После внедрения:**
```
Вопрос: "Как работает авторизация пользователей?"
Ответ агента: [Читает !DOC/architecture/SYSTEM_OVERVIEW.md#auth, 2000 токенов, 5 секунд]
Экономия: 87% токенов, 83% времени
```

---

## 🚀 Примеры использования

### Сценарий 1: Новый агент в проекте

**До системы:**
```
User: Explain the database architecture
Agent: [Reads 10 files, analyzes schema, 20000 tokens]
```

**С системой:**
```
User: Explain the database architecture
Agent: [Reads !DOC/architecture/DATABASE.md, 3000 tokens]
Result: 85% token reduction
```

### Сценарий 2: Обновление кода

**До системы:**
```
Agent: [Changes code in app/services/auth.py]
[Docs become stale, no one notices for weeks]
```

**С системой:**
```
Agent: [Changes code in app/services/auth.py]
Hook: "Code changed in auth.py. Docs !DOC/architecture/SYSTEM_OVERVIEW.md reference this. Update docs?"
Agent: [Updates docs in same commit]
Result: Docs always synchronized
```

### Сценарий 3: Поиск связанных документов

**До системы:**
```
User: Find docs about authentication
Agent: [grep -r "auth" ., reads 50 files, 30000 tokens]
```

**С системой:**
```
User: Find docs about authentication
Agent: [Reads !DOC/README.md → architecture/SYSTEM_OVERVIEW.md#authentication]
Agent: [Finds cross-references to implementations/AUTH_FLOW.md]
Result: 90% token reduction, complete context
```

---

## 📦 Готовый архив для копирования

Для удобства, создайте архив с шаблоном:

```bash
# В корне englishFriend проекта
tar -czf documentation-system-template.tar.gz \
  .claude/skills/documentation-maintenance/ \
  .claude/agents/documentation-manager.md \
  .kiro/hooks/documentation-*.json \
  .kiro/specs/documentation-management-system/ \
  !DOC/DOCUMENTATION_SYSTEM.md \
  !DOC/DOCUMENTATION_SYSTEM_TEMPLATE.md

# Распаковка в новом проекте
cd <NEW_PROJECT>
tar -xzf documentation-system-template.tar.gz
```

Или создайте Git-репозиторий с шаблоном:

```bash
# Создайте отдельный репозиторий documentation-system-template
git clone https://github.com/YOU/documentation-system-template
cd <NEW_PROJECT>
cp -r ../documentation-system-template/.claude .
cp -r ../documentation-system-template/.kiro .
mkdir -p !DOC
cp ../documentation-system-template/!DOC/README.template.md !DOC/README.md
```

---

## 🔄 Поддержка и обновления

### Обновление системы на всех проектах

Когда улучшаете систему на одном проекте:

1. Обновите шаблон в `documentation-system-template` репозитории
2. Создайте CHANGELOG с описанием улучшений
3. Примените обновления на других проектах:

```bash
# В каждом проекте
cd <PROJECT>
git pull https://github.com/YOU/documentation-system-template main --allow-unrelated-histories

# Или вручную скопируйте обновлённые файлы
```

### Версионирование шаблона

Используйте семантическое версионирование:
- **1.0.0** - Текущая версия (базовая система)
- **1.1.0** - Добавлен semantic search (minor)
- **2.0.0** - Изменена структура папок (major breaking change)

---

## 🎓 Обучение команды

### Быстрый старт для разработчиков

```markdown
# Documentation System Quick Start

## For Developers

**When you edit code:**
1. You'll get an automatic reminder to check docs
2. Search for docs mentioning your code: `grep -r "function_name" !DOC/`
3. Update affected docs
4. Commit code + docs together

**When you need info:**
1. Start with `!DOC/README.md` (documentation index)
2. Use cross-references to navigate related docs
3. Check `GLOSSARY.md` for unfamiliar terms

**When you write docs:**
1. Use the template (Summary → Overview → Details)
2. Add `last_updated` date
3. Create cross-references to related docs
4. Run validation: "Invoke documentation-manager to validate"

## For Agents

**You have access to:**
- **Skill** (automatic): Documentation maintenance rules
- **Agent** (on-demand): `"Invoke documentation-manager for [validation/search/staleness check]"`
- **Hooks** (automatic): Reminders when code changes

**Best practices:**
- ALWAYS read `!DOC/README.md` first when joining a new project
- Use Summary sections for quick context (saves 70-80% tokens)
- Update docs in same commit as code changes
- Run periodic staleness checks (weekly)
```

---

## 📞 Поддержка

**Вопросы?**
- Прочитайте `!DOC/DOCUMENTATION_SYSTEM.md` в englishFriend проекте (полная документация системы)
- Проверьте примеры в этом файле
- Вызовите documentation-manager agent для помощи

**Проблемы?**
- Убедитесь, что все файлы скопированы корректно
- Проверьте, что паттерны в хуках соответствуют вашему проекту
- Протестируйте каждый компонент отдельно (skill, agent, hooks)

**Улучшения?**
- Создайте issue в englishFriend репозитории
- Или адаптируйте под ваши нужды и поделитесь опытом

---

## Последнее обновление

**Дата**: 2025-01-31
**Версия**: 1.0
**Автор**: Основано на системе englishFriend проекта
**Лицензия**: Открыто для использования в любых проектах
