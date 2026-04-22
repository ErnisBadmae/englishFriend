---
name: 'Documentation Maintenance'
description: 'Automatically maintain project documentation: update when code changes, validate references, create cross-links, and remove outdated content. Reduces token consumption by keeping docs current.'
---

# Documentation Maintenance Skill

## Overview

This skill ensures project documentation stays synchronized with code changes, validated, and efficiently organized. It reduces token consumption by providing agents with accurate, up-to-date documentation instead of requiring repeated codebase analysis.

## When to Apply This Skill

**ALWAYS apply when:**
- Creating new modules, components, or features
- Modifying public APIs or interfaces
- Changing architecture or design patterns
- Adding or removing significant functionality
- Refactoring code that affects documented behavior

**ALSO apply when:**
- Reviewing pull requests (validate documentation completeness)
- Completing features (ensure all docs are current)
- Discovering broken references in documentation
- Finding TODO/FIXME markers in docs

**DON'T apply for:**
- Simple bug fixes (typos, missing await, import errors)
- Internal implementation details (private methods)
- Temporary debugging code
- Routine variable renames

---

## Core Principles

### 1. Documentation-Code Synchronization

**Rule:** Documentation MUST be updated in the same commit as code changes.

**When code changes:**
- Identify all documentation files that reference the changed code
- Update documentation to reflect new behavior
- Preserve existing cross-references
- Add new cross-references if related topics emerge

**Example:**
```python
# Code change: Renamed method
# OLD: async def get_user_profile(user_id: int)
# NEW: async def fetch_user_data(user_id: int)

# Documentation update required in:
# - !DOC/SYSTEM_OVERVIEW.md (API reference section)
# - !DOC/TECHNICAL_SPECIFICATION.md (service layer patterns)
# - Any other docs mentioning get_user_profile()
```

### 2. Staleness Detection

**Rule:** Flag documentation as outdated when references break or time thresholds exceed.

**Mark as OUTDATED if:**
- References non-existent files, functions, or classes
- Not updated in 90+ days (configurable threshold)
- Contains TODO, FIXME, or placeholder markers
- Code it describes has been significantly refactored

**Action on staleness:**
- Add `[OUTDATED]` marker at top of document
- Log reason for staleness (broken refs, time threshold, etc.)
- Notify in commit message or PR comment
- Archive if confirmed dead (no longer relevant)

**Example:**
```markdown
<!-- OUTDATED: References removed function `process_legacy_data()` -->
<!-- Last updated: 2024-10-15, threshold: 90 days -->

# Legacy Data Processing

This document describes the `process_legacy_data()` function...
```

### 3. Cross-Reference Management

**Rule:** Create bidirectional links between related documentation files.

**Cross-reference types:**
- **Depends-On**: Document A requires understanding Document B
- **Related-To**: Documents cover similar topics
- **Supersedes**: Document A replaces Document B
- **Implements**: Document describes implementation of concept in another doc
- **Example-Of**: Document provides example of concept in another doc

**Format:**
```markdown
## Related Documentation

- **Depends-On**: [Database Schema](./DB.md) - Required for understanding data models
- **Related-To**: [API Design](./TECHNICAL_SPECIFICATION.md#api-design) - Similar patterns
- **Implements**: [Architecture Overview](./SYSTEM_OVERVIEW.md#architecture) - Concrete implementation
```

**Bidirectional linking:**
- If Document A references Document B, ensure B also references A
- Update both documents in the same commit
- Use consistent reference types

### 4. Validation Rules

**Rule:** All documentation MUST pass validation before being committed.

**Validation checks:**

1. **Code Example Syntax**
   - Extract code blocks from markdown
   - Verify syntax using AST parsing
   - Support Python, TypeScript, JavaScript, SQL
   - Flag syntax errors with line numbers

2. **Reference Validation**
   - Parse documentation for file paths (e.g., `app/services/ai/llm_provider.py`)
   - Parse for function/class names (e.g., `get_llm_provider()`, `LearningPlanService`)
   - Verify references exist in current codebase
   - Generate specific error messages for broken references

3. **Structure Validation**
   - Check for required sections (Overview, Examples, etc.)
   - Validate heading hierarchy (no skipped levels: H1 → H3)
   - Check for empty sections or placeholder text
   - Ensure summary exists at document start

4. **Completeness Validation**
   - Flag TODO markers
   - Flag FIXME markers
   - Flag `[TBD]` or `[To Be Determined]` placeholders
   - Flag empty code blocks

**Example validation output:**
```
❌ VALIDATION FAILED: !DOC/TECHNICAL_SPECIFICATION.md

Errors:
- Line 45: Broken reference to `app/services/deprecated_service.py` (file not found)
- Line 102: Code block has Python syntax error (missing closing parenthesis)
- Line 200: Empty section "Future Enhancements" (remove or add content)

Warnings:
- Line 15: TODO marker found ("TODO: Add example for async patterns")
- Line 78: Document not updated in 95 days (threshold: 90 days)
```

### 5. Token-Efficient Documentation Format

**Rule:** Structure documentation for efficient token usage by agents.

**Required structure:**
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

**Progressive detail levels:**
- **Summary**: 2-3 sentences, always at top
- **Overview**: High-level concepts (1-2 paragraphs)
- **Details**: Implementation specifics, code examples
- **Examples**: Concrete use cases
- **Edge Cases**: Rare scenarios, gotchas

**Hierarchical organization:**
- Use clear heading hierarchy (H1 → H2 → H3, no skips)
- Group related content under common headings
- Separate conceptual from implementation details
- Use bullet points for lists (easier to scan)

**Example:**
```markdown
# Voice WebSocket Service

## Summary
Real-time voice chat using WebSocket, Groq LLM, and edge-tts. Supports learning modes (assessment, vocabulary drill, mock interview, free conversation) with automatic mode selection based on user goals.

## Overview
The voice service enables conversational English practice through a WebSocket connection. Users speak (STT via Vosk in browser), the system generates responses (Groq llama-3.3-70b), and synthesizes audio (edge-tts). Learning modes adapt to user goals and progress.

## Details
[Implementation specifics...]

## Related Documentation
- **Depends-On**: [LLM Provider](./TECHNICAL_SPECIFICATION.md#groq-llm-integration)
- **Related-To**: [Learning Modes](./SYSTEM_OVERVIEW.md#learning-modes)
```

---

## Documentation Workflow

### Step 1: Identify Documentation Impact

**Before making code changes:**
1. Search for documentation files that reference the code you're changing
2. Use grep/search for function names, class names, file paths
3. Check cross-references in related documentation

**Example search:**
```bash
# Find docs referencing a function
grep -r "get_user_profile" !DOC/

# Find docs referencing a file
grep -r "app/services/user_service.py" !DOC/
```

### Step 2: Update Documentation

**When updating:**
1. Modify all identified documentation files
2. Update code examples to match new behavior
3. Update references (file paths, function names)
4. Preserve existing cross-references
5. Add new cross-references if needed
6. Update "Last Updated" section with date and reason

**Example commit:**
```
feat: Rename get_user_profile to fetch_user_data

- Renamed method for clarity
- Updated SYSTEM_OVERVIEW.md (API reference)
- Updated TECHNICAL_SPECIFICATION.md (service patterns)
- Added cross-reference to new caching behavior
```

### Step 3: Validate Documentation

**Before committing:**
1. Run validation checks (syntax, references, structure)
2. Fix any validation errors
3. Address warnings (TODOs, staleness)
4. Ensure all cross-references are bidirectional

**Validation command (when implemented):**
```bash
# Future: Automated validation
python -m docs_manager validate !DOC/

# Manual validation (current):
# - Check code block syntax
# - Verify file paths exist
# - Ensure cross-references are bidirectional
```

### Step 4: Create Cross-References

**When creating new documentation:**
1. Identify related existing documentation
2. Add cross-references in new document
3. Add reciprocal cross-references in related documents
4. Use appropriate reference types (Depends-On, Related-To, etc.)

**Example:**
```markdown
<!-- In new document: !DOC/VOICE_ARCHITECTURE.md -->
## Related Documentation
- **Depends-On**: [LLM Provider](./TECHNICAL_SPECIFICATION.md#groq-llm-integration)
- **Related-To**: [WebSocket Patterns](./SYSTEM_OVERVIEW.md#websocket-patterns)

<!-- In existing document: !DOC/TECHNICAL_SPECIFICATION.md -->
## Related Documentation
- **Implemented-By**: [Voice Architecture](./VOICE_ARCHITECTURE.md) - Concrete WebSocket implementation
```

### Step 5: Remove Outdated Documentation

**When documentation becomes obsolete:**
1. Confirm documentation is truly dead (no longer relevant)
2. Check for cross-references pointing to it
3. Update or remove cross-references in other documents
4. Archive (move to `!DOC/archive/`) or delete
5. Log removal reason in commit message

**Example:**
```bash
# Archive outdated documentation
git mv !DOC/LEGACY_API.md !DOC/archive/LEGACY_API.md

# Update cross-references
# Remove references to LEGACY_API.md from other docs

# Commit with reason
git commit -m "docs: Archive LEGACY_API.md (replaced by REST_API.md)"
```

---

## Documentation Coverage

### Track Coverage by Component

**Components to document:**
- **Backend Services**: API endpoints, service layer, database models
- **Frontend Components**: React components, hooks, utilities
- **AI Services**: LLM integration, TTS/STT, memory pipeline, FSRS
- **Infrastructure**: Docker, CDC pipeline, databases (PostgreSQL, Neo4j, Qdrant)
- **Scripts**: Deployment, testing, partition management

**Coverage metrics:**
- **High Priority**: Public APIs, core services, complex algorithms
- **Medium Priority**: Internal services, utilities, helpers
- **Low Priority**: Simple CRUD operations, boilerplate code

**Example coverage report:**
```
Documentation Coverage Report:

Backend Services: 85% (17/20 modules documented)
  ✅ app/services/ai/llm_provider.py
  ✅ app/services/ai/tts_service.py
  ❌ app/services/ai/whisper_pipeline.py (missing)

Frontend Components: 60% (12/20 components documented)
  ✅ VoiceChat.tsx
  ❌ VoiceButton.tsx (missing)

AI Services: 90% (9/10 modules documented)
  ✅ memory_pipeline.py
  ✅ vocabulary_service.py
```

### Identify Documentation Gaps

**Flag as high-priority gaps:**
- High-complexity code without documentation (cyclomatic complexity > 10)
- Public APIs without examples
- Core services without overview documentation
- Architecture decisions without rationale

**Example gap report:**
```
High-Priority Documentation Gaps:

1. app/services/ai/memory_extraction_service.py
   - Complexity: 15 (high)
   - Public API: Yes
   - Documentation: None
   - Recommendation: Add overview + examples

2. app/agent/graph.py
   - Complexity: 12 (high)
   - Public API: Yes
   - Documentation: Partial (missing examples)
   - Recommendation: Add workflow examples
```

---

## Integration with Development Workflow

### Git Hooks (Future)

**Pre-commit hook:**
- Validate documentation syntax
- Check for broken references
- Ensure documentation updated if code changed

**Post-commit hook:**
- Update documentation index
- Regenerate cross-reference graph
- Calculate coverage metrics

### Pull Request Checklist

**Before merging:**
- [ ] Documentation updated for all code changes
- [ ] Validation passes (syntax, references, structure)
- [ ] Cross-references added and bidirectional
- [ ] No new TODO/FIXME markers in docs
- [ ] Coverage maintained or improved

### Continuous Integration

**CI pipeline checks:**
- Run documentation validation
- Check for broken references
- Verify cross-reference consistency
- Generate coverage report

---

## Quick Reference

### Documentation File Locations

- **Project Overview**: `!DOC/SYSTEM_OVERVIEW.md`
- **Technical Specs**: `!DOC/TECHNICAL_SPECIFICATION.md`
- **Database Schema**: `!DOC/DB.md`
- **Strategy & Roadmap**: `!DOC/STRATEGY.md`
- **Architecture Decisions**: `!DOC/concept.md`
- **Session Logs**: `!DOC/CLAUDE_SESSION_LOG.md`

### Common Tasks

**Update documentation after code change:**
```bash
# 1. Find affected docs
grep -r "function_name" !DOC/

# 2. Update docs
vim !DOC/TECHNICAL_SPECIFICATION.md

# 3. Validate (manual for now)
# - Check code block syntax
# - Verify file paths exist
# - Ensure cross-references work

# 4. Commit together
git add app/services/my_service.py !DOC/TECHNICAL_SPECIFICATION.md
git commit -m "feat: Update my_service + docs"
```

**Create new documentation:**
```markdown
# New Document Title

## Summary
[2-3 sentences]

## Overview
[High-level explanation]

## Details
[Implementation specifics]

## Related Documentation
- **Depends-On**: [Required reading](./OTHER_DOC.md)
- **Related-To**: [Similar topic](./RELATED_DOC.md)

## Last Updated
2025-01-31: Initial creation
```

**Mark documentation as outdated:**
```markdown
<!-- OUTDATED: Reason for staleness -->
<!-- Last updated: YYYY-MM-DD, threshold: 90 days -->

# Document Title
...
```

---

## Key Principles Summary

1. **Synchronize**: Update docs in same commit as code changes
2. **Validate**: Check syntax, references, structure before committing
3. **Cross-Reference**: Create bidirectional links between related docs
4. **Structure**: Use consistent format (Summary → Overview → Details)
5. **Detect Staleness**: Flag outdated docs (broken refs, time threshold)
6. **Remove Dead Docs**: Archive or delete obsolete documentation
7. **Track Coverage**: Monitor documentation completeness by component
8. **Token Efficiency**: Structure for progressive detail levels

---

## Future Enhancements

When the Documentation Management System is implemented (see `.kiro/specs/documentation-management-system/`):

- **Automated validation**: Run on every commit
- **Semantic search**: Find related docs by concept, not just keywords
- **Auto cross-references**: Discover relationships using embeddings
- **Staleness scanning**: Periodic checks for outdated content
- **Coverage reports**: Automated gap identification
- **Hook system**: Trigger doc updates on file changes
- **Version history**: Track documentation evolution over time
- **Multi-language**: Support documentation in multiple languages

Until then, apply these principles manually to maintain documentation quality.
