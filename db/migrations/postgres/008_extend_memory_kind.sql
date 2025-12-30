-- Migration 008: Extend memory_kind enum to include error_pattern
-- Adds new 'error_pattern' value to memory_kind enum for tracking recurring user errors

-- Add new enum value for error patterns
ALTER TYPE memory_kind ADD VALUE IF NOT EXISTS 'error_pattern';

-- Create index for filtering by metadata type
-- This allows efficient queries like: WHERE meta->>'type' = 'pronunciation_error'
CREATE INDEX IF NOT EXISTS idx_memories_meta_type
ON memories ((meta->>'type'))
WHERE kind = 'error_pattern';

-- Update enum comment for documentation
COMMENT ON TYPE memory_kind IS 'Memory types:
- episodic: Individual memories of events and conversations
- semantic: General factual knowledge about the user
- persona: Personality traits and characteristics
- skill: Learned abilities and competencies
- error_pattern: Recurring mistakes to watch for and help correct';

-- Verification query (for testing)
-- SELECT enum_range(NULL::memory_kind);
