#!/bin/bash
# Скрипт для развертывания системы управления документацией на новом проекте

set -e  # Exit on error

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Функция для вывода сообщений
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Проверка аргументов
if [ -z "$1" ]; then
    log_error "Usage: $0 <target_project_path> [project_name]"
    echo "Example: $0 /path/to/my-project MyProject"
    exit 1
fi

TARGET_PROJECT="$1"
PROJECT_NAME="${2:-MyProject}"
CURRENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_DIR="$(dirname "$CURRENT_DIR")"

log_info "Starting documentation system deployment..."
log_info "Source: $SOURCE_DIR"
log_info "Target: $TARGET_PROJECT"
log_info "Project Name: $PROJECT_NAME"

# Проверка существования целевого проекта
if [ ! -d "$TARGET_PROJECT" ]; then
    log_error "Target project directory does not exist: $TARGET_PROJECT"
    exit 1
fi

# Создание структуры папок
log_info "Creating folder structure..."

mkdir -p "$TARGET_PROJECT/!DOC"/{architecture,strategy,implementations,research,operations,archive}
mkdir -p "$TARGET_PROJECT/.claude"/{agents,skills/documentation-maintenance}
mkdir -p "$TARGET_PROJECT/.kiro"/{hooks,specs/documentation-management-system}

# Создание .gitkeep файлов
touch "$TARGET_PROJECT/!DOC"/{architecture,implementations,research,operations,archive}/.gitkeep

log_info "✓ Folder structure created"

# Копирование skill
log_info "Copying documentation maintenance skill..."
cp "$SOURCE_DIR/.claude/skills/documentation-maintenance/SKILL.md" \
   "$TARGET_PROJECT/.claude/skills/documentation-maintenance/"
log_info "✓ Skill copied"

# Копирование agent
log_info "Copying documentation manager agent..."
cp "$SOURCE_DIR/.claude/agents/documentation-manager.md" \
   "$TARGET_PROJECT/.claude/agents/"
log_info "✓ Agent copied"

# Копирование hooks
log_info "Copying hooks..."
cp "$SOURCE_DIR/.kiro/hooks/documentation-update-reminder.json" \
   "$TARGET_PROJECT/.kiro/hooks/"
cp "$SOURCE_DIR/.kiro/hooks/documentation-staleness-check.json" \
   "$TARGET_PROJECT/.kiro/hooks/"
log_info "✓ Hooks copied"

# Копирование specs (опционально)
log_info "Copying specs..."
cp "$SOURCE_DIR/.kiro/specs/documentation-management-system"/*.md \
   "$TARGET_PROJECT/.kiro/specs/documentation-management-system/"
log_info "✓ Specs copied"

# Создание README.md с подстановкой имени проекта
log_info "Creating README.md..."
cat > "$TARGET_PROJECT/!DOC/README.md" << EOF
# $PROJECT_NAME Documentation Index

---
last_updated: $(date +%Y-%m-%d)
---

## 📚 Overview

This directory contains all documentation for **$PROJECT_NAME** - [brief project description].

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
- **Last Updated Date**: Each file includes a \`last_updated\` field
- **Summary Section**: Each file starts with a 2-3 sentence summary
- **Clear Structure**: Consistent heading hierarchy
- **Internal Links**: All cross-references use relative paths

## 🔄 Keeping Documentation Updated

- Update relevant docs when implementing features
- Add \`last_updated\` date when making changes
- Log major changes in [CHANGELOG.md](CHANGELOG.md)
- Archive outdated docs to \`archive/\` folder

---

**Last Updated**: $(date +%Y-%m-%d)
EOF

log_info "✓ README.md created"

# Создание CHANGELOG.md
log_info "Creating CHANGELOG.md..."
cat > "$TARGET_PROJECT/!DOC/CHANGELOG.md" << EOF
# Documentation Changelog

---
last_updated: $(date +%Y-%m-%d)
---

## $(date +%Y-%m-%d) - Initial Documentation Structure

### Overview
Initial creation of documentation structure with automated management system.

### Changes

#### New Structure
- **Created** folder structure: \`architecture/\`, \`strategy/\`, \`implementations/\`, \`research/\`, \`operations/\`, \`archive/\`
- **Created** \`README.md\` - Documentation index
- **Created** \`CHANGELOG.md\` - This file

#### Documentation System
- **Deployed** Documentation Maintenance Skill (\`.claude/skills/\`)
- **Deployed** Documentation Manager Agent (\`.claude/agents/\`)
- **Deployed** Automated Hooks (\`.kiro/hooks/\`)

### Improvements
- ✅ Structured navigation
- ✅ Automatic documentation-code synchronization
- ✅ Validation of references and structure
- ✅ Staleness detection
- ✅ 70-80% token consumption reduction

---

EOF

log_info "✓ CHANGELOG.md created"

# Создание GLOSSARY.md
log_info "Creating GLOSSARY.md..."
cat > "$TARGET_PROJECT/!DOC/GLOSSARY.md" << EOF
# Technical Glossary

---
last_updated: $(date +%Y-%m-%d)
---

## Overview

Definitions of technical terms, acronyms, and concepts used throughout the $PROJECT_NAME documentation.

---

## Project-Specific Terms

### [Term 1]
[Definition]

### [Term 2]
[Definition]

---

## Common Technical Terms

### API (Application Programming Interface)
[Definition]

### Async/Await
[Definition]

---

## Last Updated

$(date +%Y-%m-%d): Initial creation
EOF

log_info "✓ GLOSSARY.md created"

# Копирование шаблона системы документации
log_info "Copying documentation system template..."
cp "$SOURCE_DIR/!DOC/DOCUMENTATION_SYSTEM_TEMPLATE.md" \
   "$TARGET_PROJECT/!DOC/"
log_info "✓ Template copied"

# Вывод итоговой информации
echo ""
log_info "=========================================="
log_info "Documentation system deployed successfully!"
log_info "=========================================="
echo ""
log_info "Next steps:"
echo "  1. Adapt hooks patterns in .kiro/hooks/documentation-update-reminder.json"
echo "     (set file patterns for your programming language)"
echo ""
echo "  2. Create initial documents:"
echo "     - !DOC/architecture/SYSTEM_OVERVIEW.md"
echo "     - !DOC/strategy/TECHNICAL_STRATEGY.md"
echo "     - !DOC/strategy/ROADMAP.md"
echo ""
echo "  3. Test the system:"
echo "     - Edit a code file → check if reminder appears"
echo "     - Invoke documentation-manager agent for validation"
echo "     - Run staleness check"
echo ""
log_info "For detailed instructions, see:"
log_info "  $TARGET_PROJECT/!DOC/DOCUMENTATION_SYSTEM_TEMPLATE.md"
echo ""
log_info "System components:"
echo "  ✓ Skill: .claude/skills/documentation-maintenance/"
echo "  ✓ Agent: .claude/agents/documentation-manager.md"
echo "  ✓ Hooks: .kiro/hooks/documentation-*.json"
echo "  ✓ Docs:  !DOC/ (with structure)"
echo ""
log_info "Deployment complete! 🎉"
