# Documentation Management System

## Summary

Automated documentation maintenance system that keeps project docs synchronized with code changes, validates references, creates cross-links, and removes outdated content. Reduces token consumption by 70-80% by providing agents with accurate, up-to-date documentation instead of requiring repeated codebase analysis.

## Overview

The Documentation Management System consists of three layers:

1. **SKILL** (`.claude/skills/documentation-maintenance/`) - Lightweight rules applied by all agents
2. **Specialized Agent** (`.claude/agents/documentation-manager.md`) - Heavy operations (validation, search, indexing)
3. **Hooks** (`.kiro/hooks/`) - Automated triggers for documentation updates

This hybrid approach ensures documentation stays current without manual intervention while minimizing overhead.

---

## Components

### 1. Documentation Maintenance Skill

**Location**: `.claude/skills/documentation-maintenance/SKILL.md`

**Purpose**: Provides all agents with documentation maintenance guidelines

**Applied automatically when:**
- Creating new modules/components
- Modifying public APIs
- Changing architecture
- Completing features

**Key principles:**
- Update docs in same commit as code changes
- Validate syntax and references before committing
- Create bidirectional cross-references
- Flag outdated documentation
- Use token-efficient structure (Summary → Overview → Details)

**Example usage:**
```bash
# Agent automatically applies skill when editing code
# No explicit invocation needed
```

### 2. Documentation Manager Agent

**Location**: `.claude/agents/documentation-manager.md`

**Purpose**: Performs heavy documentation operations

**Capabilities:**
- **Validation**: Check syntax, references, structure
- **Search**: Find documentation by keywords or semantic similarity
- **Cross-Reference Analysis**: Build relationship graph, find missing links
- **Staleness Detection**: Identify outdated docs, broken references
- **Coverage Analysis**: Calculate documentation completeness by component
- **Indexing**: Build searchable index (future: Qdrant integration)

**Invocation examples:**
```bash
# Validate all documentation
"Invoke documentation-manager agent to validate all docs"

# Find related documentation
"Invoke documentation-manager agent to find docs related to voice WebSocket"

# Detect stale documentation
"Invoke documentation-manager agent to scan for outdated docs"

# Analyze coverage
"Invoke documentation-manager agent to generate coverage report"

# Build cross-reference graph
"Invoke documentation-manager agent to analyze cross-references"
```

### 3. Documentation Hooks

**Location**: `.kiro/hooks/`

**Purpose**: Automated triggers for documentation maintenance

**Available hooks:**

1. **documentation-update-reminder.json**
   - **Trigger**: File edited (Python, TypeScript, SQL)
   - **Action**: Reminds agent to check if docs need updating
   - **Patterns**: `app/**/*.py`, `frontend/src/**/*.tsx`, `db/migrations/**/*.sql`

2. **documentation-staleness-check.json**
   - **Trigger**: User-triggered (manual)
   - **Action**: Invokes documentation-manager agent for staleness scan
   - **Usage**: Run periodically (weekly/monthly)

**Enable/disable hooks:**
```bash
# Hooks are enabled by default
# To disable, edit hook JSON and set "enabled": false
```

---

## Workflow

### Daily Development Workflow

**When editing code:**

1. **Automatic reminder** (via hook):
   - Hook triggers when you save a code file
   - Agent checks if documentation references this code
   - Agent updates documentation if needed

2. **Manual check** (if needed):
   - Search for docs referencing your code: `grep -r "function_name" !DOC/`
   - Update affected documentation
   - Commit code + docs together

**Example:**
```bash
# 1. Edit code
vim app/services/ai/llm_provider.py

# 2. Hook triggers automatically
# Agent: "Checking if documentation needs updating..."

# 3. Agent updates docs
# Modified: !DOC/TECHNICAL_SPECIFICATION.md

# 4. Commit together
git add app/services/ai/llm_provider.py !DOC/TECHNICAL_SPECIFICATION.md
git commit -m "feat: Update LLM provider + docs"
```

### Weekly Maintenance Workflow

**Staleness check:**

1. **Trigger staleness check hook**:
   - Manually trigger: "Run documentation staleness check"
   - Agent invokes documentation-manager agent
   - Agent generates staleness report

2. **Review and fix**:
   - Update CRITICAL items (broken references)
   - Review WARNING items (approaching staleness threshold)
   - Archive obsolete documentation

**Example:**
```bash
# 1. Trigger staleness check
"Run documentation staleness check"

# 2. Review report
# CRITICAL: !DOC/LEGACY_API.md (broken references)
# WARNING: !DOC/DEPLOYMENT.md (95 days old)

# 3. Fix issues
git mv !DOC/LEGACY_API.md !DOC/archive/
vim !DOC/DEPLOYMENT.md  # Update

# 4. Commit
git commit -m "docs: Archive LEGACY_API.md, update DEPLOYMENT.md"
```

### Monthly Coverage Review

**Coverage analysis:**

1. **Generate coverage report**:
   - Invoke: "Generate documentation coverage report"
   - Agent scans codebase and documentation
   - Agent identifies gaps

2. **Prioritize gaps**:
   - Focus on high-complexity code without docs
   - Focus on public APIs without examples
   - Create documentation for priority gaps

**Example:**
```bash
# 1. Generate coverage report
"Generate documentation coverage report"

# 2. Review gaps
# High-Priority: app/services/ai/memory_extraction_service.py (complexity: 15, no docs)

# 3. Create documentation
vim !DOC/TECHNICAL_SPECIFICATION.md  # Add section

# 4. Commit
git commit -m "docs: Add memory extraction service documentation"
```

---

## Documentation Structure

### Required Sections

All documentation files MUST include:

```markdown
# Document Title

## Summary
[2-3 sentence overview - ALWAYS include this]

## Overview
[High-level explanation - what, why, when]

## Details
[In-depth content - how, examples, edge cases]

## Related Documentation
[Cross-references to other docs]

## Last Updated
[Date and reason for update]
```

### Cross-Reference Format

Use consistent reference types:

```markdown
## Related Documentation

- **Depends-On**: [Database Schema](./DB.md) - Required for understanding data models
- **Related-To**: [API Design](./TECHNICAL_SPECIFICATION.md#api-design) - Similar patterns
- **Implements**: [Architecture Overview](./SYSTEM_OVERVIEW.md#architecture) - Concrete implementation
- **Supersedes**: [Legacy API](./archive/LEGACY_API.md) - Replaced by this document
- **Example-Of**: [Design Patterns](./PATTERNS.md) - Concrete example
```

### Staleness Markers

Mark outdated documentation:

```markdown
<!-- OUTDATED: References removed function `process_legacy_data()` -->
<!-- Last updated: 2024-10-15, threshold: 90 days -->

# Document Title
...
```

---

## Validation Rules

### Code Block Validation

**Supported languages:**
- Python (`.py`)
- TypeScript (`.ts`, `.tsx`)
- JavaScript (`.js`, `.jsx`)
- SQL (`.sql`)
- Bash (`.sh`)

**Validation:**
- Extract code blocks from markdown
- Parse syntax using AST or language-specific tools
- Flag syntax errors with line numbers

**Example:**
```markdown
<!-- Valid Python code block -->
```python
async def get_user(user_id: int) -> User:
    """Fetch user by ID."""
    return await db.get(User, user_id)
```

<!-- Invalid Python code block (missing closing parenthesis) -->
```python
async def get_user(user_id: int -> User:
    return await db.get(User, user_id)
```
```

### Reference Validation

**File path references:**
- Format: `app/services/ai/llm_provider.py`
- Validation: Verify file exists in codebase
- Error: "Broken reference to `<path>` (file not found)"

**Function/class references:**
- Format: `get_llm_provider()`, `LearningPlanService`
- Validation: Verify name exists using grep
- Error: "Broken reference to `<name>` (not found in codebase)"

**URL references:**
- Format: `https://example.com/docs`
- Validation: Check URL is well-formed (future: check reachability)
- Error: "Invalid URL `<url>` (malformed)"

### Structure Validation

**Required sections:**
- Summary (at top)
- Overview
- Details (or equivalent content sections)
- Related Documentation (if applicable)
- Last Updated

**Heading hierarchy:**
- No skipped levels (H1 → H2 → H3, not H1 → H3)
- Clear nesting structure
- Consistent formatting

**Completeness:**
- No empty sections
- No TODO/FIXME markers (flag as warnings)
- No placeholder text (`[TBD]`, `[To Be Determined]`)

---

## Metrics and Thresholds

### Staleness Thresholds

**Time-based:**
- **Fresh**: Updated within 90 days
- **Warning**: 90-120 days since last update
- **Critical**: 120+ days since last update

**Reference-based:**
- **Fresh**: All references valid
- **Warning**: 1-2 broken references
- **Critical**: 3+ broken references

### Coverage Thresholds

**Overall coverage:**
- **Good**: 80%+ modules documented
- **Acceptable**: 60-80% modules documented
- **Poor**: <60% modules documented

**By component:**
- **Backend Services**: Target 85%+
- **Frontend Components**: Target 70%+
- **AI Services**: Target 90%+
- **Infrastructure**: Target 60%+

### Complexity Thresholds

**Cyclomatic complexity:**
- **Low**: 1-5 (documentation optional)
- **Medium**: 6-10 (documentation recommended)
- **High**: 11+ (documentation required)

**Public API:**
- All public APIs MUST have documentation
- All public APIs MUST have examples

---

## Future Enhancements

When the full Documentation Management System is implemented (see `.kiro/specs/documentation-management-system/`):

### Automated Features

1. **Semantic Search** (Qdrant integration)
   - Find documentation by concept, not just keywords
   - Discover related docs using embeddings
   - Rank results by semantic similarity

2. **Auto Cross-References** (Embedding-based)
   - Automatically discover related documentation
   - Suggest cross-references based on content similarity
   - Maintain bidirectional links automatically

3. **Real-Time Validation** (Git hooks)
   - Validate on every commit
   - Block commits with broken references
   - Auto-fix simple issues (formatting, links)

4. **Staleness Detection** (Scheduled hooks)
   - Periodic scans (daily/weekly)
   - Automatic flagging of outdated docs
   - Notifications for critical staleness

5. **Coverage Tracking** (Dashboard)
   - Real-time coverage metrics
   - Gap identification with priorities
   - Trend analysis over time

6. **Version History** (Git integration)
   - Track documentation evolution
   - Query docs at specific timestamps
   - Coordinate doc/code reversions

7. **Multi-Language Support**
   - Store docs in multiple languages
   - Flag translations when source updates
   - Maintain cross-language references

### Implementation Status

**Current (Manual):**
- ✅ Documentation maintenance skill (all agents)
- ✅ Documentation manager agent (manual invocation)
- ✅ File edit hooks (automatic reminders)
- ✅ Staleness check hook (manual trigger)

**Planned (Automated):**
- ⏳ Semantic search (Qdrant integration)
- ⏳ Auto cross-references (embedding-based)
- ⏳ Real-time validation (Git hooks)
- ⏳ Scheduled staleness scans
- ⏳ Coverage dashboard
- ⏳ Version history queries
- ⏳ Multi-language support

**Timeline:**
- Phase 1 (Current): Manual operations with skill + agent
- Phase 2 (Q2 2025): Automated validation + indexing
- Phase 3 (Q3 2025): Semantic search + auto cross-references
- Phase 4 (Q4 2025): Full system with dashboard + multi-language

---

## Quick Reference

### Common Commands

**Validate documentation:**
```bash
"Invoke documentation-manager agent to validate all docs"
```

**Find related docs:**
```bash
"Invoke documentation-manager agent to find docs related to <topic>"
```

**Check staleness:**
```bash
"Run documentation staleness check"
```

**Generate coverage report:**
```bash
"Generate documentation coverage report"
```

**Analyze cross-references:**
```bash
"Invoke documentation-manager agent to analyze cross-references"
```

### File Locations

**Documentation:**
- Project docs: `!DOC/`
- Archived docs: `!DOC/archive/`

**System files:**
- Skill: `.claude/skills/documentation-maintenance/SKILL.md`
- Agent: `.claude/agents/documentation-manager.md`
- Hooks: `.kiro/hooks/documentation-*.json`
- Spec: `.kiro/specs/documentation-management-system/`

### Key Principles

1. **Synchronize**: Update docs in same commit as code
2. **Validate**: Check syntax, references, structure
3. **Cross-Reference**: Create bidirectional links
4. **Structure**: Use consistent format (Summary → Overview → Details)
5. **Detect Staleness**: Flag outdated docs (broken refs, time threshold)
6. **Remove Dead Docs**: Archive or delete obsolete documentation
7. **Track Coverage**: Monitor completeness by component
8. **Token Efficiency**: Structure for progressive detail levels

---

## Support

**Questions or issues?**
- Review this document: `!DOC/DOCUMENTATION_SYSTEM.md`
- Check skill guidelines: `.claude/skills/documentation-maintenance/SKILL.md`
- Invoke documentation-manager agent for help

**Contributing:**
- Follow documentation maintenance skill guidelines
- Use documentation-manager agent for heavy operations
- Enable hooks for automatic reminders
- Run periodic staleness checks (weekly/monthly)

---

## Last Updated

2025-01-31: Initial creation of documentation management system
