# Code Simplification Implementation Checklist

Use this checklist to track progress when integrating the simplification helpers into the codebase.

## Phase 1: Validation (Recommended First Step)

- [ ] Review all helper modules
  - [ ] `app/api/voice_helpers.py`
  - [ ] `app/api/response_mappers.py`
  - [ ] `app/services/logger_helpers.py`
  - [ ] `app/services/query_helpers.py`

- [ ] Run unit tests for helpers
  ```bash
  pytest tests/test_voice_helpers.py -v
  pytest tests/test_response_mappers.py -v
  pytest tests/test_logger_helpers.py -v
  pytest tests/test_query_helpers.py -v
  ```

- [ ] Fix any failing tests
- [ ] Review test coverage (aim for >90%)

## Phase 2: Pilot Integration (memory_and_interests.py)

**Why start here?** Most straightforward - just response mapping, no complex logic.

### Step 2.1: Prepare
- [ ] Create backup branch: `git checkout -b refactor/simplify-api-responses`
- [ ] Read current `app/api/memory_and_interests.py` (354 lines)

### Step 2.2: Add Imports
- [ ] Add to top of `memory_and_interests.py`:
  ```python
  from app.api.response_mappers import (
      map_interest_to_response,
      map_interests_to_list_response,
      map_memory_to_response,
      map_memories_to_list_response,
      map_xp_event_to_response,
      map_xp_events_to_list_response,
      map_learning_plan_to_response,
  )
  ```

### Step 2.3: Replace Response Mapping (Interest Endpoints)
- [ ] `create_user_interest()` - lines 36-41 → `return map_interest_to_response(interest)`
- [ ] `get_user_interests()` - lines 59-69 → `return map_interests_to_list_response(interests)`
- [ ] `get_top_user_interests()` - lines 84-94 → `return map_interests_to_list_response(interests)`
- [ ] `update_interest_weight()` - lines 113-118 → `return map_interest_to_response(updated_interest)`

### Step 2.4: Replace Response Mapping (Memory Endpoints)
- [ ] `create_memory()` - lines 131-141 → `return map_memory_to_response(memory)`
- [ ] `get_memory()` - lines 159-168 → `return map_memory_to_response(memory)`
- [ ] `get_user_memories()` - lines 185-199 → `return map_memories_to_list_response(memories)`
- [ ] `search_user_memories()` - lines 215-229 → `return map_memories_to_list_response(memories)`

### Step 2.5: Replace Response Mapping (Learning Plan Endpoints)
- [ ] `create_learning_plan()` - lines 242-250 → `return map_learning_plan_to_response(plan)`
- [ ] `get_learning_plan()` - lines 265-272 → `return map_learning_plan_to_response(plan)`
- [ ] `get_user_active_plan()` - lines 286-293 → `return map_learning_plan_to_response(plan)`

### Step 2.6: Replace Response Mapping (XP Endpoints)
- [ ] `create_xp_event()` - lines 306-314 → `return map_xp_event_to_response(event)`
- [ ] `get_user_xp_events()` - lines 331-343 → `return map_xp_events_to_list_response(events)`

### Step 2.7: Test
- [ ] Run API tests: `pytest tests/ -k memory_and_interests -v`
- [ ] Manual test key endpoints:
  - [ ] GET /api/v1/users/{user_id}/interests
  - [ ] GET /api/v1/users/{user_id}/memories
  - [ ] POST /api/v1/memories/
  - [ ] GET /api/v1/users/{user_id}/xp-total

### Step 2.8: Verify
- [ ] Check response schemas match expected format
- [ ] Verify no fields missing
- [ ] Count lines saved: 354 → ~230 lines (target: -35%)
- [ ] Commit changes: `git commit -m "Refactor: simplify memory_and_interests API response mapping"`

## Phase 3: Voice WebSocket Simplification (voice.py)

**Why second?** Larger impact but more complex - requires careful testing.

### Step 3.1: Prepare
- [ ] Create/checkout branch: `git checkout -b refactor/simplify-voice-websocket`
- [ ] Read current `app/api/voice.py` (691 lines)

### Step 3.2: Add Imports
- [ ] Add to top of `voice.py`:
  ```python
  from app.api.voice_helpers import (
      handle_goal_setting,
      rebuild_system_prompt,
      award_session_gamification,
  )
  ```

### Step 3.3: Replace Goal Setting Logic (First Occurrence)
- [ ] Lines 207-260: Replace with:
  ```python
  if message.get("type") == "set_goal":
      goal_text = message.get("goal", "").strip()
      if goal_text:
          result = await handle_goal_setting(
              goal_text, user_id, db, learning_plan_service,
              session_context, websocket
          )
          if result[0]:  # If successful
              current_mode, focus_area = result
              system_prompt = rebuild_system_prompt(
                  current_mode, session_context, focus_area,
                  vocabulary_list, memory_section
              )
      continue
  ```

### Step 3.4: Replace Goal Detection Logic (Second Occurrence)
- [ ] Lines 302-349: Similar replacement with `handle_goal_setting()`

### Step 3.5: Replace System Prompt Rebuilding
- [ ] Line 177-186: Initial prompt → Use `rebuild_system_prompt()`
- [ ] Lines 242-249: After goal set → Use `rebuild_system_prompt()`
- [ ] Lines 270-277: After mode change → Use `rebuild_system_prompt()`
- [ ] Lines 339-346: After goal detection → Use `rebuild_system_prompt()`
- [ ] Lines 356-363: After mode request → Use `rebuild_system_prompt()`

### Step 3.6: Replace Gamification Logic (Session End)
- [ ] Lines 513-558: Replace entire gamification block with:
  ```python
  await award_session_gamification(db, user_id, session_id)
  ```

### Step 3.7: Replace Gamification Logic (Disconnect Handler)
- [ ] Lines 574-584: Replace with:
  ```python
  if turn_count > 0:
      await award_session_gamification(db, user_id, session_id)
  ```

### Step 3.8: Test
- [ ] Run voice tests: `pytest tests/ -k voice -v`
- [ ] Manual WebSocket test:
  - [ ] Connect to `/api/v1/voice/chat`
  - [ ] Send text message
  - [ ] Set goal
  - [ ] Change mode
  - [ ] End session
  - [ ] Verify gamification (XP awarded, streak updated)

### Step 3.9: Verify
- [ ] All WebSocket message types work
- [ ] Goal setting creates vocab cards
- [ ] Mode switching updates prompts
- [ ] Gamification awards all bonuses
- [ ] Count lines saved: 691 → ~550 lines (target: -20%)
- [ ] Commit: `git commit -m "Refactor: simplify voice WebSocket with helper functions"`

## Phase 4: Logger Simplification (data_flow_logger.py)

**Why third?** Non-critical - logging improvements won't break functionality.

### Step 4.1: Prepare
- [ ] Checkout branch: `git checkout -b refactor/simplify-logging`
- [ ] Read current `app/services/data_flow_logger.py` (241 lines)

### Step 4.2: Import Helpers
- [ ] Add to top of file:
  ```python
  from app.services.logger_helpers import (
      format_user_info,
      format_data_preview,
      build_log_message,
  )
  ```

### Step 4.3: Replace _format_data_preview Method
- [ ] Lines 193-208: Replace method body with:
  ```python
  return format_data_preview(data, max_len)
  ```
  Or remove method entirely and use helper directly

### Step 4.4: Refactor log_postgres_write
- [ ] Lines 46-62: Simplify to:
  ```python
  def log_postgres_write(self, table, data, operation="INSERT", user_id=None):
      self.stats["postgres_writes"] += 1
      message = build_log_message(
          "📝", "POSTGRES", operation, "→", table,
          format_data_preview(data), user_id
      )
      logger.info(message)
  ```

### Step 4.5: Refactor log_postgres_read
- [ ] Lines 64-77: Similar simplification

### Step 4.6: Refactor log_qdrant_write
- [ ] Lines 79-95: Use `build_log_message()`

### Step 4.7: Refactor log_qdrant_search
- [ ] Lines 97-110: Use `build_log_message()`

### Step 4.8: Refactor log_neo4j_write
- [ ] Lines 112-127: Use `build_log_message()`

### Step 4.9: Test
- [ ] Run logger tests (if any exist)
- [ ] Manually verify logs still format correctly
- [ ] Check log output in running application

### Step 4.10: Verify
- [ ] All log messages still formatted correctly
- [ ] User info appears when provided
- [ ] Data preview truncates long values
- [ ] Count lines saved: 241 → ~180 lines (target: -25%)
- [ ] Commit: `git commit -m "Refactor: simplify data flow logger with helpers"`

## Phase 5: Query Simplification (context_builder.py and services)

**Why last?** Most invasive - touches database layer.

### Step 5.1: Prepare
- [ ] Checkout branch: `git checkout -b refactor/simplify-queries`
- [ ] Read current `app/services/context_builder.py` (182 lines)

### Step 5.2: Refactor context_builder.py

- [ ] Import helpers:
  ```python
  from app.services.query_helpers import (
      get_by_id,
      get_by_user_id,
      get_top_by_field,
  )
  ```

- [ ] Simplify `get_user_profile()` (lines 51-74):
  ```python
  async def get_user_profile(self, user_id: int) -> Optional[UserProfile]:
      user = await get_by_id(self.db, User, user_id)
      if not user:
          return None
      # ... rest of method
  ```

- [ ] Simplify `get_user_interests()` (lines 76-94):
  ```python
  async def get_user_interests(self, user_id: int, limit: int = 10) -> List[PromptUserInterest]:
      interests = await get_top_by_field(
          self.db, UserInterest, user_id,
          field_name="salience", limit=limit
      )
      return [PromptUserInterest(topic=i.topic, salience=i.salience) for i in interests]
  ```

- [ ] Simplify `get_user_memories()` (lines 96-118):
  ```python
  async def get_user_memories(self, user_id: int, limit: int = 10) -> List[PromptMemory]:
      memories = await get_top_by_field(
          self.db, Memory, user_id,
          field_name="salience", limit=limit
      )
      return [PromptMemory(kind=m.kind, content=m.content, salience=m.salience) for m in memories]
  ```

- [ ] Simplify `get_recent_utterances()` (lines 120-145):
  ```python
  async def get_recent_utterances(self, session_id: str, limit: int = 10) -> List[RecentUtterance]:
      # Note: This one needs custom query for session_id, not user_id
      # Can still potentially simplify with a new helper
  ```

### Step 5.3: Apply to Other Services
- [ ] `app/services/memory_and_interests.py` - Replace repetitive queries
- [ ] `app/services/dimensions.py` - Replace get_by_id patterns
- [ ] `app/services/database.py` - Replace user queries

### Step 5.4: Test
- [ ] Run all service tests: `pytest tests/test_services/ -v`
- [ ] Run integration tests: `pytest tests/integration/ -v`
- [ ] Verify database queries still work correctly

### Step 5.5: Verify
- [ ] All queries return correct results
- [ ] Pagination still works
- [ ] Ordering still correct
- [ ] Count lines saved in context_builder: 182 → ~120 lines (target: -34%)
- [ ] Commit: `git commit -m "Refactor: simplify database queries with generic helpers"`

## Phase 6: Final Validation

- [ ] Run full test suite:
  ```bash
  pytest tests/ -v --cov=app
  ```

- [ ] Check test coverage (aim for >80% overall)

- [ ] Manual end-to-end testing:
  - [ ] Create user
  - [ ] Start voice chat session
  - [ ] Set goal
  - [ ] Have conversation
  - [ ] End session
  - [ ] Check XP/streak updated
  - [ ] Verify memories created
  - [ ] Check vocabulary cards generated

- [ ] Review code quality:
  ```bash
  flake8 app/api/voice_helpers.py
  flake8 app/api/response_mappers.py
  flake8 app/services/logger_helpers.py
  flake8 app/services/query_helpers.py
  mypy app/api/voice_helpers.py
  ```

- [ ] Performance check:
  - [ ] No new N+1 queries introduced
  - [ ] Response times similar or better
  - [ ] Memory usage stable

## Phase 7: Merge and Deploy

- [ ] Create pull requests for each phase:
  - [ ] PR 1: Response mappers (memory_and_interests.py)
  - [ ] PR 2: Voice helpers (voice.py)
  - [ ] PR 3: Logger helpers (data_flow_logger.py)
  - [ ] PR 4: Query helpers (context_builder.py, services)

- [ ] Get code reviews

- [ ] Merge to main branch (one PR at a time)

- [ ] Deploy to staging environment

- [ ] Monitor for issues:
  - [ ] Check error logs
  - [ ] Verify API responses
  - [ ] Test WebSocket connections
  - [ ] Confirm gamification working

- [ ] Deploy to production

- [ ] Post-deployment verification

## Summary Metrics

Track these metrics to measure success:

| File | Before | After | Saved | Percentage |
|------|--------|-------|-------|------------|
| voice.py | 691 lines | ~550 lines | ~140 lines | -20% |
| memory_and_interests.py | 354 lines | ~230 lines | ~120 lines | -35% |
| data_flow_logger.py | 241 lines | ~180 lines | ~60 lines | -25% |
| context_builder.py | 182 lines | ~120 lines | ~60 lines | -34% |
| **TOTAL** | **1,468 lines** | **~1,080 lines** | **~380 lines** | **-26%** |

## Rollback Plan

If issues arise:

1. **Identify problematic helper**: Which helper is causing issues?
2. **Revert specific changes**: Git revert the commit introducing that helper
3. **Keep other helpers**: Don't need to revert everything
4. **Fix and retry**: Fix the helper and try again

## Notes

- Take your time - better to do one phase well than rush all phases
- Test thoroughly after each phase
- Don't hesitate to adjust helpers if needed
- Keep old code in comments initially for reference
- Remove commented code only after verification

## Completion

- [ ] All phases completed
- [ ] All tests passing
- [ ] Code reviewed and approved
- [ ] Deployed to production
- [ ] No regressions detected
- [ ] Team trained on new patterns
- [ ] Documentation updated

**Date Completed**: _____________

**Team Sign-off**: _____________
