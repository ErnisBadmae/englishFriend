# EnglishFriend Documentation Index

---
last_updated: 2025-01-31
---

## 📚 Overview

This directory contains all documentation for the EnglishFriend AI Mentor project - an AI-powered English learning platform specialized for Russian-speaking students.

## 🗂️ Documentation Structure

```
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
│   ├── BUSINESS_STRATEGY.md - Market analysis, pricing, competitors
│   ├── TECHNICAL_STRATEGY.md - Technology choices and decisions
│   └── ROADMAP.md - Development phases and milestones
│
├── implementations/ - Implementation guides
│   ├── LANGGRAPH_AGENT.md - LangGraph agent implementation
│   └── DATABASE_ROADMAP.md - Database implementation plan
│
├── research/ - Research and analysis
│   └── VOICE_AI_TECHNOLOGIES.md - Voice AI technology comparison
│
├── operations/ - Operational documentation
│   └── SESSION_LOG.md - Development session log
│
└── archive/ - Outdated/historical documents
    └── concept_original.md - Original project concept
```

## 🚀 Quick Start for New Developers

### Recommended Reading Order

1. **Start Here**: [QUICK_START.md](../QUICK_START.md) - Get the project running
2. **Understand the System**: [architecture/SYSTEM_OVERVIEW.md](architecture/SYSTEM_OVERVIEW.md) - Architecture overview
3. **Database Design**: [architecture/DATABASE.md](architecture/DATABASE.md) - Database schema and design
4. **Business Context**: [strategy/BUSINESS_STRATEGY.md](strategy/BUSINESS_STRATEGY.md) - Market positioning
5. **Technical Decisions**: [strategy/TECHNICAL_STRATEGY.md](strategy/TECHNICAL_STRATEGY.md) - Why we chose our tech stack
6. **Development Plan**: [strategy/ROADMAP.md](strategy/ROADMAP.md) - What we're building and when

### For Specific Tasks

- **Setting up the database**: [implementations/DATABASE_ROADMAP.md](implementations/DATABASE_ROADMAP.md)
- **Understanding the AI agent**: [implementations/LANGGRAPH_AGENT.md](implementations/LANGGRAPH_AGENT.md)
- **Voice AI technology choices**: [research/VOICE_AI_TECHNOLOGIES.md](research/VOICE_AI_TECHNOLOGIES.md)
- **Recent changes**: [operations/SESSION_LOG.md](operations/SESSION_LOG.md)

## 📖 Key Documents

### Architecture

- **[SYSTEM_OVERVIEW.md](architecture/SYSTEM_OVERVIEW.md)** - Complete system architecture, data flow, components
- **[DATABASE.md](architecture/DATABASE.md)** - PostgreSQL schema, partitioning, RLS policies, CDC

### Strategy

- **[BUSINESS_STRATEGY.md](strategy/BUSINESS_STRATEGY.md)** - Market analysis, competitors, pricing model
- **[TECHNICAL_STRATEGY.md](strategy/TECHNICAL_STRATEGY.md)** - Technology stack, architecture decisions
- **[ROADMAP.md](strategy/ROADMAP.md)** - Development phases, timelines, milestones

### Implementations

- **[LANGGRAPH_AGENT.md](implementations/LANGGRAPH_AGENT.md)** - LangGraph agent implementation summary
- **[DATABASE_ROADMAP.md](implementations/DATABASE_ROADMAP.md)** - Sprint-based database implementation plan

### Research

- **[VOICE_AI_TECHNOLOGIES.md](research/VOICE_AI_TECHNOLOGIES.md)** - Analysis of voice AI technologies (Moshi, OpenAI Realtime, Hume AI, etc.)

### Operations

- **[SESSION_LOG.md](operations/SESSION_LOG.md)** - Development session history and current status

## 🔍 Finding Information

### By Topic

| Topic | Document |
|-------|----------|
| Getting started | [QUICK_START.md](../QUICK_START.md) |
| System architecture | [architecture/SYSTEM_OVERVIEW.md](architecture/SYSTEM_OVERVIEW.md) |
| Database design | [architecture/DATABASE.md](architecture/DATABASE.md) |
| Market analysis | [strategy/BUSINESS_STRATEGY.md](strategy/BUSINESS_STRATEGY.md) |
| Technology choices | [strategy/TECHNICAL_STRATEGY.md](strategy/TECHNICAL_STRATEGY.md) |
| Development roadmap | [strategy/ROADMAP.md](strategy/ROADMAP.md) |
| Voice AI comparison | [research/VOICE_AI_TECHNOLOGIES.md](research/VOICE_AI_TECHNOLOGIES.md) |
| Recent changes | [operations/SESSION_LOG.md](operations/SESSION_LOG.md) |
| Technical terms | [GLOSSARY.md](GLOSSARY.md) |

### By Role

**New Developer:**
1. QUICK_START.md → architecture/SYSTEM_OVERVIEW.md → architecture/DATABASE.md

**Product Manager:**
1. strategy/BUSINESS_STRATEGY.md → strategy/ROADMAP.md

**Technical Lead:**
1. strategy/TECHNICAL_STRATEGY.md → architecture/SYSTEM_OVERVIEW.md → research/VOICE_AI_TECHNOLOGIES.md

**DevOps Engineer:**
1. architecture/SYSTEM_OVERVIEW.md → architecture/DATABASE.md → implementations/DATABASE_ROADMAP.md

## 📝 Documentation Standards

All documentation follows these standards:

- **Last Updated Date**: Each file includes a `last_updated` field
- **Summary Section**: Each file starts with a 2-3 sentence summary
- **Clear Structure**: Consistent heading hierarchy and formatting
- **Internal Links**: All cross-references use relative paths
- **Language**: English for technical docs, Russian for business strategy

## 🔄 Keeping Documentation Updated

- Update relevant docs when implementing features
- Add `last_updated` date when making changes
- Log major changes in [CHANGELOG.md](CHANGELOG.md)
- Archive outdated docs to `archive/` folder

## 📚 Glossary

See [GLOSSARY.md](GLOSSARY.md) for definitions of technical terms used throughout the documentation.

## 📋 Recent Changes

See [CHANGELOG.md](CHANGELOG.md) for a complete history of documentation changes.

---

**Note**: For the complete technical specification, refer to [architecture/SYSTEM_OVERVIEW.md](architecture/SYSTEM_OVERVIEW.md) and [architecture/DATABASE.md](architecture/DATABASE.md). The original TECHNICAL_SPECIFICATION.md was incomplete and has been archived.

**Last Updated**: 2025-01-31
