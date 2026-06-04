-- Migration 008: Align memory_kind enum with application values
-- Adds canonical memory values used by MemoryKind in app/models/enums_and_dimensions.py

ALTER TYPE memory_kind ADD VALUE IF NOT EXISTS 'fact';
ALTER TYPE memory_kind ADD VALUE IF NOT EXISTS 'preference';
ALTER TYPE memory_kind ADD VALUE IF NOT EXISTS 'experience';
ALTER TYPE memory_kind ADD VALUE IF NOT EXISTS 'goal';
ALTER TYPE memory_kind ADD VALUE IF NOT EXISTS 'error_pattern';

-- Create index for filtering by metadata type
-- This allows efficient queries like: WHERE meta->>'type' = 'pronunciation_error'
CREATE INDEX IF NOT EXISTS idx_memories_meta_type
ON memories ((meta->>'type'))
WHERE kind = 'error_pattern';

-- Update enum comment for documentation
COMMENT ON TYPE memory_kind IS 'Memory types:
- fact: Stable facts about the learner
- preference: Learning and interaction preferences
- experience: Relevant background, projects, and events
- goal: Learning and career goals
- error_pattern: Recurring mistakes to watch for and help correct';

-- Verification query (for testing)
-- SELECT enum_range(NULL::memory_kind);
