# Documentation System - Quick Start

## 🎯 Что это?

Система автоматического управления документацией, которая:
- ✅ Напоминает обновлять документацию при изменении кода
- ✅ Проверяет корректность ссылок и примеров кода
- ✅ Создает перекрестные ссылки между документами
- ✅ Находит устаревшую документацию
- ✅ Снижает расход токенов на 70-80%

## 🚀 Быстрый старт (3 минуты)

### 1. Система уже работает!

Ничего устанавливать не нужно. Система состоит из:

- **SKILL** (`.claude/skills/documentation-maintenance/`) - Автоматически применяется всеми агентами
- **Agent** (`.claude/agents/documentation-manager.md`) - Вызывается для тяжелых операций
- **Hooks** (`.kiro/hooks/`) - Автоматические напоминания

### 2. Как это работает в повседневной работе

**Сценарий 1: Редактируете код**

```python
# Вы редактируете файл
vim app/services/ai/llm_provider.py

# Сохраняете (Ctrl+S)
# ↓
# Хук автоматически срабатывает
# ↓
# Агент проверяет: "Нужно ли обновить документацию?"
# ↓
# Если нужно - агент обновляет !DOC/TECHNICAL_SPECIFICATION.md
# ↓
# Вы коммитите код + документацию вместе
git add app/services/ai/llm_provider.py !DOC/TECHNICAL_SPECIFICATION.md
git commit -m "feat: Update LLM provider + docs"
```

**Сценарий 2: Ищете информацию**

```bash
# Вместо чтения всего кода, спросите агента:
"Как работает voice WebSocket?"

# Агент использует документацию (быстро, мало токенов)
# Вместо чтения 10+ файлов кода (медленно, много токенов)
```

**Сценарий 3: Еженедельная проверка**

```bash
# Раз в неделю запускайте:
"Run documentation staleness check"

# Агент найдет:
# - Документы с битыми ссылками
# - Документы старше 90 дней
# - TODO/FIXME маркеры

# Вы исправляете критичные проблемы
```

### 3. Основные команды

**Проверить документацию:**
```bash
"Validate all documentation"
```

**Найти связанные документы:**
```bash
"Find documentation related to voice WebSocket"
```

**Проверить устаревшую документацию:**
```bash
"Run documentation staleness check"
```

**Посмотреть покрытие:**
```bash
"Generate documentation coverage report"
```

## 📋 Правила для разработчиков

### ✅ Делайте

1. **Обновляйте документацию в том же коммите, что и код**
   ```bash
   git add app/services/my_service.py !DOC/TECHNICAL_SPECIFICATION.md
   git commit -m "feat: Update service + docs"
   ```

2. **Используйте структуру Summary → Overview → Details**
   ```markdown
   # Document Title
   
   ## Summary
   [2-3 sentences]
   
   ## Overview
   [High-level explanation]
   
   ## Details
   [Implementation specifics]
   ```

3. **Добавляйте перекрестные ссылки**
   ```markdown
   ## Related Documentation
   - **Depends-On**: [Database Schema](./DB.md)
   - **Related-To**: [API Design](./TECHNICAL_SPECIFICATION.md)
   ```

4. **Проверяйте документацию перед коммитом**
   ```bash
   # Агент проверит автоматически, но можно и вручную:
   "Validate documentation for my changes"
   ```

### ❌ Не делайте

1. **Не коммитьте код без обновления документации**
   ```bash
   # Плохо:
   git add app/services/my_service.py
   git commit -m "feat: Update service"  # Документация забыта!
   ```

2. **Не оставляйте битые ссылки**
   ```markdown
   <!-- Плохо: -->
   See [Old API](./REMOVED_FILE.md)  # Файл удален!
   ```

3. **Не оставляйте TODO маркеры надолго**
   ```markdown
   <!-- Плохо: -->
   ## Future Work
   TODO: Add this section  # Либо добавьте, либо удалите секцию
   ```

## 🔧 Расширенное использование

### Вызов специализированного агента

**Для валидации:**
```bash
"Invoke documentation-manager agent to validate all docs"
```

**Для поиска:**
```bash
"Invoke documentation-manager agent to find docs related to LLM integration"
```

**Для анализа покрытия:**
```bash
"Invoke documentation-manager agent to generate coverage report"
```

**Для проверки устаревшей документации:**
```bash
"Invoke documentation-manager agent to scan for stale docs"
```

**Для анализа перекрестных ссылок:**
```bash
"Invoke documentation-manager agent to analyze cross-references"
```

### Настройка хуков

**Отключить напоминания при редактировании:**
```json
// Редактируйте .kiro/hooks/documentation-update-reminder.json
{
  "enabled": false  // Добавьте это поле
}
```

**Изменить паттерны файлов:**
```json
// Редактируйте .kiro/hooks/documentation-update-reminder.json
{
  "when": {
    "patterns": [
      "app/**/*.py",           // Python файлы
      "frontend/src/**/*.tsx"  // TypeScript файлы
      // Добавьте свои паттерны
    ]
  }
}
```

## 📊 Метрики

### Пороги устаревания

- **Fresh**: Обновлено < 90 дней назад
- **Warning**: 90-120 дней
- **Critical**: > 120 дней

### Пороги покрытия

- **Good**: 80%+ модулей задокументировано
- **Acceptable**: 60-80%
- **Poor**: < 60%

### Сложность кода

- **Low** (1-5): Документация опциональна
- **Medium** (6-10): Документация рекомендуется
- **High** (11+): Документация обязательна

## 🎓 Примеры

### Пример 1: Создание новой документации

```markdown
# Voice WebSocket Service

## Summary
Real-time voice chat using WebSocket, Groq LLM, and edge-tts. Supports learning modes with automatic mode selection.

## Overview
The voice service enables conversational English practice through WebSocket. Users speak (STT via Vosk), system generates responses (Groq), and synthesizes audio (edge-tts).

## Details
[Implementation specifics...]

## Related Documentation
- **Depends-On**: [LLM Provider](./TECHNICAL_SPECIFICATION.md#groq-llm-integration)
- **Related-To**: [Learning Modes](./SYSTEM_OVERVIEW.md#learning-modes)

## Last Updated
2025-01-31: Initial creation
```

### Пример 2: Обновление существующей документации

```markdown
<!-- Добавьте в начало, если обновляете -->
## Last Updated
2025-01-31: Updated LLM provider section to reflect Groq integration

<!-- Обновите содержимое -->
## LLM Integration

Previously used OpenAI GPT-4. Now uses Groq llama-3.3-70b for faster inference...
```

### Пример 3: Маркировка устаревшей документации

```markdown
<!-- OUTDATED: References removed function `process_legacy_data()` -->
<!-- Last updated: 2024-10-15, threshold: 90 days -->

# Legacy Data Processing

This document describes the `process_legacy_data()` function...
```

## 📚 Дополнительные ресурсы

**Полная документация:**
- [Documentation System Overview](!DOC/DOCUMENTATION_SYSTEM.md) - Полное описание системы
- [Documentation Maintenance Skill](../.claude/skills/documentation-maintenance/SKILL.md) - Правила для агентов
- [Documentation Manager Agent](../.claude/agents/documentation-manager.md) - Специализированный агент

**Спецификация:**
- [Requirements](.kiro/specs/documentation-management-system/requirements.md)
- [Design](.kiro/specs/documentation-management-system/design.md)
- [Tasks](.kiro/specs/documentation-management-system/tasks.md)

## ❓ FAQ

**Q: Нужно ли что-то устанавливать?**
A: Нет, система уже работает. SKILL и Agent уже созданы, хуки настроены.

**Q: Как часто проверять устаревшую документацию?**
A: Рекомендуется раз в неделю запускать `"Run documentation staleness check"`.

**Q: Что делать, если агент не напоминает об обновлении документации?**
A: Проверьте, что хук включен в `.kiro/hooks/documentation-update-reminder.json` и паттерны файлов соответствуют вашим изменениям.

**Q: Можно ли отключить автоматические напоминания?**
A: Да, добавьте `"enabled": false` в файл хука `.kiro/hooks/documentation-update-reminder.json`.

**Q: Как агент понимает, какую документацию обновлять?**
A: Агент ищет упоминания имен функций, классов и путей к файлам в документации с помощью grep.

**Q: Что делать с TODO маркерами в документации?**
A: Либо выполните TODO (добавьте контент), либо удалите маркер. Не оставляйте TODO надолго.

**Q: Как добавить новый тип перекрестной ссылки?**
A: Используйте существующие типы: Depends-On, Related-To, Implements, Supersedes, Example-Of. Если нужен новый тип, обсудите с командой.

## ✅ Чеклист

Перед коммитом проверьте:

- [ ] Документация обновлена вместе с кодом
- [ ] Все ссылки на код корректны (файлы, функции, классы существуют)
- [ ] Примеры кода синтаксически корректны
- [ ] Добавлены перекрестные ссылки к связанным документам
- [ ] Обновлена секция "Last Updated"
- [ ] Нет TODO/FIXME маркеров (или они обоснованы)
- [ ] Структура документа соответствует стандарту (Summary → Overview → Details)

---

**Готово!** Теперь вы знаете, как работать с системой управления документацией. 🎉

Если возникнут вопросы, обратитесь к [полной документации](!DOC/DOCUMENTATION_SYSTEM.md).
